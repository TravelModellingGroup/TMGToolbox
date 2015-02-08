'''
    Copyright 2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

    This file is part of the TMG Toolbox.

    The TMG Toolbox is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The TMG Toolbox is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with the TMG Toolbox.  If not, see <http://www.gnu.org/licenses/>.
'''
'''
Contains a bunch of Python utility functions commonly used in TMG tools
and products. Set up as a non-runnable (e.g. private) Emme module so that
it can be distributed in the TMG toolbox

'''

import inro.modeller as _m
import math
import inro.emme.core.exception as _excep
from contextlib import contextmanager, nested
import warnings as _warn
import sys as _sys
import traceback as _tb
import subprocess as _sp
_MODELLER = _m.Modeller()
_DATABANK = _MODELLER.emmebank
class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Utilities",
                                description="Collection of private utilities",
                                branding_text="- TMG Toolbox")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()

#-------------------------------------------------------------------------------------------

def formatReverseStack():
    eType, eVal, eTb = _sys.exc_info()
    stackList = _tb.extract_tb(eTb)
    msg = "%s: %s\n\n\Stack trace below:" %(eVal.__class__.__name__, str(eVal))
    stackList.reverse()
    for file, line, func, text in stackList:
        msg += "\n  File '%s', line %s, in %s" %(file, line, func)
    return msg

#-------------------------------------------------------------------------------------------

def iterpairs(iterable):
    '''
    Iterates through two subsequent elements in any iterable.
    Example: 
        x = [1,2,3,4,5]
        for (val1, val2) in iterpairs(x): print "1=%s 2=%s" %(val1, val2)
        >>> 1=1 2=2
        >>> 1=2 2=3
        >>> 1=3 2=4
        >>> 1=4 2=5
    '''
    
    iterator = iterable.__iter__()
    
    try: prev = iterator.next()
    except StopIteration: return
    
    for val in iterator:
        yield prev, val
        prev = val


#-------------------------------------------------------------------------------------------

def itersync(list1, list2):
    '''
    Iterates through tuples of corresponding values for
    lists of the same length.
    
    Example:
        list1 = [1,2,3,4,5]
        list2 = [6,7,8,9,10]
        
        for a, b in itersync(list1, list2):
            print a,b
        >>>1 6
        >>>2 7
        >>>3 8
        >>>4 9
        >>>5 10
    '''
    
    if len(list1) != len(list2):
        raise IndexError("Lists must be of the same length")
    
    for i in xrange(len(list1)):
        yield list1[i], list2[i]

#-------------------------------------------------------------------------------------------

def equap(number1, number2, precision= 0.00001):
    '''
    Tests for shallow floating point approximate equality.
    
    Args:
        - number 1: The first float
        - number 2: The second float
        - precision (=0.00001): The maximum allowed error.
    '''
    diff = abs(float(number1), float(number2))
    return diff < precision

#-------------------------------------------------------------------------------------------

def databankHasDifferentZones(emmebank):
    '''
    Checks that all scenarios have the same zone system.
    
    Args:
        - emmebank: The Emmebank object to test
    
    Returns:
        - True if all of the scenarios have the same zone system,
                False otherwise.
    '''
    
    scenarioZones = [set(sc.zone_numbers) for sc in emmebank.scenarios()]
    differentZones = False
    for nZones1, nZones2 in iterpairs(scenarioZones):
        if nZones1 != nZones2:
            differentZones = True
            break
    return differentZones

#-------------------------------------------------------------------------------------------

def getScenarioModes(scenario, types=['AUTO', 'AUX_AUTO', 'TRANSIT', 'AUX_TRANSIT']):
    '''
    Returns a list of mode tuples [(id, type, description)] for a given Scenario object, 
    bypassing the need to load the Network first.
    '''
    '''
    IMPLEMENTATION NOTE: This currently uses an *undocumented* function for the
    Scenario object (scenario.modes()). I can confirm that this function exists
    in Emme 4.0.3 - 4.0.8, and is supported in the 4.1 Beta versions (4.1.0.7 and
    4.1.0.8). Since this is unsupported, however, there is a possibility that
    this will need to be changed going forward (possibly using a new function
    scenario.get_partial_network(...) which is included in 4.1.0.7 but also
    currently undocumented).
        - @pkucirek 11/03/2014
    '''
    return [(mode.id, mode.type, mode.description) for mode in scenario.modes() if mode.type in types]

