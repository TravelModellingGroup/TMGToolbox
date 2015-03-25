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
#---TODO LIST
'''
TODO LIST:

- Ensure that all query functions work even if the query geometry does not intersect the grid.
    In general, the _index functions should not care about the extents, and only the query(...)
    functions make the 'within grid' restriction. This standard is not consistently applied for
    all query/index pairings.

'''

from numpy import array
from numpy import min as nmin
from numpy import max as nmax

import inro.modeller as _m
from copy import copy
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')

class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Spatial Index",
                                description="For internal use only.",
                                branding_text="- TMG Toolbox")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()

class nrange():
    '''
    xrange-like object which also accepts 'negative' ranges.
    
    Example:
        >>>for i in nrange(3, 6): print i
        3
        4
        5
        >>>
        >>>for i in nrange(6, 3): print i
        6
        5
        4
        
    '''
    
    def __init__(self, start, stop):
        self.start = int(start)
        self.stop = int(stop)
        if start < stop: self._stepsize = 1
        else: self._stepsize = -1
        
    def __len__(self):
        return abs(self.stop - self.start)
    
    def __iter__(self):
        x = self.start
        while x != self.stop:
            yield x
            x += self._stepsize     

class frange():
    '''
    A convenience class for a continuous range of floating point values.
    Does not support iteration, but does support containment and overlap
    checking.
    '''
    
    __slots__ = ['min', 'max']
    
    def __init__(self, min, max):
        self.min = float(min)
        self.max = float(max)

    def __contains__(self, val):
        val = float(val)
        return (val >= self.min and val < self.max)
    
    def length(self):
        return abs(self.max - self.min)
    
    def overlaps(self, otherRange):
        return otherRange.min in self or otherRange.max in self or self.max in otherRange or self.min in otherRange
    
    def __str__(self):
        return "(%s - %s)" %(self.min, self.max)

class Rectangle():
    
    def __init__(self, minx, miny, maxx, maxy):
        self.rangeX = frange(minx, maxx)
        self.rangeY = frange(miny, maxy)
    
    def intersects(self, otherRectangle):
        props = set(dir(otherRectangle))
        if 'rangeX' in props and 'rangeY' in props:
            return self.rangeX.overlaps(otherRectangle.rangeX) and \
                    self.rangeY.overlaps(otherRectangle.rangeY)
        elif 'x' in props and 'y' in props:
            return otherRectangle.x in self.rangeX and otherRectangle.y in self.rangeY
        elif '__iter__' in props:
            x, y = otherRectangle
            return x in self.rangeX and y in self.rangeY
        else:
            raise TypeError("Object must be another rectangle or (x,y) point.")
    
    def __str__(self):
        return "%s %s" %(self.rangeX, self.rangeY)

def get_network_extents(net):
    '''
    For a given Emme Network, find the envelope (extents) of all of its elements.
    Includes link vertices as well as nodes.
    
    Args:
        -net: An Emme Network Object
    
    Returns:
        minx, miny, maxx, maxy tuple
    '''
    xs, ys = [], []
    for node in net.nodes():
        xs.append(node.x)
        ys.append(node.y)
    for link in net.links():
        for x, y in link.vertices:
            xs.append(x)
            ys.append(y)
    xa = array(xs)
    ya = array(ys)
    
    return nmin(xa) - 1.0, nmin(ya) - 1.0, nmax(xa) + 1.0, nmax(ya) + 1.0

#------------------------------------------------------------------------------        

class grid():
    def __init__(self, xSize, ySize):
        self._contents = []
        for col in xrange(xSize):
            cells = []
            
            for row in xrange(ySize): cells.append(set())
            
            self._contents.append(cells)
        self._maxCol = xSize
        self._maxRow = ySize
    
    def __contains__(self, key):
        col, row = key
        return row >= 1 and row <= self._maxRow and col >= 1 and col <= self._maxCol
    
    def __getitem__(self, key):
        col, row = key

        if row < 1 or row > self._maxRow:
            raise IndexError(row)
        if col < 1 or col > self._maxCol:
            raise IndexError(col)
        
        col = int(col) - 1
        row = int(row) - 1
        
        return self._contents[col][row]        

