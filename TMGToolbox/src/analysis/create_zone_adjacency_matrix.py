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
Create Zone Adjaency Matrix

    Authors: Peter Kucirek

    Latest revision by: @pkucirek
    
    
    Generates a zone adjacency matrix.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created 21-08-2013
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class CreateZoneAdjacencyMatrix(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType)
    ResultMatrixId = _m.Attribute(str)
    ZoneBoundariesFile = _m.Attribute(str)
    ZoneIdFiledName = _m.Attribute(str)
    BufferSize = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.BufferSize = 20.0
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Zone Adjacency Matrix v%s" %self.version,
                     description="Using a zone boundary shapefile, creates a full matrix of zone \
                         adjacencies (with 1 indicating that two zones are adjacent). Works by \
                         drawing a buffer around each zone boundary and testing for intersection; \
                         so zones touching at a corner will be considered adjacent. A zone is \
                         always adjacent to itself.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_new_matrix(tool_attribute_name='ResultMatrixId',
                                 overwrite_existing=True,
                                 title="Zone Adjacency Matrix")
        
        pb.add_select_file(tool_attribute_name='ZoneBoundariesFile',
                           window_type='file', file_filter="ESRI shapefiles *.shp",
                           title="Zone Boundary File")
        
        pb.add_text_box(tool_attribute_name='ZoneIdFiledName',
                        size=10, title="Name of zone id field",
                        note="Used to attach zone geometry to zone.")
        
        pb.add_text_box(tool_attribute_name='BufferSize',
                        size=10, title="Buffer Size")
        
        return pb.render()
    
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
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            
            adjacencyMatrix = _util.initializeMatrix(id=self.ResultMatrixId, name="zadj", description="Zone adjacency matrix")
            
            network = self.Scenario.get_network()
            _m.logbook_write("Loaded network data")
            with _m.logbook_trace("Loading zone boundaries"):
                self._LoadShapefileGeometry(network)
                self.TRACKER.completeTask()
                
            with _m.logbook_trace("Processing zone adjacencies"):
                self._ProcessAdjacencies(network, adjacencyMatrix)
                self.TRACKER.completeTask()

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Zone Boundary File": self.ZoneBoundariesFile,
                "Zone Id Field": self.ZoneIdFiledName,
                "Buffer Radius": self.BufferSize,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _LoadShapefileGeometry(self, network):
        network.create_attribute('NODE', 'geometry', default_value=None)
        loaded = 0
        with _geo.Shapely2ESRI(self.ZoneBoundariesFile) as reader:
            self.TRACKER.startProcess(len(reader))
            if not self.ZoneIdFiledName in reader.getFieldNames():
                raise IOError("Cannot find zone id field '%s' in zone boundary shapefile '%s'." %(self.ZoneIdFiledName, self.ZoneBoundariesFile))
            for feature in reader.readThrough():
                zoneId = reader.get_properties_by_fid(loaded)[self.ZoneIdFiledName] #this is the zoneId integer
                zone = network.node(zoneId)
                if zone is None or not zone.is_centroid:
                    _m.logbook_write("Could not find a valid zone '%s' in network" %zoneId)
                    self.TRACKER.completeSubtask()
                    continue
                zone.geometry = feature.buffer(self.BufferSize, 1)
                loaded += 1
                self.TRACKER.completeSubtask()
        
        _m.logbook_write("Loaded %s features from file" %loaded)
            
    def _ProcessAdjacencies(self, network, matrix):        
        data = matrix.get_data(self.Scenario)
        _m.logbook_write("Loaded matrix data")
        adjacencies = 0
        
        def flagPQ(p, q):
            if p == q:
                return True
            elif p.geometry is not None and q.geometry is not None:
                return p.geometry.intersects(q.geometry)
            return False
        
        # This is a deliberately slow procedure. The smarter option would be to do a search grid, but
        # ATM I don't have time to figure that out. - pkucirek
        self.TRACKER.startProcess(network.element_totals['centroids'] * network.element_totals['centroids'])
        for p in network.centroids():
            for q in network.centroids():
                if flagPQ(p, q):
                    data.set(p.number, q.number, 1)
                    adjacencies += 1
                self.TRACKER.completeSubtask()
        
        _m.logbook_write("Found %s adjacencies in the network" %adjacencies)
        matrix.set_data(data, self.Scenario)
        _m.logbook_write("Saved matrix data")
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    