#-------------------------------------------------------------------------------------------

_mtxNames = {'FULL' : 'mf',
             'DESTINATION' : 'md',
             'ORIGIN' : 'mo',
             'SCALAR' : 'ms'}

def initializeMatrix(id=None, default=0, name="", description="", matrix_type='FULL', \
                     preserve_description= False):
    '''
    Utility function for creation and initialization of matrices. Only works
    for the current Emmebank.
    
    Args:
        - id (=None): Optional. Accepted value is a string or integer ID  (must 
            also specify a matrix_type to be able to use integer ID). If specified, 
            this function will initialize the matrix with the given ID to a new
            default value; changing its name and description if they are given. 
            If unspecified, this function will create an available matrix - however
            the 'matrix_type' argument MUST also be specified.
        - default (=0): Optional The numerical value to initialize the matrix to 
            (i.e., its default value).
        - name (=""): Optional. If specified, the newly-initialized matrix will
            have this as its 6-character name.
        - description (=""): Optional. If specified, the newly-initialized matrix will
            have this as its 40-character description.
        - matrix_type (='FULL'): One of 'SCALAR', 'ORIGIN', 'DESTINATION',
            or 'FULL'. If an ID is specified, the matrix type will be
            inferred from the ID's prefix. This argument is NOT optional
            if passing in an integer ID, or if requesting a new matrix.
        - preserve_description (=False): Set to True to preserve the description of an 
            existing matrix. This is useful if you don't know whether the matrix being 
            initialized exists or is new, and you want to specify a 'default' 
            description.
    
    Returns: The Emme Matrix object created or initialized.
    '''
    
    if id == None:
        #Get an available matrix
        id = _DATABANK.available_matrix_identifier(matrix_type)
    elif type(id) == int:
        #If the matrix id is given as an integer
        try:
            id = "%s%s" %(_mtxNames[matrix_type],id)
        except KeyError, ke:
            raise TypeError("Matrix type '%s' is not a valid matrix type." %matrix_type)
    elif 'type' in dir(id):
        #If the matrix id is given as a matrix object
        t = id.type
        if not t in _mtxNames:
            raise TypeError("Assumed id was a matrix, but its type value was not recognized %s" %type(id))
        id = id.id #Set the 'id' variable to the matrix's 'id' property.
    elif type(id) != str:
        raise TypeError("Id is not a supported type: %s" %type(id))
    
    mtx = _DATABANK.matrix(id)
    
    if mtx == None:
        #Matrix does not exist, so create it.
        mtx = _DATABANK.create_matrix(id, default_value=default)
        if name: mtx.name = name[:6]
        if description:  mtx.description = description[:40]
        _m.logbook_write("Created new matrix %s: '%s' (%s)." %(id, mtx.name, mtx.description))
    else:
        if mtx.read_only: raise _excep.ProtectionError("Cannot modify matrix '%s' as it is protected against modifications." %id)
        
        mtx.initialize(value=default)
        if name: mtx.name = name[:6]
        if description and not preserve_description:  mtx.description = description[:40]
        _m.logbook_write("Initialized existing matrix %s: '%s' (%s)." %(id, mtx.name, mtx.description))
        
    return mtx

#-------------------------------------------------------------------------------------------

def getAvailableScenarioNumber():
    '''
    Returns: The number of an available scenario. Raises an exception
    if the _DATABANK is full.
    '''
    for i in range(0, _m.Modeller().emmebank.dimensions['scenarios']):
        if _m.Modeller().emmebank.scenario(i + 1) == None:
            return (i + 1)
    
    raise inro.emme.core.exception.CapacityError("No new scenarios are available: databank is full!")

#-------------------------------------------------------------------------------------------

TEMP_ATT_PREFIXES = {'NODE': 'ti',
                     'LINK': 'tl',
                     'TURN': 'tp',
                     'TRANSIT_LINE': 'tt',
                     'TRANSIT_SEGMENT': 'ts'}

