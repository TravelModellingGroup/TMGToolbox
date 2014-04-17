'''
    Copyright 2014 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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

class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Utilities",
                                description="Collection of private utilities",
                                branding_text="TMG")
        
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

#@deprecated: Just use Python's builtin functionality instead
def truncateString(s, num):
    '''    
    Truncates string 's' to desired length 'num'.
    '''
    return s[:num]

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

def initMatrix2(id=None, default=0, name="", description="", matrix_type='FULL'):
    '''
    Utility function for creation and initialization of matrices.
    
    Args:
        - id (=None): String id (e.g. 'mf2') If specified, this function will 
            initialize the given matrix (if it exists) or create it (if it 
            does not). If left blank, an available matrix will be found.
        - default (=0): The numerical value to initialize the matrix to (i.e.,
            its default value).
        - name (=""): The 6-character name of the matrix. Will be truncated
            if longer.
        - description (=""): The 40-character descriptor for the matrix. Will
            be truncated if longer.
        - matrix_type (='FULL'): One of 'SCALAR', 'ORIGIN', 'DESTINATION',
            or 'FULL'. If an ID is specified, the matrix type will be
            inferred from the ID's prefix.
    
    Returns: The Emme Matrix object created or initialized.
    '''
    
    databank = _m.Modeller().emmebank
    
    if id == None:
        #Get an available matrix
        id = databank.available_matrix_identifier(matrix_type)
    elif type(id) == int:
        #If the matrix id is for some reason given as an integer
        try:
            id = "%s%s" %(_mtxNames[matrix_type],id)
        except KeyError, ke:
            raise KeyError("Matrix type '%s' is not a valid matrix type." %matrix_type)
    
    mtx = databank.matrix(id)
    
    if mtx == None:
        #Matrix does not exist, so create it.
        mtx = databank.create_matrix(id, default_value=default)
        mtx.name = name[:6] 
        mtx.description = description[:40] 
        _m.logbook_write("Created new matrix %s: '%s' (%s)." %(id, mtx.name, mtx.description))
    else:
        #Matrix exists, so rename it, and re-initialize it.
        if mtx.read_only:
                raise _excep.ProtectionError("Cannot modify matrix '%s' as it is protected against modifications." %id)
        mtx.initialize(value=default)
        mtx.name = name[:6]
        mtx.description = description[:40]
        _m.logbook_write("Initialized existing matrix %s: '%s' (%s)." %(id, mtx.name, mtx.description))
    
    return mtx        

#-------------------------------------------------------------------------------------------

#@deprecated: Use initMatrix2 instead
# Initialize a matrix safely, by checking if it exists or not
def initMatrix(id, default, name, descr):
    try:
        mtx = _m.Modeller().emmebank.matrix(id)
        
        if mtx == None:
            #Matrix does not exist, so create it.
            mtx = _m.Modeller().emmebank.create_matrix(id, default_value=default)
            mtx.name = truncateString(name, 6)
            mtx.description = truncateString(descr, 40)
        else:
            #Matrix exists, so rename it, and re-initialize it.
            if mtx.read_only:
                raise _excep.ProtectionError("Cannot modify matrix '%s' as it is protected against modifications." %id)
            mtx.initialize(value=default)
            mtx.name = truncateString(name, 6)
            mtx.description = truncateString(descr, 40)
        
        return mtx
    except Exception, e:
        raise e
    
    return None

#-------------------------------------------------------------------------------------------

def getAvailableScenarioNumber():
    '''
    Returns: The number of an available scenario. Raises an exception
    if the databank is full.
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
def tempExtraAttributeMANAGER(scenario, domain, default= 0.0, description= None):
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
        
    Yields: The Extra Attribute object created.
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
    
    try:
        yield tempAttribute
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
    
    databank = _m.Modeller().emmebank
    id = databank.available_matrix_identifier(matrix_type)
    mtx = initMatrix(id, default, id, 
                     description)
    
    if mtx == None:
        raise Exception("Could not create temporary matrix: %s" %description)
    
    s = "Created temporary matrix {0}: {1}.".format(id, description)
    _m.logbook_write(s)
    
    try:
        yield mtx
    finally:
        databank.delete_matrix(id)
        
        s = "Deleted matrix %s." %id
        _m.logbook_write(s)

#-------------------------------------------------------------------------------------------

def fastLoadTransitSegmentAttributes(scenario, list_of_attribtues):
    '''
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
    '''
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

def getEmmeVersion():
    '''
    Gets the version of Emme that is currently running, as a string. For example,
    'Emme 4.0.8', or 'Emme 4.1.0 32-bit'.
    '''
    emmeProcess = _sp.Popen(['Emme', '-V'], stdout= _sp.PIPE, stderr= _sp.PIPE)
    output = emmeProcess.communicate()[0]
    return output.split(',')[0]

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

def buildSearchGridFromNetwork(network, gridSize=100, loadNodes=True, loadCentroids=False):
    '''
    Creates a NodeSearchGrid object from the network.
    
    Args:
        - network: An Emme Network object.
        - gridSize (=100): The number of rows and columns in the grid (e.g., 100x100 by default)
        - loadNodes (=True): Boolean flag whether to load the network's regular nodes into the grid.
        - loadCentroids (=False): Boolean flag whether to load the network's centroids into the grid.
    '''
    extents = getExtents(network)
    grid = NodeSearchGrid(extents, gridSize)
    
    if loadNodes:
        for node in network.regular_nodes():
            grid.addNode(node)
    if loadCentroids:
        for centroid in network.centroids():
            grid.addNode(centroid)
            
    return grid

