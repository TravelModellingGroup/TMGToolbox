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
from copy import copy
'''
Copy Transit Lines

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-07-10 by pkucirek
    
    1.0.0 Published on 2014-08-27

    1.1.0 Fixed the calculation of maximum skipped stops at the beginning or end. 
          Added the function to copy dwt and ttf to target network as well.
    
'''

import inro.modeller as _m
from inro.emme.database.emmebank import Emmebank

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from math import pow, sqrt
from collections import namedtuple
from html import HTML

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_building = _MODELLER.module('inro.emme.utility.transit_line_build_utilities')

_util = _MODELLER.module('tmg.common.utilities')
_geolib = _MODELLER.module('tmg.common.geometry')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_spindex = _MODELLER.module('tmg.common.spatial_index')

ShapefileWriter = _geolib.Shapely2ESRI
NullPointerException = _util.NullPointerException

##########################################################################################################

ItineraryData = namedtuple('ItineraryData', "succeeded path_data skipped_stops error_msg error_detail dwt_ttf")

class CopyTransitLines(_m.Tool()):
    
    version = '1.1.0'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    SourceEmmebankPath = _m.Attribute(str)
    SourceScenarioId = _m.Attribute(str)
    SourceLineFilterAttributeId = _m.Attribute(str)
    
    TargetScenario = _m.Attribute(_m.InstanceType)
    TargetNewStopOptionId = _m.Attribute(str)
    TargetLinkCostAttributeId = _m.Attribute(str)
    
    OverwriteLinesFlag = _m.Attribute(bool)
    ClearTargetNetworkFlag = _m.Attribute(bool)
    
    TransitVehicleCorrespondenceFile = _m.Attribute(str)
    
    NodeCorrespondenceRadius = _m.Attribute(float)
    LineBufferRadius = _m.Attribute(float)
    MaxSkippedStartingStops = _m.Attribute(int)
    MaxSkippedEndingStops = _m.Attribute(int)
    MaxTotalSkippedStops = _m.Attribute(int)
    MaxTotalNewNodes = _m.Attribute(int)
    MaxSymmetricDifferece = _m.Attribute(float)
    
    ErrorShapefileReport = _m.Attribute(str)
    NodeCorrespondenceReportFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        self._cahcedSourceScenarioAttributes = {}
        
        #---Set the defaults of parameters used by Modeller
        self.SourceEmmebankPath = _MODELLER.emmebank.path
        self.SourceScenarioId = _MODELLER.scenario.id
        self.TargetScenario = _MODELLER.scenario
        self.TargetNewStopOptionId = 0
        self.TargetLinkCostAttributeId = 'length'
        self.ClearTargetNetworkFlag = True
        self.OverwriteLinesFlag = True
        
        self.NodeCorrespondenceRadius = 100.0
        self.LineBufferRadius = 100.0
        self.MaxSkippedStartingStops = 5
        self.MaxSkippedEndingStops = 5
        self.MaxTotalSkippedStops = 20
        self.MaxTotalNewNodes = 9999999
        self.MaxSymmetricDifferece = 9999999
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Copy Transit Lines v%s" %self.version,
                     description="Using network correspondence, copies a subset transit lines from \
                         a source scenario into a target scenario, even if node IDs are \
                         different. For each line, the tool tries to create as many segments \
                         in the target scenario as possible, filling in any gaps using shortest \
                         path. This new itinerary is then validated against specified conditions, \
                         such as maximum number of skipped (un-matched) stop nodes. The tool \
                         can also check for geometric similarity, by drawing polygon buffers \
                         around the original line and the copy, then computing the difference \
                         in area. \
                         <br><br>For each line in the selected set, the tool reports the line ID \
                         and error message to the Logbook. In most cases, when the matched \
                         itinerary contains at least two nodes, the tool will also write a polyline \
                         to the output shapefile (along with the error details).",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_file(tool_attribute_name= 'TransitVehicleCorrespondenceFile',
                           window_type='file', file_filter='*.csv',
                           title= "Transit vehicle correspondence file",
                           note= "Select a two-column CSV file which maps transit vehicle \
                           IDs from the source scenario to the target scenario.")
        
        pb.add_header("SOURCE")
        
        pb.add_select_file(tool_attribute_name= 'SourceEmmebankPath',
                           window_type='file', file_filter='emmebank',
                           title="Source Database",
                           note="Select a source database (can be in another project)")
        
        keyval1 = []
        for scenario in _MODELLER.emmebank.scenarios():
            key = scenario.id
            val = "{0!s} - {1!s}".format(key, scenario.title)
            keyval1.append((key, val))
            
            attributes = ['<option value="-1">ALL - Copy all transit lines in the source scenario</option>']
            for exatt in scenario.extra_attributes():
                if exatt.type != 'TRANSIT_LINE': continue
                text = "%s - TRANSIT LINE - %s" %(exatt.id, exatt.description)
                attributes.append('<option value="%s">%s</option>' %(exatt.id, text))
            self._cahcedSourceScenarioAttributes[scenario.id] = attributes
            
        pb.add_select(tool_attribute_name='SourceScenarioId',
                      keyvalues=keyval1, title="Source Scenario",
                      note="Select a scenario from the source database.")
        
        #Setup attributes
        keyval2 = [(-1, "ALL - Copy all transit lines in the source scenario")]
        keyval3 = []
        keyval4 = [('length', 'length - LINK - Link length'),
                   ('data1', 'ul1 - LINK - Link user data 1'),
                   ('data2', 'ul2 - LINK - Link user data 2'),
                   ('data3', 'ul3 - LINK - Link user data 3')]
        if _MODELLER.scenario.has_traffic_results:
            keyval4.append(('auto_time', 'timau - LINK - Link auto time'))
        for exatt in _MODELLER.scenario.extra_attributes():
            t = exatt.type
            text = "%s - %s - %s" %(exatt.id, t, exatt.description)
            if t == 'TRANSIT_LINE':
                keyval2.append((exatt.id, text))
            elif t == 'NODE':
                keyval3.append((exatt.id, text))
            elif t == 'LINK':
                keyval4.append((exatt.id, text))
          
        pb.add_select(tool_attribute_name= 'SourceLineFilterAttributeId',
                      keyvalues= keyval2, title= "Source Line Filter Attribute",
                      note= "TRANSIT LINE attribute selecting a subset of transit lines \
                      in the source scenario.")
        
        pb.add_header("TARGET")
        
        pb.add_select_scenario(tool_attribute_name= 'TargetScenario',
                               title= "Target Scenario",
                               note= "Select a target scenario from this database.")
        
        keyval3.insert(0, (1, "ALL - Stops on all new nodes"))
        keyval3.insert(0, (0, "NONE - No new stops"))
        pb.add_select(tool_attribute_name= 'TargetNewStopOptionId',
                      keyvalues= keyval3,
                      title= "Option for stops on new nodes",
                      note= "Select ALL to create stops on all new nodes, NONE to create no \
                      new stops, or select a node extra attribute to create new stops only \
                      on selected nodes in the target network.")
        
        pb.add_select(tool_attribute_name= 'TargetLinkCostAttributeId',
                      keyvalues= keyval4, title= "Link Cost Attribute")
        
        pb.add_checkbox(tool_attribute_name= 'ClearTargetNetworkFlag',
                        label= "Clear target network of existing transit lines?")
        
        pb.add_checkbox(tool_attribute_name= 'OverwriteLinesFlag',
                        label= 'Overwrite existing lines in the target network?',
                        note= "Lines in the source network having the same ID as lines in the \
                            target will be either overwritten, or reported as errors to the \
                            Logbook.")
        
        pb.add_header("TOOL PARAMETERS")
        
        options = [('NodeCorrespondenceRadius', 'Node correspondence radius', \
                    "Maximum radius to search for corresponding nodes"),
                   ('LineBufferRadius', "Line buffer radius", \
                    "The distance, in coordinates units, used to buffer transit \
                    line shapes for overlap testing"),
                   ('MaxSkippedStartingStops', "Max skipped starting stops", \
                    "The maximum number of untwinned (skipped) transit stops \
                    allowed at the start of a line's itinerary."),
                   ('MaxSkippedEndingStops', "Max skipped ending stops", \
                    "The maximum number of untwinned (skipped) transit stops \
                    allowed at the end of a line's itinerary."),
                   ('MaxTotalSkippedStops', "Max total skipped stops", \
                    "The maximum number of total untwinned (skipped) stops."),
                   ('MaxTotalNewNodes', "Max total new nodes", \
                    "The maximum number of new nodes permitted in a line's itinerary"),
                   ('MaxSymmetricDifferece', "Max area of difference", \
                    "The maximum permitted area (in squared coordinate units) of non-\
                    overlap between the source line shape and the target line shape.")]
        
        with pb.add_table(False) as t:
            first = True
            for toolAttributeName, title, note in options:
                if first:
                    first = False
                else:
                    t.new_row()
                
                with t.table_cell():
                    pb.add_html("<b>%s:</b>" %title)
                with t.table_cell():
                    pb.add_text_box(tool_attribute_name= toolAttributeName, size= 9)
                with t.table_cell():
                    pb.add_html(note)
        
        pb.add_header("OUTPUTS")
        
        pb.add_select_file(tool_attribute_name= 'ErrorShapefileReport',
                           window_type= 'save_file', file_filter= "*.shp",
                           title= "Error shapefile report",
                           note= "Save a shapefile to contain the shapes of transit lines \
                           which could not be copied to the target scenario.")
        
        pb.add_select_file(tool_attribute_name= 'NodeCorrespondenceReportFile',
                           window_type= 'save_file', file_filter= "*.csv",
                           title= "Node correspondence report",
                           note= "<font color='green'><b>Optional:</b></font> Specify a table \
                            in which to save node correspondence data.")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        $("#SourceScenarioId").bind('change', function()
        {
            $(this).commit();
            
            $("#SourceLineFilterAttributeId")
                .empty()
                .append(tool.preload_source_scenario_attributes())
            inro.modeller.page.preload("#SourceLineFilterAttributeId");
            $("#SourceLineFilterAttributeId").trigger('change')
        });
        
        $("#SourceEmmebankPath").bind('change', function()
        {
            $(this).commit();
            
            $("#SourceScenarioId")
                .empty()
                .append(tool.preload_database_scenarios())
            inro.modeller.page.preload("#SourceScenarioId");
            $("#SourceScenarioId").trigger('change')
        });
        
        $("#TargetScenario").bind('change', function()
        {
            $(this).commit();
            
            $("#TargetLinkCostAttributeId")
                .empty()
                .append(tool.preload_target_scenario_link_attributes())
            inro.modeller.page.preload("#TargetLinkCostAttributeId");
            $("#TargetLinkCostAttributeId").trigger('change')
            
            $("#TargetNewStopOptionId")
                .empty()
                .append(tool.preload_target_scenario_node_attributes())
            inro.modeller.page.preload("#TargetNewStopOptionId");
            $("#TargetNewStopOptionId").trigger('change')
        });
        
        $("#ClearTargetNetworkFlag").bind('change', function()
        {
            $(this).commit();
            var otherbox = $("#OverwriteLinesFlag");
            
            if ($(this).prop('checked'))
            {
                otherbox.prop('disabled', true);
            } else {
                otherbox.prop('disabled', false);
            }
            
        });
        
        $("#ClearTargetNetworkFlag").trigger('change');
        
    });