class GridIndex():
    '''
    Grid-based spatial index class. Geometry objects (and geometry-
    like objects such as Emme links) can be stored in this grid
    for faster searching. This is particularly useful when
    searching for intersecting features, to avoid having to test
    every single feature for intersection (which is a slow 
    operation).
    
    USAGE
    
    Insertion: Inserts an object into the grid index for later
    queries. Objects can only be inserted into locations which
    overlap the grid itself. Three low-level insertions are
    defined:
        insertxy: Inserts an object at a single point
        insertpline: Inserts an object over a polyline
        insertbox: Inserts an object within a box.
    Several convenience methods are also provided.
    
    Querying: Queries the grid index for objects. [More to come]
    
    Nearest: Only one nearest operation is supported. [More to come]
    '''
    
    __READ_ONLY_FLAG = False
    
    def __init__(self, extents, xSize= 100, ySize= 100, marginSize=0.0):
        '''
        Args:
            - extents: A tuple of minx, miny, maxx, maxy, OR
                a Rectangle object. Represents the spatial extents
                of the grid. Objects outside of the extents
                CANNOT be inserted into the grid (an error will
                be raised). Querying points outside of the grid,
                on the other hand, IS permitted.
            - xSize (=100): The number of columns in the grid.
            - ySize (=100): The number of rows in the grid.
            - marginSize (=0.0): A margin applied to the extents.
                For example, a margin of 1.0 sets the minimum x
                coordinate to minx - 1.0 and the maximum x
                coordinate to maxx + 1.0
        '''
        
        if hasattr(extents, '__iter__'):
            minx, miny, maxx, maxy = extents
            self.extents = Rectangle(minx - marginSize, miny - marginSize, \
                                     maxx + marginSize, maxy + marginSize)
        else:
            self.extents = extents
        
        xSize = int(xSize)
        ySize = int(ySize)
        self._deltaX = self.extents.rangeX.length() / xSize
        self._deltaY = self.extents.rangeY.length() / ySize
        self.minX = self.extents.rangeX.min
        self.maxX = self.extents.rangeX.max
        self.minY = self.extents.rangeY.min
        self.maxY = self.extents.rangeY.max
        
        self.maxCol = self._transform_x(self.maxX) - 1
        self.maxRow = self._transform_y(self.maxY) - 1
        
        self._grid = grid(xSize, ySize)
        self._addressbook = {}
        
        self.__READ_ONLY_FLAG = True
    
    def __setattr__(self, name, value):
        if self.__READ_ONLY_FLAG:
            raise NotImplementedError(name)
        else:
            self.__dict__[name] = value

    
    @staticmethod
    def __link2coords(link):
        inode = link.i_node
        jnode = link.j_node
        
        coordinates = copy(link.vertices)
        coordinates.insert(0, (inode.x, inode.y))
        coordinates.append((jnode.x, jnode.y))
        
        return coordinates
    
    @staticmethod
    def __line2coords(line):
        coords = []
        for node in line.itinerary():
            coords.append((node.x, node.y))
        return coords
    
    #------------------------------------------------------------------------------
    #---INDEXING
    
    def _check_x(self, x):
        if not x in self.extents.rangeX: 
            raise IndexError("X-coordinate '%s' is outside the bounds of the grid %s" %(x, self.extents.rangeX))
    
    def _check_y(self, y):
        if not y in self.extents.rangeY:
            raise IndexError("Y-coordinate '%s' is outside the bounds of the grid %s" %(y, self.extents.rangeY))
    
    def _transform_x(self, x):
        return int((x - self.minX) / self._deltaX) + 1
    
    def _transform_y(self, y):
        return int((y - self.minY) / self._deltaY) + 1
    
    def _index_point(self, x, y):
        return self._transform_x(x), self._transform_y(y)
    
    '''
    Each of the _index functions return an iterable of (col, row) tuples
    '''
    
    def _index_line_segment(self, x0, y0, x1, y1):
        
        if x1 < x0:
            x0, x1 = float(x1), float(x0)
            y0, y1 = float(y1), float(y0)
        else:
            x0, x1 = float(x0), float(x1)
            y0, y1 = float(y0), float(y1)
        
        col0, row0 = self._index_point(x0, y0)
        col1, row1 = self._index_point(x1, y1)
        
        col0 = max(1, col0)
        col1 = min(self.maxCol, col1)
        row0 = max(1, row0)
        row1 = min(self.maxRow, row1)
        
        #Initialize the return value with the two cells the end-points are in.
        retval = set([(col0, row0), (col1, row1)])
        
        if x0 == x1: #Vertical line
            for row in nrange(row0, row1):
                retval.add((col0, row))
        else:
            slope = (y1 - y0) / (x1 - x0)
            
            if slope < 0: delta = -1
            else: delta = 1  
            
            xIntercept = y0 - slope * x0
            prevRow = row0
            for col in nrange(col0, col1):
                columnBoundary = self._deltaX * col + self.minX
                yIntercept = slope * columnBoundary + xIntercept
                rowIntercept = self._transform_y(yIntercept)
                
                for row in nrange(prevRow, rowIntercept + delta):
                    retval.add((col, row))
                
                prevRow = rowIntercept
            for row in nrange(prevRow, row1):
                retval.add((col1, row))
            
        return retval
    
    def _index_box(self, x0, y0, x1, y1):
        x0 = float(min(x0, x1))
        y0 = float(min(y0, y1))
        x1 = float(max(x0, x1))
        y1 = float(max(y0, y1))
        
        col0, row0 = self._index_point(x0, y0)
        col1, row1 = self._index_point(x1, y1)
        
        col0 = max(col0, 1)
        col1 = min(col1, self.maxCol)
        row0 = max(row0, 1)
        row1 = min(row1, self.maxRow)
        
        retval = set()
        for col in xrange(col0, col1 + 1):
            for row in xrange(row0, row1 + 1):
                retval.add((col, row))
        return retval
    
    def _index_cirlce(self, center_x, center_y, radius):
        center_x, center_y, radius = float(center_x), float(center_y), float(radius)
        
        x0, x1 = center_x - radius, center_x + radius
        
        col0 = max(1, self._transform_x(x0))
        col1 = min(self._transform_x(x1), self.maxCol)
        
        retval = set()
        
        if col0 == col1:
            y0, y1 = center_y - radius, center_y + radius
            row0, row1 = self._transform_y(y0), self._transform_y(y1)
            
            for row in xrange(row0, row1 + 1):
                retval.add((col0, row))
                
            return retval
            
        rad2 = radius ** 2
        
        for col in xrange(col0, col1):
            columnBoundary = self._deltaX * col + self.minX
            # y = center_y +/- sqrt(radius^2 - (x - center_x)^2 )
            root = (rad2 - (columnBoundary - center_x)**2) ** 0.5
            
            upper_yIntercept = center_y + root
            lower_yIntercept = center_y - root
            
            row0 = max(1, self._transform_y(lower_yIntercept))
            row1 = min(self.maxRow, self._transform_y(upper_yIntercept) )
            
            for row in xrange(row0, row1 + 1):
                retval.add((col, row))
                retval.add((col + 1, row))
        
        return retval
    
    #------------------------------------------------------------------------------        
    #---INSERTION
    
    def insertxy(self, obj, x, y):
        '''
        Low-level insertion. Insert ANY hashable object using given coordinates.
        
        Args:
            - obj: The object to insert. Must be hashable (e.g. no lists)
            - x: The x-coordinate into where the object will be inserted
            - y: The y-coordinate into where the object will be inserted
        '''
        
        self._check_x(x)
        self._check_y(y)
        
        col, row = self._index_point(x, y)
        self._grid[col, row].add(obj)
        self._addressbook[obj] = [(col, row)]
        
    
    def insertpline(self, obj, coordinates):
        '''
        Low-level insertion. Insert ANY hashable object using given coordinates.
        
        Args:
            - obj: The object to insert. Must be hashable (e.g. no lists)
            - coordinates: List of (x,y) tuples corresponding to the vertices of the line
        '''
        
        for p0, p1 in _util.iterpairs(coordinates):
            x0, y0 = p0
            x1, y1 = p1
            
            self._check_x(x0)
            self._check_x(x1)
            self._check_y(y0)
            self._check_y(y1)
            
            addresses = self._index_line_segment(x0, y0, x1, y1)
            for col, row in addresses:
                self._grid[col, row].add(obj)
            self._addressbook[obj] = addresses
    
    def insertbox(self, obj, minx, miny, maxx, maxy):
        '''
        Low-level insertion. Insert ANY hashable object using a given bounding box.
        
        Args:
            - obj: The object to insert. Must be hashable (e.g. no lists)
            - minx: The minimum x-coordinate of the bounding box
            - miny: The minimum y-coordinate of the bounding box
            - maxx: The maximum x-coordinate of the bounding box
            - maxy: The maximum y-coordinate of the bounding box
        '''
        
        self._check_x(minx)
        self._check_x(maxx)
        self._check_y(miny)
        self._check_y(maxy)
        
        addresses = self._index_box(minx, miny, maxx, maxy)
        for col, row in addresses:
            self._grid[col, row].add(obj)
        self._addressbook[obj] = addresses
    
    def insertPoint(self, pointOrNode):
        '''
        Inserts a Shapely Point or Emme Node object.
        '''
        
        self.insertxy(pointOrNode, pointOrNode.x, pointOrNode.y)
    
    def insertLineString(self, linestring):
        '''
        Inserts a Shapely LineString object.
        '''
        
        self.insertpline(linestring, linestring.coords)
    
    def insertLink(self, link):
        '''
        Inserts an Emme Link object
        '''
        
        self.insertpline(link, self.__link2coords(link))
    
    def insertTransitLine(self, line):
        '''
        Inserts an Emme Transit Line object
        '''
        
        self.insertpline(line, self.__line2coords(line))
    
    def insertTransitSegment(self, segment):
        '''
        Inserts an Emme Transit Segment object
        '''
        
        self.insertpline(segment, self.__link2coords(segment.link))
    
    def insertPolygon(self, polygon):
        '''
        Inserts a Shapely Polygon object (or any object with a 'bounds'
        property).
        '''
        
        self.insertbox(polygon, *polygon.bounds)
    
    #------------------------------------------------------------------------------
    #---REMOVAL
    
    def remove(self, obj):
        '''
        Removes an object from the spatial index. The object must have been
        already inserted to the index, otherwise a KeyError will be raised.
        '''
        if not obj in self._addressbook:
            raise KeyError(str(obj))
        
        for col, row in self._addressbook[obj]:
            self._grid[col, row].remove(obj)
            
        self._addressbook.pop(obj)
    
    #------------------------------------------------------------------------------
    #---QUERY
    
    def queryxy(self, x, y):
        '''
        Queries a single point. The point does not have to overlap the grid.
        
        Args:
            - x: The x-coordinate
            - y: The y-coordinate
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        address = self._index_point(x, y)
        if address in self._grid:
            return set(self._grid[address]) #Return a copy of the set
        return set()
    
    def querypline(self, coordinates):
        '''
        Queries a polyline / linestring. The line's points do not need to overlap
        the grid.
        
        Args:
            - coordinates: A list of (x,y) tuples.
            
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        retval = set()
        
        for p0, p1 in _util.iterpairs(coordinates):
            x0, y0 = p0
            x1, y1 = p1
            for address in self._index_line_segment(x0, y0, x1, y1):
                if address in self._grid:
                    retval |= self._grid[address]
        
        return retval
    
    def querybox(self, minx, miny, maxx, maxy):
        '''
        Queries a rectangular box. The box does not need to overlap the grid.
        
        Args:
            minx: The minimum x coordinate
            miny: The minimum y coordinate
            maxx: The maximum x coordinate
            maxy: The maximum y coordinate
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        retval = set()
        for address in self._index_box(minx, miny, maxx, maxy):
            if address in self._grid:
                retval |= self._grid[address]
        
        '''
        col0 = max(1, self._transform_x(minx))
        col1 = min(self.maxCol, self._transform_x(maxx))
        row0 = max(1, self._transform_y(miny))
        row1 = min(self.maxRow, self._transform_y(maxy))
        
        retval = set()
        for col in xrange(col0, col1):
            for row in xrange(row0, row1):
                retval |= self._grid[col, row]
        '''
        
        return retval
    
    def queryPoint(self, pointOrNode):
        '''
        Queries a single point. The point does not need to overlap the grid.
        
        Args:
            - pointOrNode: A Shapely Point or Emme Node object,
                    with x and y properties.
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        x = pointOrNode.x
        y = pointOrNode.y
        
        return self.queryxy(x, y)
    
    def queryLineString(self, linestring):
        '''
        Queries a polyline / linestring. The line does not need to overlap the grid.
        
        Args:
            - linestring: A Shapely LineString object
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        coordinates = linestring.coords
        
        return self.querypline(coordinates)
    
    def queryLink(self, link):
        '''
        Queries an Emme Link object. The link does not need to overlap the grid.
        
        Args:
            - link: An Emme Link object
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        coordinates = self.__link2coords(link)
        
        return self.querypline(coordinates)
    
    def queryTransitLine(self, line):
        '''
        Queries an Emme Transit Line object. The line does not need to overlap the 
        grid.
        
        Args:
            - line: An Emme Transit Line object
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        return self.querypline(self.__line2coords(line))
    
    def queryTransitSegment(self, segment):
        '''
        Queries an Emme Transit Segment object. The segment does not need to overlap the 
        grid.
        
        Args:
            - segment: An Emme Transit Segment object
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        return self.querypline(self.__link2coords(segment.link))
    
    def queryPolygon(self, polygon):
        '''
        Queries a rectangular box.
        
        Args:
            polygon: A Shapely Geometry object (anything which
                implements the 'bounds' property).
            
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        minx, miny, maxx, maxy = polygon.bounds
        return self.querybox(minx, miny, maxx, maxy)
    
    def queryRectangle(self, rectangle):
        '''
        Queries a rectangular box. The rectangle does not need to overlap the grid.
        
        Args:
            rectangle: A Rectangle object (in this module).
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        minx = rectangle.rangeX.min
        maxx = rectangle.rangeX.max
        miny = rectangle.rangeY.min
        maxy = rectangle.rangeY.max
        
        return self.querybox(minx, miny, maxx, maxy)
    
    def queryCircle(self, x, y, radius):
        '''
        Queries a circle. The circle does not need to overlap the grid.
        
        Args:
            - x: The x-coordinate of the circle's center
            - y: The y-coordinate of the circle's center
            - radius: The radius of the circle
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        retval = set()
        
        for address in self._index_cirlce(x, y, radius):
            if address in self._grid:
                retval |= self._grid[address]
        return retval
    
    #------------------------------------------------------------------------------
    #---NEAREST
    
    def nearestToPoint(self, x, y):
        '''
        A special query to find the nearest element to a given point.
        The grid is queried in rings around the point, stopping once
        the return set is non-empty, or the grid is fully searched.
        
        Args:
            -x, y: the coordinates of interest. This point MUST overlap
                the grid.
        
        Returns:
            A set of objects which may be the nearest to the point of
            interest. Another operation is required to determine
            which objects are actually nearest.
        '''
        self._check_x(x)
        self._check_y(y)
        
        centerCol, centerRow = self._index_point(x, y)
        if len(self._grid[centerCol, centerRow]) > 0:
            return copy(self._grid[centerCol, centerRow])
        
        col0 = max(1, centerCol - 1)
        col1 = min(self.maxCol, centerCol + 1)
        row0 = max(1, centerRow - 1)
        row1 = min(self.maxRow, centerRow + 1)
        
        retval = set()
        while col0 > 1 and col1 < self.maxCol and row0 > 1 and row1 < self.maxRow:
            
            for col in nrange(col0, col1): retval |= self._grid[col, row1]
            for row in nrange(row1, row0): retval |= self._grid[col1, row]
            for col in nrange(col1, col0): retval |= self._grid[col, row0]
            for row in nrange(row0, row1): retval |= self._grid[col0, row]
            
            if len(retval) > 0: return retval
            col0 = max(1, col0 -1)
            col1 = min(self.maxCol, col1 + 1)
            row0 = max(1, row0 -1)
            row1 = min(self.maxRow, row1 + 1)
        
        for col in nrange(1, self.maxCol): retval |= self._grid[col, self.maxRow]
        for row in nrange(self.maxRow, 1): retval |= self._grid[self.maxCol, row]
        for col in nrange(self.maxCol, 1): retval |= self._grid[col, 1]
        for row in nrange(1, self.maxRow): retval |= self._grid[1, row]
        
        return retval
