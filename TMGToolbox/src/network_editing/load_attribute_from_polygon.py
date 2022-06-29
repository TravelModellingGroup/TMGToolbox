#---LICENSE----------------------
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
#---METADATA---------------------
'''
Load Attribute From Shapefile
    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-26 by pkucirek
    
    1.0.0 Tested and published on 2014-07-04
    
'''


import traceback as _traceback
from shapely.validation import explain_validity

import inro.modeller as _m
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_geolib = _MODELLER.module('tmg.common.geometry')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_spindex = _MODELLER.module('tmg.common.spatial_index')
Shapely2ESRI = _geolib.Shapely2ESRI
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

def _insertnode(node, grid):
    p = _geolib.Point(node.x, node.y)
    p['NODE'] = node
    grid.insertPoint(p)

def _insertlink(link, grid):
    inode = link.i_node
    jnode = link.j_node
    
    coordinates = [vertex for vertex in link.vertices]
    coordinates.insert(0, (inode.x, inode.y))
    coordinates.append((jnode.x, jnode.y))
    
    ls = _geolib.LineString(coordinates)
    ls['LINK'] = link
    grid.insertLineString(ls)

def _insertline(line, grid):
    coords = [(node.x, node.y) for node in line.itinerary()]
    ls = _geolib.LineString(coords)
    ls['TRANSIT_LINE'] = line
    grid.insertLineString(ls)


def _insertsegment(segment, grid):
    link = segment.link
    
    inode = link.i_node
    jnode = link.j_node
    
    coordinates = copy(link.vertices)
    coordinates.insert(0, (inode.x, inode.y))
    coordinates.append((jnode.x, jnode.y))
    
    ls = _geolib.LineString(coordinates)
    ls['TRANSIT_SEGMENT'] = segment
    grid.insertLineString(ls)

