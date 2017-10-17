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
Copy Zone System V2

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Copies a zone system (centroids + connectors) from a
     source scenario to a target scenario. The source scenario does
     not need to be in the same database. Optionally, a shapefile can
     be written which contains those connectors that were not able to
     be copied from the source to the target.
     
    Two options are available for matching connector j-nodes: 
     GEOMETRY (default), and NODE_ID. GEOMETRY will use the 
     source node's coordinates to find the nearest target node within 
     a specified radius. NODE_ID will find the node in the target network 
     with the same number, to a specified tolerance of link length.
     
    Five error types are reported to the Logbook:
     -'No match (ID)': The source j-node does not exist
         in the target scenario.
     -'No match (Coordinate)': No target node could be found
         within the specified radius of the source j-node.
     -'Flagged to skip': A j-node was found, but was flagged
         to be skipped.
     -'Bad link length': The new target connector's length is greater
         than the source connector's length by the specified margin.
     -'Found overlap': A connector between the zone and the
         found j-node already exists.
        
'''
#---VERSION HISTORY
'''
    0.2.0 Created on 2014-03-11 by pkucirek
    
    1.0.0 Changed to "published" version number as this version is clean and well-tested.
    
    1.0.1 Re-factored to use the more general-purpose Spatial Index module
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from inro.emme.database.emmebank import Emmebank
from math import sqrt
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geolib = _MODELLER.module('tmg.common.geometry')
_spindex = _MODELLER.module('tmg.common.spatial_index')
NullPointerException = _util.NullPointerException
Shapely2ESRI = _geolib.Shapely2ESRI

##########################################################################################################

