'''
Contains a bunch of Python utility functions commonly used in TMG tools
and products. Set up as a non-runnable (e.g. private) Emme module so that
it can be distributed in the TMG toolbox

'''

import inro.modeller as _m
import math
import inro.emme.core.exception as _excep
from contextlib import contextmanager
import warnings as _warn
import sys as _sys
import traceback as _tb

class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Utilities",
                                description="Collection of private utilities",
                                branding_text="TMG")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()

def formatReverseStack():
    eType, eVal, eTb = _sys.exc_info()
    stackList = _tb.extract_tb(eTb)
    msg = "%s: %s\n\n\Stack trace below:" %(eVal.__class__.__name__, str(eVal))
    stackList.reverse()
    for file, line, func, text in stackList:
        msg += "\n  File '%s', line %s, in %s" %(file, line, func)
    return msg


# Truncates a string to a desired length
def truncateString(s, num):
    return s[:num]

_mtxNames = {'FULL' : 'mf',
             'DESTINATION' : 'md',
             'ORIGIN' : 'mo',
             'SCALAR' : 'ms'}

def initMatrix2(id=None, default=0, name="", description="", matrix_type='FULL'):
    
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

def getAvailableScenarioNumber():
    for i in range(0, _m.Modeller().emmebank.dimensions['scenarios']):
        if _m.Modeller().emmebank.scenario(i + 1) == None:
            return (i + 1)
    
    raise inro.emme.core.exception.CapacityError("No new scenarios are available: databank is full!")

@contextmanager
def tempMatrixMANAGER(description="[No description]"):
    #Code here is executed upon entry
    
    databank = _m.Modeller().emmebank
    id = databank.available_matrix_identifier('FULL')
    mtx = initMatrix(id, 0, id, 
                     description)
    
    if mtx == None:
        raise Exception("Could not create temporary matrix: %s" %description)
    
    s = "Created temporary matrix {0}: {1}.".format(id, description)
    print s
    _m.logbook_write(s)
    
    try:
        yield mtx
    finally:
        databank.delete_matrix(id)
        
        s = "Deleted matrix %s." %id
        print s
        _m.logbook_write(s)

def getExtents(network):
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

class FloatRange():
    
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
        return "[%s - %s]" %(self.min, self.max)

def buildSearchGridFromNetwork(network, gridSize=100, loadNodes=True, loadCentroids=False):
    extents = getExtents(network)
    grid = NodeSearchGrid(extents, gridSize)
    
    if loadNodes:
        for node in network.regular_nodes():
            grid.addNode(node)
    if loadCentroids:
        for centroid in network.centroids():
            grid.addNode(centroid)
            
    return grid

class NodeSearchGrid():
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

class Extents():
    
    def __init__(self, minX, minY, maxX, maxY):
        self.xrange = FloatRange(minX, maxX)
        self.yrange = FloatRange(minY, maxY)
    
    def __contains__(self, coord):
        return coord[0] in self.xrange and coord[1] in self.yrange
    
    def __str__(self):
        return "Extents(X=%s Y=%s)" %(self.xrange, self.yrange)

class ProgressTracker():
    
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
        if self._processIsRunning:
            self._processIsRunning =False
            self._subTasks = 0
            self._completedSubtasks = 0
        self._progress += self._taskIncr
    
    def runTool(self, tool, *args, **kwargs):
        self._activeTool = tool
        self._toolIsRunning = True
        #actually run the tool. no knowledge of the arguments is required.
        ret = self._activeTool(*args, **kwargs) 
        self._toolIsRunning = False
        self._activeTool = None
        self.completeTask()
        return ret
    
    def startProcess(self, numberOfSubtasks):
        self._subTasks = numberOfSubtasks
        self._completedSubtasks = 0
        self._processIsRunning = True            
    
    def completeSubtask(self):
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
    
    