#-------------------------------------------------------------------------------------------

class NodeSearchGrid():
    
    '''
    A simple spatial index for searching for nodes/points.
    '''
    
    def __init__(self, extents, gridSize=100):
        self.extents = extents
        #(minX, minY, maxX, maxY)
        self._xInterval = (self.extents.xrange.length()) / float(gridSize)
        self._yInterval = (self.extents.yrange.length()) / float(gridSize)
        self.gridSize = gridSize
        
        self._contents = []
        for i in range(0, gridSize):
            a = []
            for j in range(0, gridSize):
                a.append(set())
            self._contents.append(a)
    
    def addNode(self, node):
        if not (node.x, node.y) in self.extents:
            _warn.warn("Cannot add node %s to the grid as its coordinates are outside of the extents" %node)
            return
        
        self._contents[self._transformX(node.x)][self._transformY(node.y)].add(node)
    
    def _transformX(self, x):
        return int((x - self.extents.xrange.min) / self._xInterval)
    
    def _transformY(self, y):
        return int((y - self.extents.yrange.min) / self._yInterval)
    
    def getNodesInBox(self, box_tuple_or_geometry):
        '''
        Accepts a tuple in (minx, miny, maxx, maxy) format, or a Geometry
        object.
        '''
        if type(box_tuple_or_geometry) == type(()):
            minx, miny, maxx, maxy = box_tuple_or_geometry
        elif 'bounds' in dir(box_tuple_or_geometry):
            minx, miny, maxx, maxy = box_tuple_or_geometry.bounds
        else:
            raise TypeError("Box must be a tuple of (minx, miny, maxx, maxy) or a have a 'bounds' property which gives it.")
        
        minxi = self._transformX(minx)
        minyi = self._transformY(miny)
        maxxi = self._transformX(maxx)
        maxyi = self._transformY(maxy)
        
        xRange = range(minxi, maxxi + 1)
        yRange = range(minyi, maxyi + 1)
        
        retval = []
        for i in xRange:
            row = self._contents[i]
            for j in yRange:
                retval.extend(row[j])
        return retval
        
    def getNearestNode(self, x, y, searchRadius=float('inf')):
        if not (x, y) in self.extents:
            return None
        
        xIndex = self._transformX(x)
        yIndex = self._transformY(y)
        
        xSearcgRange = range(max(0, xIndex - 1), min(self.gridSize, xIndex + 2))
        ySearchRange = range(max(0, yIndex - 1), min(self.gridSize, yIndex + 2))
        
        minDist = searchRadius
        nearestNode = None
        for i in xSearcgRange:
            for j in ySearchRange:
                for node in self._contents[i][j]:
                    dist = abs(node.x - x) + abs(node.y - y)
                    if dist < minDist:
                        nearestNode = node
                        minDist = dist
        
        return nearestNode
    
    def getNearestNodes(self, x, y, searchRadius=float('inf'), maxNodes=100):
        if not (x, y) in self.extents:
            return None
        
        xIndex = self._transformX(x)
        yIndex = self._transformY(y)
        
        xSearcgRange = range(max(0, xIndex - 1), min(self.gridSize, xIndex + 2))
        ySearchRange = range(max(0, yIndex - 1), min(self.gridSize, yIndex + 2))
        
        searchRadius
        nearestNodes = []
        for i in xSearcgRange:
            for j in ySearchRange:
                for node in self._contents[i][j]:
                    dist = abs(node.x - x) + abs(node.y - y)
                    if dist < searchRadius:
                        nearestNodes.append((dist, node))
        nearestNodes.sort()
        while len(nearestNodes) > maxNodes:
            nearestNodes.pop()
        
        return [tuple[1] for tuple in nearestNodes]

#-------------------------------------------------------------------------------------------

class Extents():
    
    def __init__(self, minX, minY, maxX, maxY):
        self.xrange = FloatRange(minX, maxX)
        self.yrange = FloatRange(minY, maxY)
    
    def __contains__(self, coord):
        return coord[0] in self.xrange and coord[1] in self.yrange
    
    def __str__(self):
        return "Extents(X=%s Y=%s)" %(self.xrange, self.yrange)

#-------------------------------------------------------------------------------------------

class ProgressTracker():
    
    '''
    Convenience class for tracking and reporting progress. Also
    captures the progress from other Emme Tools (such as those
    provided by INRO), and combines with a total progress.
    
    Handles progress at two levels: Tasks and Subtasks. Running
    an Emme Tool counts as a Task. The total number of tasks 
    must be known at initialization.
    '''
    
    def __init__(self, numberOfTasks):
        self._taskIncr = 1000.0 / numberOfTasks #floating point number
        self.reset()
        self._errorTools = set()
    
    def reset(self):
        self._subTasks = 0
        self._completedSubtasks = 0
        self._progress = 0.0 #floating point number
        self._toolIsRunning = False
        self._processIsRunning = False
        self._activeTool = None
    
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

    
