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
import shapelib as _shp
import dbflib as _dbf
from shutil import copyfile
from os import path as _path
import warnings as _warn
import inro.modeller as _m

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
    
    if type.lower() == 'point':
        vertices = list(geom.coords)
        return Point(vertices[0][0], vertices[0][1])
    elif type.lower() == 'linestring':
        return LineString(list(geom.coords))
    elif type.lower() == 'polygon':
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
    except ZeroDivisionError, e:
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
        df.add_field(self.name, _dbf.FTString, self.length, 0)
    
    def format(self, value):
        return str(value)[:self.length]
    
    def __str__(self):
        return "%s (STR)" %self.name

class FloatField():
    def __init__(self, name, length=12, decimals=4, default=0.0):
        if length < 3:
            raise IOError("DBF field definition failed: Field length must be at least 3.")
        if decimals >= (length - 2):
            raise IOError("DBF field definition failed: Cannot assign more than {0} decimals for a field length of {1}".format((length - 2), length))
        
        self.name =str(name)
        self.max = float(pow(10, length - decimals - 1) - 1)
        self.min = - float(pow(10, length - decimals - 1) - 2) # This is untested.
        self.length = length
        self.decimals = decimals
        self.default = default
        
        self.type = 'FLOAT'
    
    def addToDf(self, df):
        df.add_field(self.name, _dbf.FTDouble, self.length, self.decimals)
    
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
        df.add_field(self.name, _dbf.FTInteger, self.length, 0)
    
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
        df.add_field(self.name, _dbf.FTInteger, 1, 0)
    
    def format(self, value):
        return int(bool(value))
    
    def __str__(self):
        return "%s (BOOL)" %self.name

#---Shapefile class for I/O

