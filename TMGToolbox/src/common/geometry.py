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

from shapely import geometry as _geo
from shapely.geometry import mapping, shape
import fiona
from shutil import copyfile
from os import path as _path
import warnings as _warn
import inro.modeller as _m
import six

_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')

##################################################################################################################

class Face(_m.Tool()):

    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Geometry",
                                description="Collection of private tools for performing geometric \
                                        operations from shapefiles.",
                                branding_text="- TMG Toolbox")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()
    
##################################################################################################################
#---Wrapped subclasses of shapely geometries which can have attached attributes

class _attachable():
    
    def __getitem__(self, attributeName):
        return self._atts[attributeName]
    
    def __setitem__(self, attributeName, value):
        self._atts[attributeName] = value
    
    def setAttributes(self, map):
        self._atts = map
        
    def getAttributes(self):
        return self._atts
    
    def __contains__(self, key):
        return key in self._atts
    
class Point(_geo.Point, _attachable):
    def __init__(self, *args):
        root = super(Point, self)
        self._atts = {}
        root.__init__(args)

class LineString(_geo.LineString, _attachable):
    def __init__(self, coordinates=None):
        root = super(LineString, self)
        self._atts = {}
        root.__init__(coordinates)

class Polygon(_geo.Polygon, _attachable):
    def __init__(self, shell=None, holes=None):
        root = super(Polygon, self)
        self._atts = {}
        root.__init__(shell, holes)

class MultiPoint(_geo.MultiPoint, _attachable):
    def __init__(self, points=None):
        root = super(MultiPoint, self)
        self._atts = {}
        root.__init__(points)

class MultiLineString(_geo.MultiLineString, _attachable):
    def __init__(self, lines=None):
        root = super(MultiLineString, self)
        self._atts = {}
        root.__init__(lines)

class MultiPolygon(_geo.MultiPolygon, _attachable):
    def __init__(self, polygons=None, context_type='polygons'):
        root = super(MultiPolygon, self)
        self._atts = {}
        root.__init__(polygons, context_type)

class GeometryCollection(_geo.GeometryCollection, _attachable):
    def __init__(self):
        root = super(GeometryCollection, self)
        self._atts = {}
        root.__init__()

##################################################################################################################
#---Methods for converting Emme data types to geometry

def nodeToShape(node):
    p = Point(node.x, node.y)
    p['number'] = node.number
    p['id'] = node.id
    
    for att in node.network.attributes('NODE'):
        p[att] = node[att]
    return p

def linkToShape(link):
    coords = []
    coords.append((link.i_node.x, link.i_node.y))
    for vertex in link.vertices: coords.append(vertex)
    coords.append((link.j_node.x, link.j_node.y))
    ls = LineString(coords)
    
    for att in link.network.attributes('LINK'):
        if att == 'vertices': continue
        ls[att] = link[att]
    
    return ls

def turnToShape(turn):
    raise NotImplementedError("Turns are not yet implemented.")

def transitLineToShape(line):
    inode = line.segment(0).i_node
    coordinates = [(inode.x, inode.y)]
    
    for segment in line.segments(False):
        coordinates.extend(segment.link.vertices)
        jnode = segment.j_node
        coordinates.append((jnode.x, jnode.y))
    
    ls = LineString(coordinates)
    
    for att in line.network.attributes('TRANSIT_LINE'):
        ls[att] = line[att]
    
    return ls

#---Static methods for casting shapely geometries to attachable geometries
def castAsAttachable(geom):
    type = geom.type
    type_lower = type.lower()
    if type_lower == 'point':
        vertices = list(geom.coords)
        return Point(vertices[0][0], vertices[0][1])
    elif type_lower == 'linestring':
        return LineString(list(geom.coords))
    elif type_lower == 'polygon':
        exterior = list(geom.exterior.coords)
        interiors = []
        for interior in geom.interiors:
            interiors.append(interior.coords)
        return Polygon(exterior, interiors)
    else:
        raise TypeError("Geometry type '%s' not recognized" %type)

