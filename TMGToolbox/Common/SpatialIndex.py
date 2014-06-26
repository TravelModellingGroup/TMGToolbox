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
import inro.modeller as _m
from copy import copy
_MODELLER = _m.Modeller()
_util = _MODELLER.module('TMG2.Common.Utilities')

class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Spatial Index",
                                description="For internal use only.",
                                branding_text="TMG")
        
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
    
    Usage:
        
    '''
    
    __READ_ONLY_FLAG = False
    
    def __init__(self, xSize, ySize, extents):
        props = set(dir(extents))
        
        if '__iter__' in props:
            minx, miny, maxx, maxy = extents
            self.extents = Rectangle(minx, miny, maxx, maxy)
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
    
    #------------------------------------------------------------------------------
    #---INDEXING
    
    def _check_x(self, x):
        if not x in self.extents.rangeX: 
            raise IndexError("X-coordinate '%s' is outside the bounds of the grid." %x)
    
    def _check_y(self, y):
        if not y in self.extents.rangeY:
            raise IndexError("Y-coordinate '%s' is outside the bounds of the grid." %y)
    
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
                columnBoundary = self._deltaX * col
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
            columnBoundary = self._deltaX * col
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
            
            for col, row in self._index_line_segment(x0, y0, x1, y1):
                self._grid[col, row].add(obj)
    
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
        
        for col, row in self._index_box(minx, miny, maxx, maxy):
            self._grid[col, row].add(obj)    
    
    def insetPoint(self, pointOrNode):
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
    
    def insertPolygon(self, polygon):
        '''
        Inserts a Shapely Polygon object (or any object with a 'bounds'
        property).
        '''
        
        self.insertbox(polygon, *polygon.bounds)
    
    #------------------------------------------------------------------------------
    #---QUERY
    
    def queryxy(self, x, y):
        '''
        Queries a single point.
        
        Args:
            - x: The x-coordinate
            - y: The y-coordinate
        
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        self._check_x(x)
        self._check_y(y)
        
        col, row = self._index_point(x, y)
        return set(self._grid[col, row]) #Return a copy of the set
    
    def querypline(self, coordinates):
        '''
        Queries a polyline / linestring
        
        Args:
            - coordinates: A list of (x,y) tuples.
            
        All 'query' functions check the grid for the contents of all of the cells
        intersected by the given geometry. THERE IS NO GURANATEE that the returned
        contents intersect the given geometry, merely that they intersect the CELLS
        that intersect the given geometry. Tests for containment, intersection,
        overlap, etc. (i.e. DE-9IM relations) must be done separately.
        '''
        
        retval = set()
        
        x0, y0 = coordinates[0]
        self._check_x(x0)
        self._check_y(y0)
        
        for x1, y1 in coordinates[1:]:
            self._check_x(x1)
            self._check_y(y1)
            
            for col, row in self._index_line_segment(x0, y0, x1, y1):
                retval |= self._grid[col, row]
        
        return retval
    
    def querybox(self, minx, miny, maxx, maxy):
        '''
        Queries a rectangular box.
        
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
        
        col0 = max(1, self._transform_x(minx))
        col1 = min(self.maxCol, self._transform_x(maxx))
        row0 = max(1, self._transform_y(miny))
        row1 = min(self.maxRow, self._transform_y(maxy))
        
        retval = set()
        for col in xrange(col0, col1):
            for row in xrange(row0, row1):
                retval |= self._grid[col, row]
        return retval
    
    def queryPoint(self, pointOrNode):
        '''
        Queries a single point.
        
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
        Queries a polyline / linestring
        
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
        Queries a polyline / linestring
        
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
        Queries a rectangular box.
        
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
        Queries a circle.
        
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
        for col, row in self._index_cirlce(x, y, radius):
            retval |= self._grid[col, row]
        return retval
    
    #------------------------------------------------------------------------------
    #---NEAREST
    
    def nearestToPoint(self, x, y):
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