@contextmanager
def tempExtraAttributeMANAGER(scenario, domain, default= 0.0, description= None, returnId= False):
    '''
    Creates a temporary extra attribute in a given scenario, yield-returning the
    attribute object. Designed to be used as a context manager, for cleanup
    after a run.
    
    Extra attributes are labeled thusly:
        - Node: @ti123
        - Link: @tl123
        - Turn: @tp123
        - Transit Line: @tt123
        - Transit Segment: @ts123
        (where 123 is replaced by a number)
        
    Args: (scenario, domain, default= 0.0, description= None)
        - scenario= The Emme scenario object in which to create the extra attribute
        - domain= One of 'NODE', 'LINK', 'TURN', 'TRANSIT_LINE', 'TRANSIT_SEGMENT'
        - default= The default value of the extra attribute
        - description= An optional description for the attribute
        - returnId (=False): Flag to return either the Extra Attribute object, or its ID
        
    Yields: The Extra Attribute object created (or its ID as indicated by the returnId arg).
    '''
    
    domain = str(domain).upper()
    if not domain in TEMP_ATT_PREFIXES:
        raise TypeError("Domain '%s' is not a recognized extra attribute domain." %domain)
    prefix = TEMP_ATT_PREFIXES[domain]
    
    existingAttributeSet = set([att.name for att in scenario.extra_attributes() if att.type == domain])
    
    index = 1
    id = "@%s%s" %(prefix, index)
    while id in existingAttributeSet:
        index += 1
        id = "@%s%s" %(prefix, index)
        if index > 999:
            raise Exception("Scenario %s already has 999 temporary extra attributes" %scenario)
    tempAttribute = scenario.create_extra_attribute(domain, id, default)
    msg = "Created temporary extra attribute %s in scenario %s" %(id, scenario)
    if description:
        tempAttribute.description = description
        msg += ": %s" %description
    _m.logbook_write(msg)
    
    if returnId:
        retval = tempAttribute.id
    else:
        retval = tempAttribute
    
    try:
        yield retval
    finally:
        scenario.delete_extra_attribute(id)
        _m.logbook_write("Deleted extra attribute %s" %id)

#-------------------------------------------------------------------------------------------

@contextmanager
def tempMatrixMANAGER(description="[No description]", matrix_type='FULL', default=0.0):
    '''
    Creates a temporary matrix in a context manager.
    
    Args:
        - description (="[No description]"): The description of the temporary matrix.
        - matrix_type (='FULL'): The type of temporary matrix to create. One of 
            'SCALAR', 'ORIGIN', 'DESTINATION', or 'FULL'.
        - default (=0.0): The matrix's default value.
    '''
    
    mtx = initializeMatrix(default=default, description= 'Temporary %s' %description, \
                           matrix_type=matrix_type)
    
    if mtx == None:
        raise Exception("Could not create temporary matrix: %s" %description)
    
    try:
        yield mtx
    finally:
        _DATABANK.delete_matrix(mtx.id)
        
        s = "Deleted matrix %s." %mtx.id
        _m.logbook_write(s)

#-------------------------------------------------------------------------------------------

#@deprecated: In Emme 4.1.2 the indices have been changed
def fastLoadTransitSegmentAttributes(scenario, list_of_attribtues):
    '''
    BROEKN SINCE EMME 4.1.2. Use fastLoadSummedSegmentAttributes instead
    
    Performs a fast partial read of transit segment attributes,
    using scenario.get_attribute_values.
    
    Args:
        - scenario: The Emme Scenario object to load from
        - list_of_attributes: A list of TRANSIT SEGMENT attribute names to load.
    
    Returns: A dictionary, where the keys are transit line IDs.
        Each key is mapped to a list of attribute dictionaries.
        
        Example:
            {'TS01a': [{'number': 0, 'transit_volume': 200.0}, 
                        {'number': 1, 'transit_volume': 210.0} ...] ...} 
    '''
    '''
    Implementation note: The scenario method 'get_attribute_vlues' IS documented,
    however the return value is NOT. I've managed to decipher its structure
    but since it is not documented by INRO it could be changed.
        - pkucirek April 2014
        
    IMPORTANT: This function is currently broken for version 4.1.2! An error
    will be raised if tried. - pkucirek June 2014
    '''
    major, minor, release = getEmmeVersion(tuple)
    if major >= 4 and minor >= 1 and release >= 2:
        raise Exception("fastLoadTransitSegmentAttributes is deprecated in Emme 4.1.2 or newer versions!")
    
    retval = {}
    root_data = scenario.get_attribute_values('TRANSIT_SEGMENT', list_of_attribtues)
    indices = root_data[0]
    values = root_data[1:]
    
    for lineId, segmentIndices in indices.iteritems():
        segments = []
        
        for number, dataIndex in enumerate(segmentIndices[1]):
            segment = {'number': number}
            for attIndex, attName in enumerate(list_of_attribtues):
                segment[attName] = values[attIndex][dataIndex]
            segments.append(segment)
        retval[lineId] = segments
    
    return retval