#---Other static methods
def crossProduct(coordA1, coordA2, coordB1, coordB2):
    # A and B, as vectors
    # AxB = (A.x * B.y) - (A.y * B.x)
    return (coordA2[0] - coordA1[0])*(coordB2[1] - coordB1[1]) - \
        (coordA2[1] - coordA1[1])*(coordB2[0] - coordB1[0])

def dotProduct(coordA1, coordA2, coordB1, coordB2):
    return ((coordA2[0] - coordA1[0]) * (coordB2[0] - coordB1[0])) + \
        ((coordA2[1] - coordA1[1]) * (coordB2[1] - coordB1[1]))
        
def checkSegmentIntersection(coordA1, coordA2, coordB1, coordB2):
    deltaX1 = coordA2[0] - coordA1[0]
    deltaY1 = coordA2[1] - coordA1[1]
    deltaX2 = coordB2[0] - coordB1[0]
    deltaY2 = coordB2[1] - coordB1[1]
    
    s = None
    t = None
    try:           
        s = (-deltaY1 * (coordA1[0] - coordB1[0]) + deltaX1 * (coordA1[1] - coordB1[1])) / (-deltaX2 * deltaY1 + deltaX1 * deltaY2)
        t = ( deltaX2 * (coordA1[1] - coordB1[1]) - deltaY2 * (coordA1[0] - coordB1[0])) / (-deltaX2 * deltaY1 + deltaX1 * deltaY2)
    except ZeroDivisionError:
        return False
        
    return (s >= 0 and s <= 1 and t >= 0 and t <= 1)


##################################################################################################################
#---Field class for storing data about DBF fields

class StringField():    
    def __init__(self, name, length=50, decimals=0, default=""):
        self.name = str(name)
        self.length = length
        self.default = default
        self.type = 'STR'
        
    def addToDf(self, df):
        df.schema[self.name] = ("str:%d" %self.length)
    
    def format(self, value):
        return str(value)[:self.length]
    
    def __str__(self):
        return "%s (STR)" %self.name

class FloatField():
    def __init__(self, name, length=12, decimals=4, default=0.0):
        if length < 3:
            raise IOError("DBF field definition failed: Field length must be at least 3.")
        if decimals > (length - 2): #remove >= with an > sign only
            raise IOError("DBF field definition failed: Cannot assign more than {0} decimals for a field length of {1} of decimals {2} ".format((length - 2), length, decimals))       
        self.name =str(name)
        self.max = float(pow(10, length - decimals - 1) - 1)
        self.min = - float(pow(10, length - decimals - 1) - 2) # This is untested.
        self.length = length
        self.decimals = decimals
        self.default = default        
        self.type = 'FLOAT'
        
    def addToDf(self, df):
        df.schema[self.name] = ("float:%s.%s" %(str(self.length), str(self.decimals)))
    
    def format(self, value):
        f = float(value)
        if f < self.min: return self.min
        elif f > self.max: return self.max
        return f
    
    def __str__(self):
        return "%s (FLOAT)" %self.name

class IntField():
    
    def _getMaxInt(self, length):
        max = 0
        for i in range(0, length):
            max += 9 * pow(10, i)
            if max > 2147483647:
                return 2147483647
        return max
    
    def __init__(self, name, length=8, decimals=0, default=0):
        self.max = self._getMaxInt(length)
        self.min = - (self.max - 1)
        self.length = length
        self.default = default
        self.name = str(name)
        self.type = 'INT'
    
    def addToDf(self, df):
        df.schema[self.name] = "int:%d" %self.length
    
    def format(self, value):
        i = int(value)
        if i < self.min: return self.min
        elif i > self.max: return self.max
        return i
    
    def __str__(self):
        return "%s (INT)" %self.name

class BoolField():
    def __init__(self, name, length=1, decimals=0, default=False):
        self.name = str(name)
        self.default = default
        self.type = 'BOOL'
    
    def addToDf(self, df):
        df.schema[self.name] = "int:1"
    
    def format(self, value):
        return int(bool(value))
    
    def __str__(self):
        return "%s (BOOL)" %self.name

#---Shapefile class for I/O

