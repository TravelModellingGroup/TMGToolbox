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
GET STATION ACCESS FILE

    Authors: Peter Kucirek

    Latest revision by: @pkucirek
    
    
    Built for GTAModel (Durham Model, City of Toronto Model).
    
    Creates a CSV file which lists if a GO or subway station is within a user-specified distance, e.g.
    
        ZONE#,CloseToSubway,CloseToGo
        458,1,0
    
    Skipping zones with neither station nearby.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
    
    1.0.0 Published to use the new spatial index module.
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
from math import sqrt
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_spindex = _MODELLER.module('tmg.common.spatial_index')

##########################################################################################################

class GetStationAccessFile(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    SearchRadius = _m.Attribute(float)
    GoStationSelectorExpression = _m.Attribute(str)
    ExportFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.SearchRadius = 1000.0
        self.GoStationSelectorExpression = "i=7000,8000"
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Get Station Access File v%s" %self.version,
                     description="<p class='tmg_left'> Produces a table indicating which zones are within a 1km \
                         (or other user-specified distance) from subway or GO train stations. \
                         Subway stations are identified as stops of lines with mode = <b>'m'</b>. \
                         GO stations can be identified in one of two ways: \
                         <ol class='tmg_left'><li> Station centroids, \
                         identified by a node selector expression; or</li><li> Stops of lines with mode \
                         = <b>'r'.</b></li></ol> \
                         <p class='tmg_left'> This data is saved into a CSV file with three columns: \
                         <em>'Zone', 'NearSubway' , 'NearGO'</em>. The first column identifies the zone, \
                         the second column indicates whether a zone is within the radius of a subway \
                         station (0 or 1), and the third column indicates whether a zone is within the \
                         radius of a GO Train station (0 or 1). Zones not in the radius of either are not \
                         listed.</p>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='SearchRadius',
                        size=10, title="Search Radius",
                        note="In coordinate units (m)")
        
        basepath = _path.dirname(_MODELLER.desktop.project_file_name())
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           file_filter="*.csv",
                           start_path=basepath,
                           title="Output File")
        
        pb.add_text_box(tool_attribute_name='GoStationSelectorExpression',
                        size=100, multi_line=True,
                        title="GO Station Selector",
                        note="<font color='green'><b>Optional:</b></font> \
                            Write a zone filter expression to select GO Station centroids.\
                            <br>If ommitted, this tool will use GO rail line stops.")
        
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
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, xtmf_ScenarioNumber, SearchRadius, GoStationSelectorExpression, ExportFile):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.SearchRadius = SearchRadius
        self.GoStationSelectorExpression = GoStationSelectorExpression
        self.ExportFile = ExportFile
        
        try:
            self._Execute()
        except Exception as e:
            raise Exception(_traceback.format_exc())
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            #self.ExportFile = _path.splitext(self.ExportFile)[0] + ".csv"
            
            with self._FlagAttributeMANAGER():
                try:
                    netCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
                except Exception as e:
                    netCalcTool = _MODELLER.tool('inro.emme.standard.network_calculation.network_calculator')
                
                if self.GoStationSelectorExpression:
                    _m.logbook_write("Flagging GO station centroids.")
                    self.TRACKER.runTool(netCalcTool, self._GetCentroidFlagSpec(), scenario=self.Scenario)
                else:
                    self.TRACKER.completeTask()
                
                _m.logbook_write("Building search grid")    
                network = self.Scenario.get_network()
                self.TRACKER.completeTask()
                
                network.create_attribute('NODE', 'subStation', 0)
                network.create_attribute('NODE', 'goStation', 0)
                
                with _m.logbook_trace("Getting station coordinates"):
                    self._FlagTransitStops(network)
                    subwayStations, goStations = self._GetNodeSet(network)
                    
                with nested(_m.logbook_trace("Performing search"),
                            open(self.ExportFile, 'w')) as (log, writer):
                    
                    #Prepare the search grid
                    extents = _spindex.get_network_extents(network)
                    spatialIndex = _spindex.GridIndex(extents, marginSize= 1.0)
                    for zone in network.centroids():
                        spatialIndex.insertPoint(zone)
                    
                    self.TRACKER.startProcess(len(subwayStations) + len(goStations))
                    for station in subwayStations:
                        nearbyNodes = spatialIndex.queryCircle(station.x, station.y, self.SearchRadius)
                        for node in nearbyNodes:
                            dist = sqrt((node.x - station.x)**2 + (node.y - station.y)**2)
                            if dist > self.SearchRadius: continue
                            
                            node.subStation = 1
                        self.TRACKER.completeSubtask()
                    
                    for station in goStations:
                        nearbyNodes = spatialIndex.queryCircle(station.x, station.y, self.SearchRadius)
                        for node in nearbyNodes:
                            dist = sqrt((node.x - station.x)**2 + (node.y - station.y)**2)
                            if dist > self.SearchRadius: continue
                            
                            node.goStation = 1
                        self.TRACKER.completeSubtask()
                    
                    #Prepare the file
                    writer.write("Zone,NearSubway,NearGO")
                    for centroid in network.centroids():
                        writer.write("\n%s,%s,%s" %(centroid.number, 
                                                      centroid.subStation, 
                                                      centroid.goStation))
                        
                        
                    self.TRACKER.completeTask()

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _FlagAttributeMANAGER(self):
        if self.GoStationSelectorExpression:
            att = self.Scenario.create_extra_attribute('NODE', '@xflag')
        try:
            yield
        finally:
            if self.GoStationSelectorExpression:
                self.Scenario.delete_extra_attribute('@xflag')
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _GetCentroidFlagSpec(self):
        spec = {
                "result": "@xflag",
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "node": self.GoStationSelectorExpression
                               },
                "type": "NETWORK_CALCULATION"
                }
        
        return spec
    
    def _GetCheckMode(self, network, modeId):
        mode = network.mode(modeId)
        if mode is None:
            raise Exception("Scenario %s does not have mode '%s' defined!" %(self.Scenario.id, modeId))
        elif mode.type != 'TRANSIT':
            raise Exception("Scenario %s mode '%s' is not a transit mode!" %(self.Scenario.id, modeId))
        return mode
    
    def _FlagTransitStops(self, network):
        network.create_attribute('NODE', 'isStop', default_value=0)
        
        subwayMode = self._GetCheckMode(network, 'm')
        trainMode = self._GetCheckMode(network, 'r')
        
        self.TRACKER.startProcess(network.element_totals['transit_lines'])
        for line in network.transit_lines():
            if line.mode == subwayMode:
                for segment in line.segments(include_hidden=True):
                    if segment.allow_alightings or segment.allow_boardings:
                        segment.i_node.isStop = 1 #SUBWAY STOP
            elif line.mode == trainMode:
                for segment in line.segments(include_hidden=True):
                    if segment.allow_alightings or segment.allow_boardings:
                        segment.i_node.isStop = 2 #GO TRAIN STOP
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
    
    def _GetNodeSet(self, network):
        subwayStations = set()
        goStations = set()
        
        subStopCount = 0
        goStopCount = 0
        
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        for node in network.regular_nodes():
            if node.isStop == 1:
                subwayStations.add(node)
                subStopCount += 1
            elif node.isStop == 2 and not self.GoStationSelectorExpression:
                goStations.add(node)
                goStopCount += 1
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        
        if self.GoStationSelectorExpression:
            self.TRACKER.startProcess(network.element_totals['centroids'])
            for centroid in network.centroids():
                if centroid['@xflag'] == 1:
                    goStations.add(centroid)
                    goStopCount += 1
                self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        _m.logbook_write("Found %s subway stations and %s GO train stations." %(subStopCount, goStopCount))
        
        return (subwayStations, goStations)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    