class LoadAttributeFromPolygon(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 5 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    EmmeAttributeIdToLoad = _m.Attribute(str)
    ShapefilePath = _m.Attribute(str)
    ShapefileFieldIdToLoad = _m.Attribute(str)
    IntersectionOption = _m.Attribute(str)
    InitializeAttribute = _m.Attribute(bool)
    
    __loadedFields = []
    
    __ELEMENT_LOADERS = {'NODE': lambda net: [node for node in net.nodes()],
                         'LINK': lambda net: [link for link in net.links()],
                         'TRANSIT_LINE': lambda net: [line for line in net.transit_lines()],
                         'TRANSIT_SEGMENT': lambda net: [seg for seg in net.transit_segments()]}
    

    
    __ELEMENT_INSERTERS = {'NODE': _insertnode,
                           'LINK': _insertlink,
                           'TRANSIT_LINE': _insertline,
                           'TRANSIT_SEGMENT': _insertsegment}
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.InitializeAttribute = True
        self.IntersectionOption = 1
        self.ShapefileFieldIdToLoad = "bob"
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Load Attribute from Polygon v%s" %self.version,
                     description="Using a shapefile of polygons, this tool will load any network \
                            attribute from a specified field. Non-numeric fields must be able to be \
                            parsed into numeric values. For example '1' is acceptable since it \
                            parse to 1, but 'blue' cannot be converted to a numeric value.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        keyval1 = []
        for exatt in  self.Scenario.extra_attributes():
            if exatt.type == 'TURN': continue #Skip turn attributes
            keyval1.append((exatt.id, '%s - %s - %s' %(exatt.id, exatt.type, exatt.description)))
        pb.add_select(tool_attribute_name= 'EmmeAttributeIdToLoad',
                      keyvalues= keyval1, title= "Emme Attribute to Load",
                      note= "Select a NODE, LINK, LINE, or SEGMENT attribute in which to load data.")
        
        pb.add_checkbox(tool_attribute_name= 'InitializeAttribute',
                        label= "Initialize the attribute to its default value")
        
        pb.add_header("SHAPEFILE")
        
        pb.add_select_file(tool_attribute_name= 'ShapefilePath',
                           window_type= 'file', file_filter= "*.shp",
                           title= "Shapefile location",
                           note= " ")
        
        pb.add_select(tool_attribute_name= 'ShapefileFieldIdToLoad',
                      keyvalues=self.__loadedFields, title= 'Shapefile Field to Load',
                      note= 'String fields are accepted but will be cast to float.')
        
        pb.add_select(tool_attribute_name= 'IntersectionOption',
                      keyvalues= {'intersects': 'INTERSECTS', 'contains': 'CONTAINS'},
                      title="Intersection Option")
        
        #---JAVASCRIPT
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        if (! tool.is_shapefile_loaded())
        {
            $("#ShapefileFieldIdToLoad").prop('disabled', true);
        }
        
        
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#EmmeAttributeIdToLoad")
                .empty()
                .append(tool.preload_attributes())
            inro.modeller.page.preload("#EmmeAttributeIdToLoad");
            $("#EmmeAttributeIdToLoad").trigger('change')
        });
        
        $("#ShapefilePath").bind('change', function()
        {
            $(this).commit();
            
            //Load the valid fields
            $("#ShapefileFieldIdToLoad")
                .empty()
                .append(tool.preload_fields())
            $("#ShapefileFieldIdToLoad").trigger('change');
            inro.modeller.page.preload("#ShapefileFieldIdToLoad");
            $("#ShapefileFieldIdToLoad").prop('disabled', false);
            
            //Check shape type
            var shapeType = tool.preload_shape_type();
            var s = ""; 
            
            if (shapeType != 5)
            {            
                s = "<font color='red'><b>INVALID SHAPE TYPE. MUST BE POLYGON.</b></font>";
                $(".t_execution_block button").prop('disabled', true);
            } else {
                s = "<font color='green'><b>OK</b></font>";
                $(".t_execution_block button").prop('disabled', false);
            }
            
            $(this).parent().siblings(".t_after_widget").html(s);
        });
        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    @_m.method(return_type=six.text_type)
    def preload_fields(self):
        options = []
        self.__loadedFields = []
        validTypes = set(['INT', 'FLOAT'])
        
        with Shapely2ESRI(self.ShapefilePath, 'r') as reader:
            
            first = True
            for id, data in six.iteritems(reader.fields):
                #if not data.type in validTypes: continue #Skip fields which are not of type INT or FLOAT
                
                text = "%s (%s)" %(id, data.type)
                
                self.__loadedFields.append((id, text))
                options.append('<option value="%s">%s</option>' %(id, text))
                
                if first:
                    self.ShapefileFieldIdToLoad = id
                    first = False
                
        return "\n".join(options)
    
    @_m.method(return_type=six.text_type)
    def preload_attributes(self):
        options = []
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'TURN': continue #Skip turn attributes
            s = '<option value="%s">%s - %s - %s</option>' %(exatt.id, exatt.id, exatt.type, exatt.description)
            options.append(s)
        return "\n".join(options)
    
    @_m.method(return_type=int)
    def preload_shape_type(self):
        with Shapely2ESRI(self.ShapefilePath, 'r') as reader:
            return reader._geometryType
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
    
    @_m.method(return_type= bool)
    def is_shapefile_loaded(self):
        return bool(self.__loadedFields)
    
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
            
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            polygons = self._LoadPolygons()
            print("Loaded polygons")
            
            if self.InitializeAttribute:
                self.Scenario.extra_attribute(self.EmmeAttributeIdToLoad).initialize()
            
            network = self.Scenario.get_network()
            self.TRACKER.completeTask()
            print("Loaded network.")
            
            grid = self._SetupSpatialIndex(network)
            
            self._ApplyAttribute(grid, polygons)
            
            self.Scenario.publish_network(network)
            self.TRACKER.completeTask()
                

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _SetupSpatialIndex(self, network):
        exatt = self.Scenario.extra_attribute(self.EmmeAttributeIdToLoad)
        elements = self.__ELEMENT_LOADERS[exatt.type](network)
        
        extents = _spindex.get_network_extents(network)
        print("Determined network extents")
        
        grid = _spindex.GridIndex(extents, 200, 200)
        
        self.TRACKER.startProcess(len(elements))
        for element in elements:
            self.__ELEMENT_INSERTERS[exatt.type](element, grid)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        print("Indexed %s network elements" %len(elements))
        
        return grid
    
    def _LoadPolygons(self):
        with Shapely2ESRI(self.ShapefilePath) as reader:
            
            polygons = []
            self.TRACKER.startProcess(len(reader))
            for polygon in reader.readThrough():
                fid = polygon['FID']
                
                if not polygon.is_valid:
                    raise Exception("The polygon at FID=%s is not valid: %s" %(fid, explain_validity(polygon)))
                
                try:
                    val = polygon[self.ShapefileFieldIdToLoad]
                    polygon[self.ShapefileFieldIdToLoad] = float(val)
                except:
                    raise Exception("Cannot cast '%s' to float in field '%s' for FID=%s" %(val, self.ShapefileFieldIdToLoad, fid))
                
                polygons.append(polygon)
                self.TRACKER.completeSubtask()
                
            self.TRACKER.completeTask()
            
            return polygons
    
    def _ApplyAttribute(self, grid, polygons):
        element_type = self.Scenario.extra_attribute(self.EmmeAttributeIdToLoad).type
        
        self.TRACKER.startProcess(len(polygons))
        element_set = set()
        for polygon in polygons:
            #Use getattr to retrieve the method call
            intersection_method = getattr(polygon, self.IntersectionOption)
            
            value = polygon[self.ShapefileFieldIdToLoad]
            
            for element_geometry in grid.queryPolygon(polygon):
                if intersection_method(element_geometry):
                    element = element_geometry[element_type]
                    element_set.add(element)
                    element[self.EmmeAttributeIdToLoad] = value

            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        _m.logbook_write("%s network elements were changed" %len(element_set))
    