#-------------------------------------------------------------------------------------------

def fastLoadSummedSegmentAttributes(scenario, list_of_attributes):
    '''
    Performs a fast partial read of transit segment attributes, aggregated to each line,
    using scenario.get_attribute_values.
    
    Args:
        - scenario: The Emme Scenario object to load from
        - list_of_attributes: A list of TRANSIT SEGMENT attribute names to load.
        
    Returns: A dictionary whose keys are transit line IDs and whose values
        are dictionaries of attributes.
    '''
    retval = {}
    root_data = scenario.get_attribute_values('TRANSIT_SEGMENT', list_of_attributes)
    indices = root_data[0]
    values = root_data[1:]
    
    major, minor, release, beta = getEmmeVersion(tuple)
    if major >= 4 and minor >= 1 and release >= 2:
        get_iter = lambda segmentIndices: segmentIndices.iteritems()
    else:
        get_iter = lambda segmentIndices: itersync(*segmentIndices)
    
    for lineId, segmentIndices in indices.iteritems():
        line = {'id': lineId}
        
        for iNode, dataRow in get_iter(segmentIndices):
            for attName, dataColumn in itersync(list_of_attributes, values):
                value = dataColumn[dataRow]
                if attName in line: line[attName] += value
                else: line[attName] = value
        
        retval[lineId] = line
    
    return retval
        
#-------------------------------------------------------------------------------------------

def fastLoadTransitLineAttributes(scenario, list_of_attributes):
    '''
    Performs a fast partial read of transit line attributes,
    using scenario.get_attribute_values.
    
    Args:
        - scenario: The Emme Scenario object to load from
        - list_of_attributes: A list of TRANSIT LINE attribute names to load.
    
    Returns: A dictionary, where the keys are transit line IDs.
        Each key is mapped to a dictionary of attributes (one for
        each attribute in the list_of_attributes arg) plus 'id'.
        
        Example:
            {'TS01a': {'id': 'TS01a', 'headway': 2.34, 'speed': 52.22 } ...}
    ''' 
    
    retval = {}
    root_data = scenario.get_attribute_values('TRANSIT_LINE', list_of_attributes)
    indices = root_data[0]
    values = root_data[1:]
    
    for lineId, dataIndex in indices.iteritems():
        line = {'id': lineId}
        
        for attIndex, attName in enumerate(list_of_attributes):
            line[attName] = values[attIndex][dataIndex]
        retval[lineId] = line
    return retval

#-------------------------------------------------------------------------------------------

def fastLoadLinkAttributes(scenario, list_of_attributes):
    '''
    Performs a fast partial read of link attributes, using
    scenario.get_attribute_values.
    
    Args:
        - scenario: The scenario to load from
        - list_of_attributes: A list of attributes to load.
    
    Returns:
        A dictionary, where the keys are (i_node, j_node) tuples
        (link IDs), and whose values are dictionaries of
        attribute : values.
        
        Example: {(10001, 10002): {'i_node': 10001, 'j_node': 10002, 'length': 1.002} ...}
    '''
    
    package = scenario.get_attribute_values('LINK', list_of_attributes)
    indices = package[0]
    attribute_tables = package[1:]
    
    retval = {}
    for i_node, outgoing_links in indices.iteritems():
        for j_node, index in outgoing_links.iteritems():
            link = i_node, j_node
            attributes = {'i_node': i_node, 'j_node': j_node}
            for att_name, table in itersync(list_of_attributes, attribute_tables):
                attributes[att_name] = table[index]
            retval[link] = attributes
    return retval

#-------------------------------------------------------------------------------------------