class CopyZoneSystem2(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    ToScenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ToNodesToIgnoreSelector = _m.Attribute(str)
    FromEmmebankPath = _m.Attribute(str)
    FromScenarioId = _m.Attribute(str)
    FromZonesToIgnoreSelector = _m.Attribute(str)
    
    MatchOption = _m.Attribute(str)
    LinkLengthTolerance = _m.Attribute(float)
    CoordinateTolerance = _m.Attribute(float)
    ShapefileReport = _m.Attribute(str)
    ClearTargetZonesFlag = _m.Attribute(bool)
    OverrideDuplicates = _m.Attribute(bool)
    PublishNetworkFlag = _m.Attribute(bool)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.ToScenario = _MODELLER.scenario #Default is primary scenario
        self.FromEmmebankPath = _MODELLER.emmebank.path
        self.ClearTargetZonesFlag = False
        self.CoordinateTolerance = 200.0
        self.MatchOption = 1
        self.LinkLengthTolerance = 50.0
        self.FromZonesToIgnoreSelector = "i=9700,9900"
        self.FromScenarioId = 1
        self.OverrideDuplicates = False
        self.PublishNetworkFlag = True
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Copy Zone System v%s" %self.version,
                     description="Copies a zone system (centroids + connectors) from a \
                         source scenario to a target scenario. The source scenario does \
                         not need to be in the same database. Optionally, a shapefile can \
                         be written which contains those connectors that were not able to \
                         be copied from the source to the target.\
                         <br><br>Two options are available for matching connector j-nodes: \
                         <b>GEOMETRY</b> (default), and <b>NODE_ID</b>. GEOMETRY will use the \
                         source node's coordinates to find the nearest target node within \
                         a specified radius. NODE_ID will find the node in the target network \
                         with the same number, to a specified tolerance of link length.\
                         <br><br>Five error types are reported to the Logbook: <ul>\
                         <li><b>'No match (ID)'</b>: The source j-node does not exist \
                             in the target scenario.\
                         <li><b>'No match (Coordinate)'</b>: No target node could be found\
                             within the specified radius of the source j-node.\
                         <li><b>'Flagged to skip'</b>: A j-node was found, but was flagged\
                             to be skipped.\
                         <li><b>'Bad link length'</b>: The new target connector's length is greater\
                             than the source connector's length by the specified margin.\
                         <li><b>'Found overlap'</b>: A connector between the zone and the\
                             found j-node already exists.\
                         </ul>\
                         <br><b>Temporary storage requirements:</b> One node attribute in both\
                         the source and target scenarios.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("SOURCE")
        
        pb.add_select_file(tool_attribute_name='FromEmmebankPath',
                           window_type='file', file_filter='emmebank',
                           title="Source Database",
                           note="Select a source database (can be in another project)")
        
        keyval1 = []
        for scenario in _MODELLER.emmebank.scenarios():
            key = scenario.id
            val = "{0!s} - {1!s}".format(key, scenario.title)
            keyval1.append((key, val))
        pb.add_select(tool_attribute_name='FromScenarioId',
                      keyvalues=keyval1, title="Source Scenario",
                      note="Select a scenario from the source database.")
        
        pb.add_text_box(tool_attribute_name='FromZonesToIgnoreSelector',
                        size=100, multi_line=True,
                        title="Zones to Ignore Selector",
                        note="Emme Network Calculator NODE filter expression to skip over certain \
                            zones in the source scenario.")
        
        pb.add_header("TARGET")
        
        pb.add_select_scenario(tool_attribute_name='ToScenario',
                               title='Target Scenario',
                               allow_none=False,
                               note="Select a target scenario from this database.")
        
        pb.add_text_box(tool_attribute_name='ToNodesToIgnoreSelector',
                        size=100, multi_line=True,
                        title="Nodes to Ignore Selector",
                        note="Emme Network Calculator NODE filter expression to prohibit connecting \
                            to nodes in the target scenario.")
        
        pb.add_header("TOOL OPTIONS")
        
        keyval2 = {1: "GEOMETRY - Match based on node coordinates",
                  2: "NODE_ID - Match based on node IDs"}
        pb.add_select(tool_attribute_name='MatchOption',
                      keyvalues=keyval2,
                      title="Match Method",
                      note="Method to match each connector's j-node in the source to the target.")
        
        pb.add_text_box(tool_attribute_name='LinkLengthTolerance',
                        size=10, title="Link Length Tolerance",
                        note="When using node IDs for matching, skip connectors whose difference in\
                                length is greater than this value (in coordinate units).")
        
        pb.add_text_box(tool_attribute_name='CoordinateTolerance',
                        size=10, title="Coordinate Tolerance",
                        note="When using node coordinates for matching, skip connectors whose \
                                j-node is further from any other node by this value, in coordinate units.")
        
        pb.add_select_file(tool_attribute_name='ShapefileReport',
                           window_type='save_file', file_filter='*.shp',
                           title="Shapefile Report",
                           note="<font color='green'><b>Optional:</b></font> \
                                   a file to save the shapes of connectors \
                                    which could not be copied across.")
        
        pb.add_checkbox(tool_attribute_name='ClearTargetZonesFlag',
                        label="Flag to remove all existing zones from the target network")
        
        pb.add_checkbox(tool_attribute_name='OverrideDuplicates',
                        label="Flag to override duplicate zones in the target network.",
                        note="Otherwise, an error will be raised when duplicates are found.")
        
        pb.add_checkbox(tool_attribute_name='PublishNetworkFlag',
                        label="Flag to publish the network.",
                        note="Unflag to discard changes.")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#FromEmmebankPath").bind('change', function()
        {
            $(this).commit();
            $("#FromScenarioId")
                .empty()
                .append(tool.loadSourceDatabaseScenarios())
            inro.modeller.page.preload("#FromScenarioId");
            $("#FromScenarioId").trigger('change')
        });
        
        $("#MatchOption").bind('change', function()
        {
            $(this).commit();
            if ($(this).val() == 1)
            {
                $("#LinkLengthTolerance").parent().parent().hide();
                $("#CoordinateTolerance").parent().parent().show();
            } else {
                $("#LinkLengthTolerance").parent().parent().show();
                $("#CoordinateTolerance").parent().parent().hide();
            }
        });
        
        $("#MatchOption").trigger('change');
        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        self.MatchOption = int(self.MatchOption)
        
        try:
            if self.FromEmmebankPath is None: raise NullPointerException("Source emmebank not specified")
            if self.FromScenarioId is None: raise NullPointerException("Source scenario not specified")
            
            if self.MatchOption == 1:
                if self.CoordinateTolerance is None: raise NullPointerException("Coordinate tolerance not specified")
            else:
                if self.LinkLengthTolerance is None: raise NullPointerException("Link length tolerance not specified")
            
            if self.ClearTargetZonesFlag is None: self.ClearTargetZonesFlag = False
            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):           
            
            self.TRACKER.startProcess(5)
            with _m.logbook_trace("Loading scenarios and applying node filters"):
                #---Load the source network
                sourceBank = Emmebank(self.FromEmmebankPath)
                try:
                    sourceScenario = sourceBank.scenario(self.FromScenarioId)
                    if sourceScenario is None:
                        #Check, because the scenario could've been deleted in between the time
                        #that the list of scenarios was extracted, and the time that this tool
                        #is running
                        raise Exception("Scenario %s no longer exists" %self.FromScenarioId)
                    
                    with _util.tempExtraAttributeMANAGER(sourceScenario, 'NODE') as sourceTempAtt:
                        if self.FromZonesToIgnoreSelector:
                            self._ApplySelector(sourceScenario, sourceTempAtt, self.FromZonesToIgnoreSelector)
                        self.TRACKER.completeSubtask()
                        
                        sourceNetwork = sourceScenario.get_network()
                        self.TRACKER.completeSubtask()
                finally:
                    if self.FromEmmebankPath != _MODELLER.emmebank.path:
                        sourceBank.dispose()
                
                
                
                #---Load the target network
                with _util.tempExtraAttributeMANAGER(self.ToScenario, 'NODE') as targetTempAtt:
                    if self.ToNodesToIgnoreSelector:
                        self._ApplySelector(self.ToScenario, targetTempAtt, self.ToNodesToIgnoreSelector)
                    self.TRACKER.completeSubtask()
                    
                    targetNetwork = self.ToScenario.get_network()
                    self.TRACKER.completeSubtask()
            
            #---Determine the attributes to copy over
            attsToCopy = self._DetermineAttributesToCopy(sourceNetwork, targetNetwork)
            self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            #---Get the source nodes to be copied
            zonesToCopy = [zone for zone in sourceNetwork.centroids() if zone[sourceTempAtt.id] == 0]          
            _m.logbook_write("Found %s zones to copy over." %len(zonesToCopy))
            
            #---Clear un-flagged zones from the target network
            if self.ClearTargetZonesFlag:
                with _m.logbook_trace("Clearing zones from target network"):
                    zonesToDelete = [zone.number for zone in targetNetwork.centroids()]
                    for id in zonesToDelete: targetNetwork.delete_node(id, cascade=True)
                    _m.logbook_write("%s zones deleted from target network" %len(zonesToDelete)) 
            
            #---Run the matching process
            if self.MatchOption == 1:
                message = "Copying zones using node coordinates"
                func = self._GetMatchByGeometryLambda(targetNetwork)
            elif self.MatchOption == 2:
                message = "Copying zones using node IDs"
                func = self._GetMatchByIdLambda(targetNetwork)
            else:
                raise KeyError("Unrecognized match option", self.MatchOption)
            with _m.logbook_trace(message):
                count, uncopiedConnectors = self._NewCopyZones(zonesToCopy, targetNetwork, targetTempAtt, attsToCopy, func)
                self._WriteLogbookReport(uncopiedConnectors)                
            
            _m.logbook_write("Copied over %s connectors from source scenario" %count)
            _m.logbook_write("%s connectors could not be copied" %len(uncopiedConnectors))
            
            #---Write  shapefile
            if len(uncopiedConnectors) > 0 and self.ShapefileReport:
                self._WriteShapefile(uncopiedConnectors)
                _m.logbook_write("Wrote shapefile to %s" %self.ShapefileReport)
            self.TRACKER.completeTask()
            
            #---Publish the network
            if self.PublishNetworkFlag:
                self.ToScenario.publish_network(targetNetwork, True)
                _MODELLER.desktop.refresh_needed(True)
            self.TRACKER.completeTask()
            

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Source Emmebank": self.FromEmmebankPath,
                "Source Scenario": self.FromScenarioId,
                "Zones to Ignore Selector": self.FromZonesToIgnoreSelector,
                "Nodes to Ignore Selector": self.ToNodesToIgnoreSelector,
                "Match Option": {1: 'GEOMETRY', 2: 'NODE_ID'}[self.MatchOption],
                "Target Scenario": str(self.ToScenario),
                "Link Length Tolerance": str(self.LinkLengthTolerance),
                "Coordinate Tolerance": str(self.CoordinateTolerance),
                "Shapefile Report": self.ShapefileReport,
                "Clear Target Zones": str(self.ClearTargetZonesFlag),
                "Override Duplicate Zones": str(self.OverrideDuplicates),
                "Publish Network": str(self.PublishNetworkFlag),  
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    
    def _ApplySelector(self, scenario, att, filterExpression):
        netCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
        spec = {
                        "result": att.id,
                        "expression": "1",
                        "aggregation": None,
                        "selections": {
                            "node": filterExpression
                        },
                        "type": "NETWORK_CALCULATION"
                    }
        netCalcTool(spec, scenario)
    
    def _DetermineAttributesToCopy(self, sourceNetwork, targetNetwork):
        sourceAttributes = set(sourceNetwork.attributes('LINK'))
        targetAttributes = set(targetNetwork.attributes('LINK'))
        
        attsNotInTarget = sourceAttributes - targetAttributes
        attsNotInSource = targetAttributes - sourceAttributes
        
        if len(attsNotInSource) > 0:
            with _m.logbook_trace("Attributes in target but not in source scenario"):
                for att in attsNotInSource: _m.logbook_write(att)
                _m.logbook_write("The attributes will not be copied")
        
        if len(attsNotInTarget) > 0:
            with _m.logbook_trace("Attributes in source but not in target scenario"):
                for att in attsNotInTarget: _m.logbook_write(att)
                _m.logbook_write("The attributes will not be copied")
        
        return sourceAttributes & targetAttributes
    
    def _GetMatchByIdLambda(self, targetNetwork):
        coordFactor = _MODELLER.emmebank.coord_unit_length
        def distance(node1, node2):
            dx = node2.x - node1.x
            dy = node2.y - node1.y
            return sqrt(dx*dx + dy*dy) * coordFactor
        
        def func(connector, flagAtt, uncopiedConnectors):
            source_jNodeId = connector.j_node.number
            target_jNode = targetNetwork.node(source_jNodeId)
            
            if target_jNode is None:
                uncopiedConnectors.append((connector, "No match (ID)"))
                return None
            
            if target_jNode[flagAtt.id]:
                uncopiedConnectors.append((connector, "Flagged to skip"))
                return None
            
            dist = distance(connector.j_node, target_jNode)
            if abs(dist - connector.length) > self.LinkLengthTolerance:
                 uncopiedConnectors.append((connector, "Bad link length"))
                 return None
             
            return target_jNode
        return func
    
    def _GetMatchByGeometryLambda(self, targetNetwork):
        extents = _spindex.get_network_extents(targetNetwork)
        grid = _spindex.GridIndex(extents, marginSize= 1.0)
        
        for node in targetNetwork.regular_nodes():
            grid.insertPoint(node)
        
        def func(connector, flagAtt, uncopiedConnectors):
            zone = connector.i_node
            source_jNode = connector.j_node
            
            targetCandidates = grid.queryCircle(source_jNode.x, source_jNode.y, self.CoordinateTolerance)
            target_jNode = None
            minDistance = float('inf')
            for node in targetCandidates:
                dx = node.x - source_jNode.x
                dy = node.y - source_jNode.y
                d = sqrt(dx * dx + dy * dy)
                if d < minDistance:
                    target_jNode = node
                    minDistance = d
            
            if target_jNode is None:
                uncopiedConnectors.append((connector, "No match (Coordinate)"))
                return None
            
            if target_jNode[flagAtt.id]:
                uncopiedConnectors.append((connector, "Flagged to skip"))
                return None
            
            if targetNetwork.link(zone.number, target_jNode.number) is not None:
                uncopiedConnectors.append((connector, "Found overlap"))
                return None
            
            return target_jNode
        return func
        
    def _NewCopyZones(self, zonesToCopy, targetNetwork, flagAtt, atts, getJNodeLambda):
        uncopiedConnectors = []
        
        self.TRACKER.startProcess(len(zonesToCopy))
        count = 0
        for zone in zonesToCopy:            
            targetZone = targetNetwork.node(zone.number)
            if targetZone is not None:
                if self.OverrideDuplicates:
                    targetNetwork.delete_node(zone.number, cascade=True)
                    targetZone = targetNetwork.create_centroid(zone.number)
                    targetZone.x = zone.x
                    targetZone.y = zone.y
                else:
                    raise Exception("Zone %s already exists" %zone.number)
            else:
                targetZone = targetNetwork.create_centroid(zone.number)
                targetZone.x = zone.x
                targetZone.y = zone.y
            
            for connector in zone.outgoing_links():
                target_jNode = getJNodeLambda(connector, flagAtt, uncopiedConnectors)
                if target_jNode is None: continue #The lambda handles adding to uncopiedConnectors
                
                try:
                    self._copyConnector(connector, targetNetwork, zone.number, target_jNode.number, atts)
                    count += 1
                except Exception, e:
                    uncopiedConnectors.append((connector, str(e)))                
                
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        return count, uncopiedConnectors
    
    @staticmethod
    def _copyConnector(sourceConnector, targetNetwork, new_i, new_j, atts):
        newConnector = targetNetwork.create_link(new_i, new_j, sourceConnector.modes)
        for att in atts:
            newConnector[att] = sourceConnector[att]
        newConnector.vertices = [v for v in sourceConnector.vertices]
        
        #Now copy the reverse
        sourceReverse = sourceConnector.reverse_link
        if sourceReverse is not None:
            newReverse = targetNetwork.create_link(new_j, new_i, sourceReverse.modes)
            for att in atts: newReverse[att] = sourceReverse[att]
            newReverse.vertices = [v for v in sourceReverse.vertices]
    
    def _WriteLogbookReport(self, uncopiedConnectors):
        pb = _m.PageBuilder(title="Error Report", 
                            description="Lists connectors in the source scenario which could not be \
                                copied over to the target scenario.")
        
        html = """<table>
<tr>
    <th>Source I-Node (Zone)</th>
    <th>Source J-Node</th>
    <th>Error Message</th>
</tr>"""
        for connector, errMessage in uncopiedConnectors:
            tup = (connector.i_node, connector.j_node, errMessage)
            html += "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" %tup
        html += "</table>"
        
        pb.wrap_html("", html, "")
        
        _m.logbook_write("Error report", value=pb.render())
    
    def _WriteShapefile(self, uncopiedConnectors):
        
        self.TRACKER.startProcess(len(uncopiedConnectors))
        with Shapely2ESRI(self.ShapefileReport, 'w', 'LINESTRING') as writer:
            writer.addField('ZONE', fieldType= 'INT')
            writer.addField('jNode', fieldType= 'INT')
            writer.addField('error', fieldType= 'STR')
            
            for connector, errorMessage in uncopiedConnectors:
                coordinates = [(connector.i_node.x, connector.i_node.y)]
                coordinates.extend(connector.vertices)
                coordinates.append((connector.j_node.x, connector.j_node.y))
                
                ls = _geolib.LineString(coordinates)
                ls['ZONE'] = int(connector.i_node.number)
                ls['jNode'] = int(connector.j_node.number)
                ls['error'] = str(errorMessage)
                
                writer.writeNext(ls)
                self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def loadSourceDatabaseScenarios(self):
        emmebank = Emmebank(self.FromEmmebankPath)
        
        options = []
        for scenario in emmebank.scenarios():
            text = "%s - %s" %(scenario.id, scenario.title)
            options.append('<option value="%s">%s</option>' %(scenario.id, text))
        
        emmebank.dispose()
        return "\n".join(options)
    