class Shapely2ESRI():
    '''
    Object for interacting between shapefiles and Shapely Geometry. Reads shapefiles
    as shapely geometry objects, and writes shapely geometry objects to shapefiles.
    
    USAGE:
    
    Reading:
    
    with Shapely2ESRI("C:/MyDocuments/zone_centroids.shp", mode = 'read') as reader:
        for point in reader.readThrough():
            zoneId = point['Zone'] #Zone is the name of a defined field in the associated DBF
            ...
            
    Writing:
    
    with Shapely2ESRI("C:/MyDocuments/emme_nodes.shp", mode = 'write', 
            geometryType = Shapely2ESRI.SHP_POINT_TYPE) as writer:
        writer.addField('UI1', type=float)
        
        for node in network.nodes():
            point = nodeToShape(node)
            writer.writeNext(point)
            ...
    
    USEFUL METHODS:
        
        - addField(...): Adds a field to a new shapefile.
        - getGeometryType(): Returns a string representation of the geometry
                type.
        - getFieldNames(): Returns an iterable of field names in the
                shapefile.
        - getFieldCount(): Returns the number of fields defined.
        - __len__(): Returns the number of records defined in the shapefile.
        - __enter__(), __exit__(): Allows the class to be used as a context
                manager inside a 'with' statement.
        
    USEFUL PROPERTIES:
        
        - fields: A dict of {field_name : field_info} which can be used to
                get information about the fields in this object.
        - filepath: The path to the actual shapefile.
        - invalidFeatureIDs: A list of FIDs with invalid geometry. Sometimes
                the shapefile can define shapes that are geometrically
                invalid (see http://toblerity.org/shapely/manual.htm for
                details about what makes a shape invalid). This list
                contains FIDs of any invalid shapes that have been
                loaded.
    
    '''
    
    SHP_POINT_TYPE = _shp.SHPT_POINT
    SHP_LINE_TYPE = _shp. SHPT_ARC
    SHP_POLYGON_TYPE = _shp. SHPT_POLYGON
    SHP_NULL_TYPE = _shp.SHPT_NULL
    
    _pyTypeMap = {int : IntField,
               float : FloatField,
               str : StringField,
               bool : BoolField}
    
    _fieldTypeMap = {'INT' : IntField,
                'FLOAT' : FloatField,
                'STR' : StringField,
                'BOOL' : BoolField}
    
    _dbf2fieldMap = {_dbf.FTInteger : IntField,
                     _dbf.FTDouble: FloatField,
                     _dbf.FTString : StringField}
    
    _geom2shp = {'NULL' : _shp.SHPT_NULL,
                 'POINT' : _shp.SHPT_POINT,
                 'LINESTRING' : _shp. SHPT_ARC,
                 'POLYGON' : _shp. SHPT_POLYGON}
    
    _shp2geom = dict((v,k) for k, v in _geom2shp.iteritems())
    
    def __init__(self, filepath, mode='read', geometryType=0, projectionFile= None):
        '''
        Opens a new shapefile for reading, writing, or appending. If
        reading, only the filepath need be specified. If writing,
        the geometry type MUST be specified, otherwise an error
        will occur.
        
        The currently-defined fields can be accessed by the 'fields'
        property, which is a dictionary of {ID : FiedlObject} (see
        StringField, FloatField, IntField, and BoolField above).        
        
        To add fields to a new shapefile, call the method 'addField.'
        
        ARGS:
        
            - filepath: The string path to the shapefile
            - mode (='read'): One of "read", "write", "append". Characters
                    'r', 'w', and 'a' are also accepted.
            - geometryType (=0): Optional, except if writing. Can either be
                    an integer or string. Acceptable integer values are 
                    given by the class static properties SHP_POINT_TYPE,
                    SHP_LINE_TYPE, SHP_POLYGON_TYPE, and SHP_NULL_TYPE.
                    Acceptable string values are 'POINT', 'LINESTRING',
                    'POLYGON', and 'NULL' respectively.
            - projectionFile (=None): Optional path of a projection file to
                    attach to this shapefile (writing ONLY). If omitted, the 
                    projection file of the Emme project is used instead. The
                    projection can also be set later using setProjection(...)
        
        '''
        self.filepath = _path.splitext(filepath)[0] #Drop the extension
        self.fields = {}
        self._sf = None
        self._df = None 
        self._size = 0
        
        if mode.lower().startswith("r"): #READ MODE
            self._canread = True
            self._canwrite = False
            self.invalidFeatureIDs = set()
        elif mode.lower().startswith("w"): #WRITE MODE
            if projectionFile != None:
                self.setProjection(projectionFile)
            self._canread = False
            self._canwrite = True
            if geometryType == None:
                _warn.warn("No geometryType specified. This will cause errors when writing to a shapefile.")
            
        elif mode.lower().startswith("a"): #APPEND MODE
            self._canread = True
            self._canwrite
        else:
            _warn.warn("Mode '%s' not recognized. Defaulting to read mode" %mode)
            self._canread = True
            self._canwrite = False
        
        try:
            try: #This type gets overwritten on read
                self._geometryType = int(geometryType)
            except ValueError, ve:
                self._geometryType = self._geom2shp[geometryType.upper()]
        except KeyError, ke:
            raise IOError("Geometry type '%s' not recognized/supported." %geometryType)
                  
    def open(self):
        '''
        Opens a shapefile. Not required if using inside a 'with' statement
        '''
        if self._canread:
            self._load()
        else:
            self._create()
        
    def _create(self):
        self._sf = _shp.create(self.filepath, self._geometryType)
        self._df = _dbf.create(self.filepath)
        self._size = 0
    
    def _load(self):
        # Open the files
        self._sf = _shp.open(self.filepath)
        self._df = _dbf.open(self.filepath)
        self._size = self._df.record_count()
        
        self._geometryType = self._sf.read_object(0).type
        
        #--Load in the fields
        self.fields ['FID'] = IntField('FID') # Add FID field
         
        for i in range(0, self._df.field_count()):
            info = self._df.field_info(i)
            #type, name, length, decimals
            type = info[0]
            try:
                field = self._dbf2fieldMap[type](info[1], info[2], info[3])
                self.fields[field.name] = field
            except KeyError, ke:
                raise IOError("DBF Field type {0} for field '{1}' is \
                unsupported!".format(info[0], info[1]))
    
    def close(self):
        '''
        Closes the file. Not required if using inside a 'with' statement
        '''
        self._sf.close()
        self._df.close()
        self.fields.clear()
    
    def readAll(self):
        '''
        Returns the full collection of geometry 
        '''
        l = [geom for geom in self.readThrough()]
        if len(self.invalidFeatureIDs) > 0:
            _warn.warn("%s features were found to be invalid. This could cause problems with geometric operations.")
        return l
    
    def readThrough(self):
        '''
        Iterable read
        '''        
        for fid in range(0, self._size):
            yield self.readFrom(fid)
    
    def readFrom(self, fid):
        '''
        Reads a single record
        '''
        if not self._canread: raise IOError("Reading disabled on this object.")
        if self._sf == None:
            raise IOError("Shapefile hasn't been opened. Call [this].open() first.")
        
        feature = self._sf.read_object(fid)
        type = feature.type
        
        if type == self.SHP_POINT_TYPE:
            geom = Point(feature.vertices()[0])
        elif type == self.SHP_LINE_TYPE:
            geom = LineString(feature.vertices()[0])
        elif type == self.SHP_POLYGON_TYPE:
            v = feature.vertices()
            shell = v[0]
            holes = []
            for i in range(1, len(v)):
                holes.append(v[i])
            geom = Polygon(shell, holes)
        else:
            raise NotImplementedError("Shape type '%s' is not currently supported." %type)
        
        if not geom.is_valid:
            self.invalidFeatureIDs.add(fid)
        geom.setAttributes(self._df.read_record(fid))
        geom['FID'] = fid
        
        return geom
    
    def writeAll(self, geometries):
        '''
        Writes an iterable of attribute-attached shapely geometries at the end of the file.
        '''
        for geom in geometries:
            self.writeNext(geom)
    
    def writeNext(self, geometry, attributes={}):
        '''
        Writes a single shapely geometry at the end of the file. Optional attributes argument
        for not-attachcable-subclass shapely objects
        '''        
        self.writeTo(geometry, self._size, attributes)
        self._size += 1
        
    def writeTo(self, geometry, fid, attributes={}):
        '''
        Overwrites an existing geometry in the file at the specified index.  Optional attributes 
        argument for not-attachcable-subclass shapely objects
        '''
        if not self._canwrite: raise IOError("Writing disabled on this object.")
        if self._sf == None:
            raise IOError("Shapefile hasn't been opened. Call [this].open() first.")
        if len(self.fields) == 0:
            self.addField('NULL', int, 5)
            _warn.warn("No attribute fields defined. 'NULL' field was added to the attribute table.")
        
        # Write the geometry to the .shp file
        gtype = geometry.type
        if self._geom2shp[gtype.upper()] != self._geometryType:
            raise IOError("Cannot add geometry type {0} ({1}) to shapefile type {2} \
                ({3})!".format(self._geom2shp[gtype.upper()], gtype,
                               self._geometryType, self._shp2geom[self._geometryType]))
        
        vertices = []
        if gtype == 'Point':
            vertices = [list(geometry.coords)]
        elif gtype == 'LineString':
            vertices = [list(geometry.coords)]
        elif gtype == 'Polygon':
            vertices.append(list(geometry.exterior.coords))
            for interior in geometry.interiors:
                vertices.append(list(interior.coords))
        else:
            raise IOError("Geometry type %s currently unsupported." %gtype)
        self._sf.write_object(fid, _shp.SHPObject(self._geometryType, fid, vertices))
        
        # Write the geometry's attributes to the .dbf file
        record = {}
        if not '__getitem__' in dir(geometry):
            # Geometry doesn't inherit the attachable subclass
            geometry = attributes #--> Replace the reference to geometry so it acts like a map.
            # The actual geometry is no longer needed at this point anyways
            '''
            _warn.warn("No attributes were attached to geometry. Use optional arg \
            'attributes' or an attachable geometry. Default values were used.")
            '''
        
        for fieldName, field in self.fields.items():
            try:
                val = field.format(geometry[fieldName])
            except KeyError, ke:
                val = field.default
            except Exception, e:
                _warn.warn("Caught exception {0} formatting field {1}. \
                    Default value used.".format(str(e), fieldName))
                val = field.default
            record[fieldName] = val
        self._df.write_record(fid, record)
            
    def getFieldNames(self):
        return [k for k in self.fields.iterkeys()]
    
    def getFieldCount(self):
        return len(self.fields)
    
    def getGeometryType(self):
        return self._shp2geom[self._geometryType]
    
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
        
        name = str(name)
        field = None
        try:
            klass = self._fieldTypeMap[fieldType]
        except KeyError, ke:
            raise KeyError("'%s' not recognized as valid field type" %fieldType)
        if length == None and decimals == None and default == None: field = klass(name)
        elif length == None and decimals== None: field = klass(name, default=default)
        elif length== None and default == None: field = klass(name, decimals=decimals)
        elif decimals == None and default == None: field = klass(name, length=length)
        elif length == None: field = klass(name, decimals=decimals, default=default)
        elif decimals == None: field = klass(name, length=length, default=default)
        elif default == None: field = klass(name, length=length, decimals=decimals)
        else: field = klass(name, length=length, decimals=decimals, default=default)
        
        self.fields[name] = field
        field.addToDf(self._df)
        
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
        
        if projectionFile != None:
            #I have no way of checking that the existing file actually IS a projection
            #file. This will need to be used in good faith.
            if not _path.isfile(projectionFile):
                raise IOError("File %s does not exist" %projectionFile)
        #For a non-specified projection path, copy the file from the Emme Project
        #This can only be done for versions 4.1 and newer.
        elif major >= 4 and minor >= 1:
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










        