def lineConcatenator(network, lineSet, newId):

    if len(lineSet) <= 1:
        raise Exception("Need at least two lines")
    
    lines = []
    for lineId in lineSet:
        lines.append(network.transit_line(lineId))
    itineraries = []
    for line in lines:
        itineraries.append([node.number for node in line.itinerary()])
    
    #Check if end points match and combine itineraries
    combinedItinerary = itineraries[0]
    for num, item in enumerate(itineraries):
        if num == (len(itineraries) - 1):
            combinedItinerary += item[1:]
            break #don't test the final line
        
        nextItem = itineraries[num + 1]

        if item[-1] != nextItem[0]: #compare final stop of current line to first stop of next line
            raise Exception("Lines don't connect!")
        elif num == 0: #don't need to add the first line's itinerary
            continue
        else:
            combinedItinerary += item[1:] #combine stop lists, removing the redundant start node
                      
    attNames = network.attributes('TRANSIT_SEGMENT')
    lineAttNames = network.attributes('TRANSIT_LINE') 
    #Grabbing segment attributes. 
    combinedSegmentAttributes = []
    for line in lines:
        segmentAttributes = []
        for segment in line.segments(False):
            d = {}
            for attName in attNames:
                d[attName] = segment[attName]
            segmentAttributes.append(d) 
        combinedSegmentAttributes += segmentAttributes  

    #Allow the recreated line to take on the attributes of the first line in the list
    newVehicleId = lines[0].vehicle.id
    lineAttributes = {}
    for attName in lineAttNames:
        lineAttributes[attName] = lines[0][attName]
                
    newLine = network.create_transit_line(newId, newVehicleId, combinedItinerary)
        
    for num, segment in enumerate(newLine.segments(False)):
        d = combinedSegmentAttributes[num] 
        for attName, value in d.iteritems():
            segment[attName] = value
        
    for attName, value in lineAttributes.iteritems():
        newLine[attName] = value


#-------------------------------------------------------------------------------------------

def getEmmeVersion(returnType= str):
    '''
    Gets the version of Emme that is currently running, as a string. For example,
    'Emme 4.0.8', or 'Emme 4.1.0 32-bit'.
    
    Args & returns:
        - returnType (=str): The desired Python type to return. Accepted types are:
            str: Returns in the form "Emme 4.1.0 32-bit". This is the most verbose.
            tuple: Returns in the form (4, 1, 0) tuple of integers.
            float: Returns in the form 4.1
            int: Return in the form 4
            
        - asTuple (=False): Boolean flag to return the version number as a string, or
                as a tuple of ints (e.g., [4,1,0] for Emme 4.1.0)
    '''

    app = _MODELLER.desktop
    if hasattr(app, 'version'):
        return _getVersionNew(app, returnType)
    else:
        return _getVersionOld(returnType)

def _getVersionNew(app, returnType):
    '''
    Available in versions 4.1.3 and newer
    '''
    
    if returnType == str:
        return str(app.version)
    
    version_tuple = app.version_info
    
    if returnType == tuple: return version_tuple
    
    if returnType == float: return version_tuple[0] + version_tuple[1] * 0.1
    
    if returnType == int: return version_tuple[0]
    
    raise TypeError("Type %s not accepted for getting Emme version" %returnType)

def _getVersionOld(returnType):
    '''
    Implementation note: For the string-to-int-tuple conversion, I've assumed the
    string version is of the form ['Emme', '4.x.x', ...] (i.e., the version string
    is the second item in the space-separated list). -pkucirek April 2014
    '''
    #The following is code directly from INRO
    emmeProcess = _sp.Popen(['Emme', '-V'], stdout= _sp.PIPE, stderr= _sp.PIPE)
    output = emmeProcess.communicate()[0]
    retval = output.split(',')[0]
    if returnType == str: return retval
    
    #The following is my own code
    components = retval.split(' ')
    version = components[1].split('.')
    versionTuple = [int(n) for n in version]
    if returnType == tuple: return versionTuple
    
    if returnType == float: return versionTuple[0] + versionTuple[1] * 0.1
    
    if returnType == int: return versionTuple[0]
    
    raise TypeError("Type %s not accepted for getting Emme version" %returnType)
#-------------------------------------------------------------------------------------------