class Shapely2ESRI():
    _POINT = 1
    _ARC = 3
    _POLYGON = 5
    _MULTIPOLYGON = 6
    #From: https://github.com/sdteffen/shapelib/blob/1ef45dfea06fdd3ebfc67965220f4c17cbf25062/shapefil.h#L302
    convert_index_to_geometry = {
        0 : "NULL",
        _POINT : "POINT",
        _ARC : "ARC",
        _POLYGON : "POLYGON",
        _MULTIPOLYGON : "MULTIPOLYGON",
        8 : "MULTIPOINT",
        11 : "POINTZ",
        13 : "ARCZ",
        15 : "POLYGONZ",
        18 : "MULTIPOINTZ",
        21 : "POINTM",
        23 : "ARCM",
        25 : "POLYGONM",
        28 : "MULTIPOINTM",
        31 : "MULTIPATCH"
    }
      
    convert_geometry_to_index = dict((v,k) for k, v in six.iteritems(convert_index_to_geometry))
         
    def __init__(self, filepath, mode='read', geometryType=0, projectionFile= None):
        if len(mode) <= 0:
            raise ValueException("Mode can not be empty")
        self._shape_file_path = filepath
        self._records = {}
        self._fields = {}
        self._properties = {}
        if mode[0].lower() == 'w':
            self._sf = None
            self._canread = False
            self._canwrite = True
            self._size = 0
        else:
            if not (mode[0].lower() == 'r'):
                _warn.warn("Mode '%s' not recognized. Defaulting to read mode" %mode)
            self._canread = True
            self._canwrite = False
                  
    def open(self):
        '''
        Opens a shapefile. Not required if using inside a 'with' statement
        '''
        if self._canread:
            self._load()
        else:
            self._create()
        
    def _create(self):
        pass
    
    def _load_type(self, item):
        type = item['geometry']['type'].upper()
        if type == 'LINESTRING':
            type = "ARC"
        return self.convert_geometry_to_index[type]
    
    def _load_properties(self, item):
        properties = item['properties']
        
        return None

    def get_properties_by_fid(self, fid):
        return self._properties[fid]

    def get_properties_by_geomerty(self, geom):
        for fid, geometry in self._records.items():
            if geometry is geom:
                return self._properties[fid]
        return None
       
    def _load(self):
        self._sf = fiona.open(self._shape_file_path, 'r')
        fid = 0
        for record in self._sf.values():
            if fid == 0:
                self._geometryType = self._load_type(record)
            data = record['geometry']['coordinates']
            dataType = self._load_type(record)
            if dataType == Shapely2ESRI._POLYGON:
                geom = Polygon(data[0], data[1:(len(data) - 1)])
            elif dataType == Shapely2ESRI._MULTIPOLYGON:
                geom = MultiPolygon(shape(record['geometry']))
            elif dataType == Shapely2ESRI._POINT:
                geom = Point(data)
            elif dataType == Shapely2ESRI._ARC:
                geom = LineString(data)
            else:
                raise NotImplementedError("Unknown data type: " + str(dataType))
            self._properties[fid] = record['properties']           
            self._records[fid] = geom
            fid += 1
        self._size = len(self._records)    
        #--Load in the fields
        self._fields ['FID'] = IntField('FID') # Add FID field
        for (name, typeInfo) in self._sf.schema['properties'].items():
            typeParts = typeInfo.split(':')
            if typeParts[0] == 'int':
                field = IntField(name, int(typeParts[1]))
            elif typeParts[0] == 'float':
                formatParts = typeParts[1].split('.')
                field = FloatField(name, int(formatParts[0]), int(formatParts[1]))
            else:
                field = StringField(name, int(typeParts[1]))
            self._fields[field.name] = field
    
    def close(self):
        if (self._sf is not None) and (not self._sf.closed):
            self._sf.close()
    
    def readAll(self):
        '''
        Returns the full collection of geometry 
        '''
        return [geom for geom in self.readThrough()]
    
    def readThrough(self):
        for fid in range(0, self._size):
            yield self.readFrom(fid)
    
    def readFrom(self, fid):
        '''
        Reads a single record
        '''
        return self._records[fid]
    
    def writeAll(self, geometries):
        for geom in geometries:
            self.writeNext(geom)
    
    def writeNext(self, geometry, attributes={}): 
        self.writeTo(geometry, self._size, attributes)
        self._size += 1
        
    def _createShapefileIfNotExisting(self, geometry):
        if self._sf == None:
            geoType =  mapping(geometry)['type']
            # build schema
            self.schema = {}
            for field in self._fields.values():
                field.addToDf(self)
            self._sf = fiona.open(self._shape_file_path, 'w', 'ESRI Shapefile', {'geometry' : geoType,
                                                                                 'properties' : self.schema})
            
        
    def writeTo(self, geometry, fid, attributes={}):
        self._createShapefileIfNotExisting(geometry)
        properties= geometry.getAttributes()
        self._sf.write({
         'geometry' : mapping(geometry),
         'properties' : properties
        })
            
    def getFieldNames(self):
        return [k for k in six.iterkeys(self._fields)]
    
    def getFieldCount(self):
        return len(self.fields)
    
    def getGeometryType(self):
        return self.convert_index_to_geometry[self._geometryType]
    
    def addField(self, name, fieldType= 'STR', length=None, decimals=None, default=None, pyType= str):
        '''
        Adds a field to the shapefile's DBF. This method does NOT work if the shapefile
        already contains any records. Therefore, this method can only be used before
        the first geometry is written to the shapefile.
        
        ARGS:
            - name: The string name of the field. Required.
            - fieldType (='STR'): The type of the field. Accepted types are 'STR', 'INT',
                    'FLOAT', and 'BOOL'
            - length (=None): The length of the field. For string fields, this is the
                    maximum permitted number of characters. For int fields, this is
                    the number of digits. For float fields, this is the number of
                    digits to the left of the decimal.
                    If left blank, the default value for the field will be used.
            - decimals (=None): Applies to float fields only, and is the number of
                    digits to the right of the decimal. If left blank, the field's
                    default value of 4 gets used.
            - default (=None): A default value to apply if for some reason a write
                    occurs and the geometry does not specify this field's value.
            
            - pyType (=str): @deprecated: Use fieldType instead. Currently does nothing.
            
        '''
        if self._size > 0:
            raise IOError("Cannot add a field to a shapefile which already contains records!")
        fieldType = fieldType.upper()
        field = None
        if fieldType == 'STR':
            if length is None:
                length = 64
            field = StringField(name, length, decimals, default)
        elif fieldType == 'INT':
            field = IntField(name, length, decimals, default)
        elif fieldType == 'FLOAT':
            field = FloatField(name, length, decimals, default)
        if field is not None:
            self._fields[field.name] = field
        return field
    
    def setProjection(self, projectionFile= None):
        '''
        Sets the projection file (*.prj) for the shapefile. By default, the projection
        used is the same as that of the Emme project (only available for Emme versions
        4.1 and newer).
        
        Args:
            - projectionFile (=None): Optional path of a projection file to attach to this
                    shapefile. If omitted, the projection file of the Emme project is used
                    instead.
            
        '''
        major, minor, release, beta = _util.getEmmeVersion(tuple)
        
        if projectionFile is not None:
            #I have no way of checking that the existing file actually IS a projection
            #file. This will need to be used in good faith.
            if not _path.isfile(projectionFile):
                raise IOError("File %s does not exist" %projectionFile)
        #For a non-specified projection path, copy the file from the Emme Project
        #This can only be done for versions 4.1 and newer.
        elif (major, minor) >= (4,1):
            if release < 2: #4.1.1 has a slightly difference name
                projectionFile = _MODELLER.desktop.project.arcgis_spatial_reference_file
            else:
                projectionFile = _MODELLER.desktop.project.spatial_reference_file   
        else:
            _warn.warn("Emme project spatial reference only available in versions 4.1 and newer.")
            return #Do nothing
        
        destinationPath = self.filepath + ".prj"
        copyfile(projectionFile, destinationPath)
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, *args):
        self.close()
        
    def __len__(self):
        return self._size