</script>""" % pb.tool_proxy_tag)
        
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        self.squaredSearchRadius = self.NodeCorrespondenceRadius * self.NodeCorrespondenceRadius
        
        if self.ErrorShapefileReport is None: raise NullPointerException("Error shapefile report not specified.")
        if self.TransitVehicleCorrespondenceFile is None:
            raise NullPointerException("Transit vehicle correspondence file not specified.")
        if self.NodeCorrespondenceRadius is None:
            raise NullPointerException("Node correspondence radius not specified.")
        if self.LineBufferRadius is None:
            raise NullPointerException("Line buffer not specified.")
        if self.MaxSkippedStartingStops is None:
            raise NullPointerException("Maximum number of skipped starting stops not specified.")
        if self.MaxSkippedEndingStops is None:
            raise NullPointerException("Maximum number of skipped ending stops not specified.")
        if self.MaxTotalNewNodes is None:
            raise NullPointerException("Maximum number of new nodes not specified.")
        if self.MaxTotalSkippedStops is None:
            raise NullPointerException("Maximum number of total skipped stops not specified.")
        if self.MaxSymmetricDifferece is None:
            raise NullPointerException("Maximum area of symmetric difference not specified.")
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def preload_database_scenarios(self):
        self._cahcedSourceScenarioAttributes = {}
        
        with Emmebank(self.SourceEmmebankPath) as bank:
            options = []
            for scenario in bank.scenarios():
                text = "%s - %s" %(scenario.id, scenario.title)
                options.append('<option value="%s">%s</option>' %(scenario.id, text))
                
                attributes = ['<option value="-1">ALL - Copy all transit lines in the source scenario</option>']
                for exatt in scenario.extra_attributes():
                    if exatt.type != 'TRANSIT_LINE': continue
                    text = "%s - TRANSIT LINE - %s" %(exatt.id, exatt.description)
                    attributes.append('<option value="%s">%s</option>' %(exatt.id, text))
                self._cahcedSourceScenarioAttributes[scenario.id] = attributes

            return "\n".join(options)
        
    @_m.method(return_type=unicode)
    def preload_source_scenario_attributes(self):
        return "\n".join(self._cahcedSourceScenarioAttributes[self.SourceScenarioId])
    
    @_m.method(return_type=unicode)
    def preload_target_scenario_link_attributes(self):
        options = ['<option value="length">length - LINK - Link length</option>',
                   '<option value="data1">ul1 - LINK - Link user data 1</option>',
                   '<option value="data2">ul2 - LINK - Link user data 2</option>',
                   '<option value="data3">ul3 - LINK - Link user data 3</option>']
        
        if self.TargetScenario.has_traffic_results:
            options.append('<option value="auto_time">timau - LINK - Link auto time</option>')
            
        for exatt in self.TargetScenario.extra_attributes():
            if exatt.type != 'LINK': continue
            text = "%s - LINK - %s" %(exatt.id, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.id, text))
        
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def preload_target_scenario_node_attributes(self):
        options = ['<option value="0">NONE - No new stops</option>',
                   '<option value="1">ALL - Stops on all new nodes</option>']
        
        if self.TargetScenario.has_traffic_results:
            options.append('<option value="auto_time">timau - LINK - Link auto time</option>')
            
        for exatt in self.TargetScenario.extra_attributes():
            if exatt.type != 'NODE': continue
            text = "%s - NODE - %s" %(exatt.id, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.id, text))
        
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def preload_vehicle_correspondence_file(self):
        try:
            with open(self.TransitVehicleCorrespondenceFile) as reader:
                self._cachedCorrespondence = {}
                header = reader.readline().strip()
                cells = header.split(',')
                if len(cells) >= 2:
                    if cells[0].isdigit() and cells[1].isdigit():
                        #Guessed that there is no header
                        self._cachedCorrespondence[int(cells[0])] = int(cells[1])
                        
                
                for line in reader:
                    if line.isspace(): continue #Skip blank lines
                    cells = line.strip().split(',')
                    sourceVehicleId = int(cells[0])
                    targetVehicleId = int(cells[1])
                    
                    self._cachedCorrespondence[sourceVehicleId] = targetVehicleId
            
            with Emmebank(self.SourceEmmebankPath) as emmebank:
                sourceScenario = emmebank.scenario(self.SourceScenarioId)
            
            for sourceVehicleId, targetVehicleId in self._cachedCorrespondence.iteritems():
                sourceVehicle = sourceScenario.transit_vehicle(sourceVehicleId)
                if sourceVehicle is None:
                    return "Vehicle %s does not exist in the source scenario" %sourceVehicleId
                
                targetVehicle = self.TargetScenario.transit_vehicle(targetVehicleId)
                if targetVehicle is None:
                    return "Vehicle %s does not exist in the target scenario" %targetVehicleId
                
                if sourceVehicle.mode.id != targetVehicle.mode.id:
                    tup = sourceVehicleId, sourceVehicle.mode.id, targetVehicle, targetVehicle.mode.id
                    return "Source vehicle % mode '%s' does not match target vehicle %s mode '%s'" %tup
            return None
            
        except Exception as e: return str(e)
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            sourceNetwork = self._LoadSourceNetwork()
            targetNetwork = self.TargetScenario.get_network()
            print "Loaded target network"
            
            if self.ClearTargetNetworkFlag:
                lineIds = [line.id for line in targetNetwork.transit_lines()]
                for lineId in lineIds: targetNetwork.delete_transit_line(lineId)
                print "Cleared all transit lines in the target scenario"
            
            pathBuilders = self._GetShortestPathCalculators(targetNetwork)
            print "Prepared path builders"
            
            vehicleTable = self._LoadVehicleCorrespondenceFile(sourceNetwork, targetNetwork)
            print "Loaded vehicle correspondence table"
            
            print "Starting network correspondence"
            self._BuildNetworkCorrespondence(sourceNetwork, targetNetwork)
            if self.NodeCorrespondenceReportFile:
                self._WriteCorrespondeceFile(sourceNetwork, targetNetwork)
            
            linesToProcess = self._PrepareNetwork(sourceNetwork)
            print "Found %s lines to copy over" %len(linesToProcess)
            
            errorTable = []
            with ShapefileWriter(self.ErrorShapefileReport, mode= 'w', \
                                 geometryType= ShapefileWriter._ARC) as writer:
                writer.addField('Line_ID', length=6)
                writer.addField('Error_msg', length=100)
                writer.addField('Err_detail', length= 200)
            
                errorTable = self._ProcessTransitLines(linesToProcess, targetNetwork, vehicleTable, \
                                          pathBuilders, writer)
                
                print "Done processing lines"
                print "Encountered %s errors" %len(errorTable)
                
                self._WriteErrorReport(errorTable)
                
            self.TRACKER.completeTask()
            print "Publishing network"
            targetNetwork.publishable = True
            self.TargetScenario.publish_network(targetNetwork, True)

    ##########################################################################################################    
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Source Scenario" : self.SourceScenarioId,
                "Source Emmebank": self.SourceEmmebankPath,
                "Target Scenario": str(self.TargetScenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadSourceNetwork(self):
        
        if self.SourceEmmebankPath == _MODELLER.emmebank.path:
            scenario = _MODELLER.emmebank.scenario(self.SourceScenarioId)
            
            if scenario is None:
                raise Exception("Scenario '%s' does not exist in database at "%self.SourceScenarioId\
                                 + self.SourceEmmebankPath)
            
            if scenario == self.TargetScenario:
                raise Exception("Source and target scenarios are the same!")
            
            network = scenario.get_network()
        else:
            with Emmebank(self.SourceEmmebankPath) as emmebank:
                scenario = emmebank.scenario(self.SourceScenarioId)
                
                if scenario is None:
                    raise Exception("Scenario '%s' does not exist in database at "%self.SourceScenarioId\
                                     + self.SourceEmmebankPath)
                network = scenario.get_network()
                
        print "Loaded source network"
        return network
    
    def _LoadVehicleCorrespondenceFile(self, sourceNetwork, targetNetwork):
        with open(self.TransitVehicleCorrespondenceFile) as reader:
            resultDictionary = {}
            
            header = reader.readline()
            for line in reader:
                cells = line.strip().split(',')
                sourceVehicleId = cells[0]
                targetVehicleId = cells[1]
                
                sourceVehicle = sourceNetwork.transit_vehicle(sourceVehicleId)
                if sourceVehicle is None:
                    raise IOError("A transit vehicle with ID '%s' does not exist in the source scenario" %sourceVehicleId)
                
                targetVehicle = targetNetwork.transit_vehicle(targetVehicleId)
                if targetVehicle is None:
                    raise IOError("A transit vehicle with ID '%s' does not exist in the target scenario" %sourceVehicleId)
                
                if sourceVehicle.mode.id != targetVehicle.mode.id:
                    tup = sourceVehicleId, sourceVehicle.mode, targetVehicleId, targetVehicle.mode
                    raise IOError("Source vehicle %s mode (%s) does not match target vehicle %s mode (%s)" \
                                  %tup)
                
                resultDictionary[sourceVehicleId] = targetVehicleId
            
            return resultDictionary

    def _GetShortestPathCalculators(self, network):
        pathBuilders = {}
        for transitMode in network.modes():
            if transitMode.type != 'TRANSIT': continue
            
            excludedLinks = [link for link in network.links() if not transitMode in link.modes]
            pathBuilder = _building.ShortestPath(network, self.TargetLinkCostAttributeId, excludedLinks)
            
            pathBuilders[transitMode.id] = pathBuilder
        return pathBuilders
    
    #---
    #---Network Correspondence
    def _BuildNetworkCorrespondence(self, sourceNetwork, targetNetwork):
        #Build spatial indexing objects
        sourceExtents = _spindex.get_network_extents(sourceNetwork)
        sourceIndex = _spindex.GridIndex(sourceExtents, xSize= 1000, ySize= 1000, marginSize= 1.0)
        for node in sourceNetwork.regular_nodes(): sourceIndex.insertPoint(node)
        
        targetExtents = _spindex.get_network_extents(targetNetwork)
        targetIndex = _spindex.GridIndex(targetExtents, xSize= 1000, ySize= 1000, marginSize= 1.0)
        for node in targetNetwork.regular_nodes(): targetIndex.insertPoint(node)
        
        print "Built spatial index"
        
        sourceNetwork.create_attribute('NODE', 'twin', None)
        targetNetwork.create_attribute('NODE', 'twin', None)
        
        nTwinnedNodes = 0
        self.TRACKER.startProcess(sourceNetwork.element_totals['regular_nodes'])
        #Search for twins for nodes in the source network
        for sourceNode in sourceNetwork.regular_nodes():
            sx, sy = sourceNode.x, sourceNode.y
            
            minDist = float('inf')
            ranking = []
            
            #Rank the nodes within the search radius
            for targetNode in targetIndex.queryCircle(sx, sy, self.NodeCorrespondenceRadius):
                tx, ty = targetNode.x, targetNode.y
                dx, dy = sx - tx, sy-ty
                sd = dx*dx + dy*dy
                
                if sd > self.squaredSearchRadius: continue
                
                ranking.append((sd, targetNode))
            
            #Check the candidate nodes for a symmetrical match
            #For the match to be symmetrical, both the target AND source nodes
            #must be the closest to each other. 
            ranking.sort()
            for currentDistance, targetNode in ranking:
                tx, ty = targetNode.x, targetNode.y
                symmetricMatch = True
                
                #Query the source network to see if there are any closer nodes to the
                #current candidate target node.
                #Need to query the SQRT of current distance, which is in squared units
                for otherNode in sourceIndex.queryCircle(tx, ty, sqrt(currentDistance)):
                    ox, oy = otherNode.x, otherNode.y
                    dx, dy = tx - ox, ty - oy
                    updatedDistance = dx*dx + dy*dy
                    if updatedDistance < currentDistance:
                        symmetricMatch = False
                        break
                
                if symmetricMatch:
                    sourceNode.twin = targetNode
                    targetNode.twin = sourceNode
                    sourceIndex.remove(sourceNode)
                    targetIndex.remove(targetNode)
                    nTwinnedNodes += 1
                    break
            
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        msg = "Found %s twins for nodes in the source network" %nTwinnedNodes
        _m.logbook_write(msg)
        print msg
    
    def _WriteCorrespondeceFile(self, sourceNetwork, targetNetwork):
        with open(self.NodeCorrespondenceReportFile, 'w') as writer:
            writer.write("Source node,Target node")
            
            twinnedTargetNodes = set()
            for sourceNode in sourceNetwork.regular_nodes():
                writer.write("\n%s,%s" %(sourceNode, sourceNode.twin))
                if sourceNode.twin is not None:
                    twinnedTargetNodes.add(sourceNode.twin.number)
            for targetNode in targetNetwork.regular_nodes():
                if targetNode.number in twinnedTargetNodes: continue
                writer.write("\n%s,%s" %(targetNode.twin, targetNode))
        print "Done writing report file."
                
    #---
    #---Core execution
    def _PrepareNetwork(self, network):
        
        if self.SourceLineFilterAttributeId is None:
            filter = lambda line: True
        else:
            filter = lambda line: line[self.SourceLineFilterAttributeId]
        
        linesToProcess = []
        
        network.create_attribute('TRANSIT_SEGMENT', 'stop_index', -1)
        for line in network.transit_lines():
            
            if not filter(line): continue
            
            counter = 0
            for segment in line.segments(True):
                if segment.allow_boardings or segment.allow_alightings:
                    segment.stop_index = counter
                    counter += 1
            
            linesToProcess.append(line)
            
        msg = "Found %s lines to copy over from the source scenario" %len(linesToProcess)
        return linesToProcess
    
    def _ProcessTransitLines(self, linesToProcess, targetNetwork, vehicleTable, pathBuilders, shapefileWriter):
        
        #Setup lambdas for assigning stops to nodes
        if self.TargetNewStopOptionId == '0':
            #None: no stops on new nodes
            segmentIsStop = lambda segment, sourceIsStop: sourceIsStop
        elif self.TargetNewStopOptionId == '1':
            #All: stops on all new nodes
            def segmentIsStop(segment, sourceIsStop):
                if sourceIsStop: return True
                return segment.i_node.twin is not None
        else:
            #Attribute: stops on flagged nodes
            def segmentIsStop(segment, sourceIsStop):
                if sourceIsStop: return True
                inode = segment.i_node
                isTwinned = inode.twin is not None
                return isTwinned and inode[self.TargetNewStopOptionId]
        
        errorTable = []
        
        def logError(lineId, errorMsg, errorDetail):
            errorTable.append((lineId, errorMsg, errorDetail))
        
        def logException(lineId, e):
            errorMsg = e.__class__.__name__
            errorDetail = str(e)
            logError(lineId, errorMsg, errorDetail)
        
        def logErrorWithGeometry(lineId, geometry, errorMsg, errorDetail):
            logError(lineId, errorMsg, errorDetail)
            geometry['Line_ID'] = lineId
            geometry['Error_msg'] = errorMsg
            geometry['Err_detail'] = errorDetail
            shapefileWriter.writeNext(geometry)
        
        self.TRACKER.startProcess(len(linesToProcess))
        for sourceLine in linesToProcess:
            
            if targetNetwork.transit_line(sourceLine.id) is not None:
                if not self.OverwriteLinesFlag:
                    logException(sourceLine.id, "Line with ID already exists.", "")
                    continue
                else:
                    targetNetwork.delete_transit_line(sourceLine.id)
            
            targetVehicle = targetNetwork.transit_vehicle(vehicleTable[sourceLine.vehicle.id])
            pathBuilder = pathBuilders[targetVehicle.mode.id]
            
            lineId = sourceLine.id
            
            #Try to construct the line's itinerary in the target network
            try:
                itineraryData = self._ConstructTargetItinerary(sourceLine, pathBuilder, targetNetwork, \
                                                               targetVehicle.mode)
                
                if itineraryData.succeeded == False: #Could not construct a path
                    logError(lineId, itineraryData.error_msg, itineraryData.error_detail)
                    self.TRACKER.completeSubtask()
                    continue
            except Exception as e: #Some unexpected error
                logException(lineId, e)
                self.TRACKER.completeSubtask()
                continue
            
            #Create the geometry to write to the final shapefile report
            errorShape = self._BuildTargetLineGeometry(targetNetwork, itineraryData.path_data, True)
            
            #Validate the created line itinerary
            success, errorMsg, errorDetail = self._ValidateItinerary(sourceLine, itineraryData.skipped_stops, \
                                                                     itineraryData.path_data, targetNetwork)
            if success == False:
                logErrorWithGeometry(lineId, errorShape, errorMsg, errorDetail)
                self.TRACKER.completeSubtask()
                continue
            
            #Copy over the transit line
            self._CopyTransitLine(sourceLine, itineraryData.path_data, targetNetwork, \
                                  targetVehicle.id, segmentIsStop, itineraryData.dwt_ttf)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        return errorTable
    
    def _ConstructTargetItinerary(self, line, pathBuilder, targetNetwork, targetMode):
        sourceNetwork = line.network
        
        skippedStops = []
        
        #Put together the stop-waypoints-stop structure required
        requiredStops = []
        buffer = []
        prevStop = None
        requiredStops_dwt_ttf = []

        for segment in line.segments(True):
            isStop = segment.stop_index >= 0
            index = segment.stop_index
            sourceNode = segment.i_node
            targetNode = sourceNode.twin
            isMatched = targetNode is not None
            
            if isMatched and isStop:
                tup = prevStop, buffer, sourceNode
                requiredStops.append(tup)
                prevStop = sourceNode
                buffer = []
                dwt_ttf = sourceNode, segment.dwell_time, segment.transit_time_func
                requiredStops_dwt_ttf.append(dwt_ttf) 
            elif isMatched and not isStop:
                buffer.append(targetNode)
            elif isStop and not isMatched:
                skippedStops.append((sourceNode, index))
        requiredStops.pop(0) #Remove the first entry, which should be (None, [] firstStop)
        
        if len(requiredStops) == 0: #No matched stops were found, return with error
            id = ItineraryData(False, [], skippedStops, "Could not find two or more stops.", "", requiredStops_dwt_ttf)
            return id
        
        #Initialize the path with the first required stop
        path_data = [(requiredStops[0][0].twin, True)]
        
        #Now to find the new path
        for fromSourceStop, targetWaypoints, toSourceStop in requiredStops:
            #Try to build the entire path including the waypoints
            protopath = [fromSourceStop.twin] + targetWaypoints + [toSourceStop.twin]
            path = []
            for i, j in _util.iterpairs(protopath):
                #Occasionally, the same node can legitimately occur twice in the sequence (if a line
                #doubles-back, for example). So just ignore it if this is the case
                if i == j: continue  
                
                #Check if a link already exists, and permits the targeted mode
                candidateLink = targetNetwork.link(i.id, j.id)
                if candidateLink is not None and targetMode in candidateLink.modes:
                    path.append(j)
                else: #Indirect path exists
                    nodeIDs = pathBuilder.find_path(i, j) #contains node IDs except for the first node
                    if nodeIDs is None:
                        path = []
                        break #Exit the loop, as no path exists for the selected mode
                    for id in nodeIDs: path.append(targetNetwork.node(id))
                    
            #If the path could not be constructed from waypoints, try to construct it
            #using just the from and to stops
            if len(path) == 0:
                path = []
                nodeIDs = pathBuilder.find_path(fromSourceStop.twin, toSourceStop.twin)
                if nodeIDs is None: #Path does not exist, return with error
                    details = "i=%s, j=%s, mode=%s" %(fromSourceStop.twin, toSourceStop.twin, line.mode)
                    id = ItineraryData(False, [], skippedStops, "Could not construct path for mode.", \
                                       details, requiredStops_dwt_ttf)
                    return id
                for id in nodeIDs: path.append(targetNetwork.node(id))
            path.pop(-1) #Remove the last node, such that path only contains inter-stop nodes
            
            #Add the subsequent segment(s) to the path_data
            for i, waypointNode in enumerate(path):
                if waypointNode is None:
                    print "Found None at index %s for line %s" %(i, line)
                path_data.append((waypointNode, False))
            path_data.append((protopath[-1], True))
        
        #The path has been successfully constructed
        id = ItineraryData(True, path_data, skippedStops, None, None, requiredStops_dwt_ttf)
        return id
    
    def _ValidateItinerary(self, line, skippedStops, pathData, targetNetwork):
        
        CheckSkippedStops = [list(x) for x in skippedStops]

        # count the total number of stops in the line to find the middle point
        totalStops = 0
        for segment in line.segments(True):
            if segment.stop_index >= 0: totalStops +=1
        middleStop = round(totalStops*0.5)

        # calculate the number of skipped stops 
        counter = 0
        for s in CheckSkippedStops:
            counter += 1
            s.append(counter)

        # find the middle point of the skipped stops
        middle_stop_index = 0
        for i in range(len(CheckSkippedStops)):
            if CheckSkippedStops[i][1] <= (middleStop - 1):
                middle_stop_index = i
            else:
                continue
                
        print "Skipped stops:%s" %CheckSkippedStops

        if len(CheckSkippedStops) > self.MaxTotalSkippedStops:
            errorMsg = "Exceeded the max number of skipped stops"
            errorDetail = len(CheckSkippedStops)
            return False, errorMsg, errorDetail
        
        if len(CheckSkippedStops) > 0 and (len(CheckSkippedStops) > self.MaxSkippedStartingStops or len(CheckSkippedStops) > self.MaxSkippedEndingStops):

            if (CheckSkippedStops[middle_stop_index][2]) > self.MaxSkippedStartingStops:
                errorMsg = "Exceeded the max number of skipped stops at the start of the line"
                errorDetail = CheckSkippedStops[middle_stop_index][2]
                return False, errorMsg, errorDetail
            
            if (CheckSkippedStops[-1][2] - CheckSkippedStops[middle_stop_index+1][2] + 1) > self.MaxSkippedEndingStops:
                errorMsg = "Exceeded the max number of skipped stops at the end of the line"
                errorDetail = CheckSkippedStops[-1][2] - CheckSkippedStops[middle_stop_index+1][2] + 1
                return False, errorMsg, errorDetail
        
        nNewNodes = sum([1 for node, isStop in pathData if node.twin is None])
        if nNewNodes > self.MaxTotalNewNodes:
            errorMsg = "Exceeded the max number of new nodes in the path."
            errorDetail = nNewNodes
            return False, errorMsg, errorDetail
        
        sourceLineShape = _geolib.transitLineToShape(line)
        targetLineShape = self._BuildTargetLineGeometry(targetNetwork, pathData)
        
        sourceBuffer = sourceLineShape.buffer(self.LineBufferRadius)
        targetBuffer = targetLineShape.buffer(self.LineBufferRadius)
        symmetricDifferenceShape = sourceBuffer.symmetric_difference(targetBuffer)
        sdArea = symmetricDifferenceShape.area
        
        if sdArea > self.MaxSymmetricDifferece:
            errorMsg = "Exceeded the maximum polygonal deviation from the source line"
            errorDetail = sdArea
            return False, errorMsg, errorDetail
        
        return True, None, None
   
    def _BuildTargetLineGeometry(self, targetNetwork, path_data, includeStopTicks= False):
        coords = []
        stopflags = []
        for (i, iIsStop), (j, jIsStop) in _util.iterpairs(path_data):
            xy = i.x, i.y
            coords.append(xy)
            stopflags.append(iIsStop)
            
            try:
                link = targetNetwork.link(i.id, j.id)
            except:
                print i, iIsStop, j, jIsStop
                raise
            for xy in link.vertices:
                coords.append(xy)
                stopflags.append(False)
        
        #Create the "standard" line shape
        lineShapeForChecking = _geolib.LineString(coords)
        return lineShapeForChecking
        
        '''
        The following code adds 'tick marks' to the line shape, where stops
        are found. However, I'm having a tough time properly rendering this
        shape (particularly looped routes are giving me a headache) so I've
        disabled this feature for now.
            - pkucirek August 26 2014
        '''
        
        if not includeStopTicks: return lineShapeForChecking
        
        #Create the "special" which includes "ticks" for stops along the route
        #Create a mitred offset line, which should contain the same # of vertices as the
        #original line.
        offsetLine = lineShapeForChecking.parallel_offset(20.0, side='right', join_style= 2, \
                                                          mitre_limit= 20.0)
        index = len(coords) - 1
        while index >= 0:
            if not stopflags[index]:
                index -= 1
                continue
            xy = coords[index]
            try:
                tickxy = offsetLine.coords[index]
            except:
                print lineShapeForChecking.type
                print offsetLine.type
                print coords
                raise
            coords.insert(index, xy)
            coords.insert(index, tickxy)
            index -= 1
        lineShapeWithTicks = _geolib.LineString(coords)
        
        return lineShapeWithTicks
    
    def _CopyTransitLine(self, sourceLine, pathData, targetNetwork, targetVehicleId, segmentIsStop, dwt_ttf):
        itinerary = [node.number for node, isStop in pathData]
        lineCopy = targetNetwork.create_transit_line(sourceLine.id, targetVehicleId, itinerary)
        sourceAttributes = set([attName for attName in sourceLine.network.attributes('TRANSIT_LINE')])

        for attName in targetNetwork.attributes('TRANSIT_LINE'):
            if attName in sourceAttributes: #Only copy attributes which exist in both scenarios.
                lineCopy[attName] = sourceLine[attName]

        stop_i = 0
        for i, (node, isStop) in enumerate(pathData):
            segment = lineCopy.segment(i)

            if node.id == dwt_ttf[stop_i][0].id:
                segment.dwell_time = dwt_ttf[stop_i][1]
                segment.transit_time_func = dwt_ttf[stop_i][2]
                stop_i += 1
            else:
                segment.dwell_time = 0
                segment.transit_time_func = dwt_ttf[0][2]

            if segmentIsStop(segment, isStop):
                segment.allow_boardings = isStop
                segment.allow_alightings = isStop

    def _WriteErrorReport(self, errorTable):
        h = HTML()
        
        t = h.table()
        tr = t.tr()
        tr.th("Line ID")
        tr.th("Error Message")
        tr.th("Error Details")
        
        for lineId, errorMsg, errorDetail in errorTable:
            tr = t.tr()
            tr.td(lineId)
            tr.td(errorMsg)
            tr.td(str(errorDetail))
        
        pb = _m.PageBuilder(title= "Error Report")
        
        headerText = "<b>Source Emmebank:</b> %s" %self.SourceEmmebankPath +\
                    "<br><b>Source Scenario:</b> %s" %self.SourceScenarioId +\
                    "<br><b>Target Scenario:</b> %s" %self.TargetScenario
        
        pb.add_text_element(headerText)
        
        pb.wrap_html(body= str(t))
        
        _m.logbook_write("Error report", value= pb.render())
        
        pass
            