EMME_INFINITY = float('1E+20')
def isEmmeInfinity(number, precision= 0.001):
    '''
    Tests if a matrix value is equal to "Emme infinity" or 1E+20 using approximate equality. 
    '''
    return equap(number, EMME_INFINITY, precision)

#-------------------------------------------------------------------------------------------

#@deprecated: 
def getExtents(network):
    '''
    Creates an Extents object from the given Network.
    '''
    minX = float('inf')
    maxX = - float('inf')
    minY = float('inf')
    maxY = - float('inf')
    for node in network.nodes():
        minX = min(minX, node.x)
        maxX = max(maxX, node.x)
        minY = min(minY, node.y)
        maxY = max(maxY, node.y)
    return Extents(minX - 1.0, minY - 1.0, maxX + 1.0, maxY + 1.0)

#-------------------------------------------------------------------------------------------

class IntRange():
    '''
    A smaller object to represent a range of integer values.
    Does NOT simplify to a list!
    '''
       
    def __init__(self, min, max):
        min = int(min)
        max = int(max)
        
        if min > max:
            self.__reversed = True
            self.min = max
            self.max = min
        else:
            self.__reversed = False
            self.min = min
            self.max = max
    
    def __contains__(self, val):
        return (val >= self.min and val < self.max)
    
    def __str__(self):
        return "%s - %s" %(self.min, self.max)
    
    def __iter__(self):
        i = self.min
        while (i < self.max):
            yield i
            i += 1 - 2 * self.__reversed #Count down if reversed
    
    def __len__(self):
        return abs(self.max - self.min)
    
    def contains(self, val):
        return val in self
    
    def length(self):
        return len(self)
    
    def overlaps(self, otherRange):
        return otherRange.min in self or otherRange.max in self or self.max in otherRange or self.min in otherRange
    
#-------------------------------------------------------------------------------------------

class FloatRange():
    '''
    Represents a range of float values. Supports containment and
    overlapping boolean operations.
    '''
    
    def __init__(self, min, max):
        self.min = (float) (min)
        self.max = (float) (max)

    def __contains__(self, val):
        return self.contains(val)
    
    def contains(self, val):
        return (val >= self.min and val < self.max)
    
    def length(self):
        return abs(self.max - self.min)
    
    def overlaps(self, otherRange):
        return otherRange.min in self or otherRange.max in self or self.max in otherRange or self.min in otherRange
    
    def __str__(self):
        return "%s - %s" %(self.min, self.max)

#-------------------------------------------------------------------------------------------

class ProgressTracker():
    
    '''
    Convenience class for tracking and reporting progress. Also
    captures the progress from other Emme Tools (such as those
    provided by INRO), and combines with a total progress.
    
    Handles progress at two levels: Tasks and Subtasks. Running
    an Emme Tool counts as a Task. The total number of tasks 
    must be known at initialization.
    
    Update April 2014: Can be 'reset' with a new number of tasks,
    for when two task-levels are needed but the number of full
    tasks are not known at initialization.
    '''
    
    def __init__(self, numberOfTasks):
        self._taskIncr = 1000.0 / numberOfTasks #floating point number
        self.reset()
        self._errorTools = set()
    
    def reset(self, numberOfTasks=None):
        self._subTasks = 0
        self._completedSubtasks = 0
        self._progress = 0.0 #floating point number
        self._toolIsRunning = False
        self._processIsRunning = False
        self._activeTool = None
        
        if numberOfTasks != None: #Can be reset with a new number of tasks
            self._taskIncr = 1000.0 / numberOfTasks
    
    def completeTask(self):
        '''
        Call to indicate a Task is complete.
        
        This function is called automatically
        at the end of a Subtask and at the end
        of a Tool run.
        '''
        if self._processIsRunning:
            self._processIsRunning =False
            self._subTasks = 0
            self._completedSubtasks = 0
        self._progress += self._taskIncr
    
    def runTool(self, tool, *args, **kwargs):
        '''
        Launches another Emme Tool, 'capturing' its progress
        to report a combined overall progress.
        
        Args:
            - tool: The Emme Tool to run
            - *args, **kwargs: The arguments & keyword arguments
                to be passed to the Emme Tool.
        '''
        self._activeTool = tool
        self._toolIsRunning = True
        #actually run the tool. no knowledge of the arguments is required.
        ret = self._activeTool(*args, **kwargs) 
        self._toolIsRunning = False
        self._activeTool = None
        self.completeTask()
        return ret
    
    def startProcess(self, numberOfSubtasks):
        '''
        Tells the Tracker to start up a new Task
        with a given number of Subtasks.
        '''
        if numberOfSubtasks <= 0:
            raise Exception("A new process requires at least one task!")
        
        self._subTasks = numberOfSubtasks
        self._completedSubtasks = 0
        self._processIsRunning = True            
    
    def completeSubtask(self):
        '''
        Call to indicate that a Subtask is complete.
        '''
        
        if not self._processIsRunning:
            return
        
        if self._completedSubtasks >= self._subTasks:
            self._processIsRunning =False
            self._subTasks = 0
            self._completedSubtasks = 0
            self.completeTask()
        else:
            self._completedSubtasks += 1
    
    @_m.method(return_type=_m.TupleType)
    def getProgress(self):
        '''
        Call inside a Tool's percent_completed method
        in order to report that Tool's progress.
        '''
        
        if self._toolIsRunning:
            tup = self._activeTool.percent_completed()
            if tup[2] == None: # Tool is returning the 'marquee' display option
                #Just return the current progress. The task will be completed by the other thread.
                self._toolIsRunning = False 
                return (0, 1000, self._progress)
            toolProg = (float(tup[2]) - tup[0]) / (tup[1] - tup[0])
            return (0,1000, self._progress + toolProg * self._taskIncr)
        elif self._processIsRunning:
            return (0, 1000, self._progress + self._taskIncr * float(self._completedSubtasks) / float(self._subTasks))
        else:
            return (0, 1000, self._progress)

class CSVReader():
    def __init__(self, filepath, append_blanks=True):
        self.filepath = filepath
        self.header = None
        self.append_blanks = append_blanks
    
    def open(self):
        self.__peek()
        self.__reader = open(self.filepath, 'r')
        self.header = self.__reader.readline().strip().split(',')
        
        #Clean up special characters
        for i in range(len(self.header)):
            self.header[i] = self.header[i].replace(' ', '_').replace("@", '').replace('+', '').replace('*', '')

        self.__lincount = 1 
    
    def __peek(self):
        count = 0
        with open(self.filepath, 'r') as reader:
            for l in reader:
                count += 1
        self.__count = count
    
    def __enter__(self):
        self.open()
        return self
    
    def close(self):
        self.__reader.close()
        del self.__reader
        self.header = None
        
    def __exit__(self, *args, **kwargs):
        self.close()
    
    def __len__(self):
        return self.__count
    
    def readline(self):
        try:
            cells = self.__reader.readline().strip().split(',')
            self.__lincount += 1
            if not self.append_blanks and len(cells) < len(self.header):
                raise IOError("Fewer records than header")
            
            while len(cells) < len(self.header) and self.append_blanks:
                cells.append('')
                
            atts = {}
            for i, column_label in enumerate(self.header):
                atts[column_label] = cells[i]
            return Record(atts)
            
        except Exception, e:
            raise IOError("Error reading line %s: %s" %(self.__lincount, e))
    
    def readlines(self):
        try:
            for line in self.__reader.readlines():
                cells = line.strip().split(',')
                self.__lincount += 1
                if not self.append_blanks and len(cells) < len(self.header):
                    raise IOError("Fewer records than header")
                
                while len(cells) < len(self.header) and self.append_blanks:
                    cells.append('')
                
                yield Record(self.header, cells)
        except Exception, e:
            raise IOError("Error reading line %s: %s" %(self.__lincount, e))

class Record():
    def __init__(self, header, cells):
        self.__dic = {}
        self.__hdr = header
        for i, head in enumerate(header):
            self.__dic[header[i]] = cells[i]
    
    def __getitem__(self, key):
        if type(key) == int:
            return self.__dic[self.__hdr[key]]
        elif type(key) == str:
            return self.__dic[key]
        else:
            raise Exception()
    
    def __setitem__(self, key, val):
        self.__hdr.append(key)
        self.__dic[key] = val
    
    def __len__(self):
        return len(self.__hdr)
    
    def __str__(self):
        s = self[0]
        for i in range(1, len(self)):
            s += "," + self[i]
        return s

class NullPointerException(Exception):
    pass

    
