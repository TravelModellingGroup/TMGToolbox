#---LICENSE----------------------
'''
    Copyright 2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Fare-Based Transit Network (FBTN) From Schema

    Authors: pkucirek

    Latest revision by: mattaustin222
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-09 by pkucirek
    
    1.0.0 Debugged and deployed by 2014-05-23
    
    1.1.0 Added feature to save base I-node IDs for transit segments
        as they are being moved over to the hyper network. This enables
        transit speed updating.
    
    1.1.1 Fixed a bug in PrepareNetwork which only considers segments that permit alightings as 
        'stops.' We want to catch both boardings AND alightings
    
    1.1.2 Slightly tweaked the page() function's Javascript to allow the NONE option when segment
        attributes are pre-loaded from scenario.
        
    1.1.3 Slightly tweaked to over-write the FBTN scenario if it already exists.
    
    1.1.4 Fixed a bug in the scenario overwrite: If the target (new) scenario already exists,
        it gets deleted, then the base scenario is copied in its place first. This ensures that
        the new scenario is a verbatim copy of the base scenario prior to publishing the network.
        Before, it was possible to end up with different extra attributes between the two 
        scenarios.
        
    1.1.5 Modified to use the new spatial index. Also changed the copy scenario call to NOT
        copy over strategy or path files as this considerably increases runtime.
    
    1.2.0 Added new feature to accept relative paths for shapefiles. Absolute paths are still
        supported.
    
    1.3.0 Added new feature to associate a set of station zones with line group. Initial boarding rules
        will then be applied to all centroid connectors going from station zones to a stop of that
        operator.
        
    1.3.1 Minor change to accept two station groups being associated with a shared line group

    1.4.0 Added option to allow station-to-centroid hypernetwork connections by default. This 
        enables the proper connection of a centroid to a multi-operator station. The station group
        method allows for finer control of centroids, but cannot handle multiple operators at 
        a station. 
    
'''
from copy import copy
from contextlib import contextmanager
from contextlib import nested
from html import HTML
from itertools import combinations as get_combinations
from os import path
import traceback as _traceback
from xml.etree import ElementTree as _ET

import inro.modeller as _m
from inro.emme.core.exception import ModuleError

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geolib = _MODELLER.module('tmg.common.geometry')
_editing = _MODELLER.module('tmg.common.network_editing')
_spindex = _MODELLER.module('tmg.common.spatial_index')
Shapely2ESRI = _geolib.Shapely2ESRI
GridIndex = _spindex.GridIndex
TransitLineProxy = _editing.TransitLineProxy
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple) 

##########################################################################################################    

class XmlValidationError(Exception):
    pass

class grid():
    '''
    Grid class to support tuple indexing (just for coding convenience).
    
    Upon construction, it copies the default value into each of its cells.
    '''
    
    def __init__(self, x_size, y_size, default= None):
        x_size, y_size = int(x_size), int(y_size)
        self._data = []
        self.x = x_size
        self.y = y_size
        i = 0
        total = x_size * y_size
        while i < total:
            self._data.append(copy(default))
            i += 1
    
    def __getitem__(self, key):
        x,y = key
        x, y = int(x), int(y)
        index = x * self.y + y
        return self._data[index]
    
    def __setitem__(self, key, val):
        x,y = key
        x, y = int(x), int(y)
        index = x * self.y + y
        self._data[index] = val

class NodeSpatialProxy():
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y
        self.zone = 0
        self.geometry = _geolib.Point(x,y)
    
    def __str__(self):
        return str(self.id)
        

#---
#---MAIN MODELLER TOOL--------------------------------------------------------------------------------

class FBTNFromSchema(_m.Tool()):
    
    version = '1.4.0'
    tool_run_msg = ""
    number_of_tasks = 5 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    XMLSchemaFile = _m.Attribute(str)
    VirtualNodeDomain = _m.Attribute(int)
    
    xtmf_BaseScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    BaseScenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    NewScenarioNumber = _m.Attribute(int)
    NewScenarioTitle = _m.Attribute(str)
    
    TransferModeId = _m.Attribute(str) 
    SegmentFareAttributeId = _m.Attribute(str)
    LinkFareAttributeId = _m.Attribute(str)
    SegmentINodeAttributeId = _m.Attribute(str)

    StationConnectorFlag = _m.Attribute(bool)
    
    __ZONE_TYPES = ['node_selection', 'from_shapefile']
    __RULE_TYPES = ['initial_boarding', 
                    'transfer',
                    'in_vehicle_distance',
                    'zone_crossing']
    __BOOL_PARSER = {'TRUE': True, 'T': True, 'FALSE': False, 'F': False}
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        self.VirtualNodeDomain = 100000
        self.NewScenarioTitle = ""
        
        self.LinkFareAttributeId = "@lfare"
        self.SegmentFareAttributeId = "@sfare"

        self.StationConnectorFlag = True
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="FBTN From Schema v%s" %self.version,
                     description="Generates a hyper-network to support fare-based transit \
                     assignment (FBTA), from an XML schema file. Links and segments with negative\
                     fare values will be reported to the Logbook for further inspection. \
                     For fare schema specification, \
                     please consult TMG documentation.\
                     <br><br><b>Temporary storage requirements:</b> one transit line extra \
                     attribute, one node extra attribute.\
                     <br><br><em>Tip: To view tool progress messages in real-time, press CTRL+K to \
                     open the Python Console.</em>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_file(tool_attribute_name='XMLSchemaFile', window_type='file',
                           file_filter="*.xml", title="Fare Schema File")
        
        pb.add_header("SCENARIO")
        
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_new_scenario_select(tool_attribute_name='NewScenarioNumber',
                                   title="New Scenario Id")
        
        pb.add_text_box(tool_attribute_name='NewScenarioTitle',
                        title= "New Scenario Title", size=60)
        
        pb.add_header("OPTIONS AND RESULTS")
        
        pb.add_text_box(tool_attribute_name= 'VirtualNodeDomain', size=10,
                        title= "Virtual Node Domain",
                        note= "All virtual node IDs created will be greater than \
                        this number.")
        
        keyval1 = []
        for id, type, description in _util.getScenarioModes(self.BaseScenario, ['AUX_TRANSIT']):
            val = "%s - %s" %(id, description)
            keyval1.append((id, val))
        
        pb.add_select(tool_attribute_name='TransferModeId', keyvalues= keyval1,
                      title="Transfer Mode", 
                      note="Select an AUX_TRANSIT mode to apply to virtual connector links.")
        
        keyval2 = []
        keyval3 = []
        keyval4 = [(-1, "None - Do not save segment base info")]
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type == 'LINK':
                val = "%s - %s" %(exatt.name, exatt.description)
                keyval2.append((exatt.name, val))
            elif exatt.type == 'TRANSIT_SEGMENT':
                val = "%s - %s" %(exatt.name, exatt.description)
                keyval3.append((exatt.name, val))
                keyval4.append((exatt.name, val))
        
        pb.add_select(tool_attribute_name= 'LinkFareAttributeId',
                      keyvalues= keyval2,
                      title= "Link Fare Attribute",
                      note= "Select a LINK extra attribute in which to save \
                      transit fares")
        
        pb.add_select(tool_attribute_name= 'SegmentFareAttributeId',
                      keyvalues= keyval3,
                      title="Segment Fare Attribute",
                      note= "Select a TRANSIT SEGMENT extra attribute in which \
                      to save transit fares.")
        
        pb.add_select(tool_attribute_name= 'SegmentINodeAttributeId',
                      keyvalues= keyval4,
                      title= "Segment I-node Attribute",
                      note= "Select a TRANSIT SEGMENT extra attribute in which \
                      to save the base node ID. This data is used to implement \
                      transit speed updating. Select 'None' to disable this \
                      feature.")
        
        pb.add_checkbox(tool_attribute_name= 'StationConnectorFlag',
                        label= "Allow station-to-centroid connections?")                      
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        $("#BaseScenario").bind('change', function()
        {
            $(this).commit();
            
            $("#TransferModeId")
                .empty()
                .append(tool.preload_auxtr_modes())
            inro.modeller.page.preload("#TransferModeId");
            $("#TransferModeId").trigger('change')
            
            $("#LinkFareAttributeId")
                .empty()
                .append(tool.preload_scenario_link_attributes())
            inro.modeller.page.preload("#LinkFareAttributeId");
            $("#LinkFareAttributeId").trigger('change')
            
            $("#SegmentFareAttributeId")
                .empty()
                .append(tool.preload_scenario_segment_attributes())
            inro.modeller.page.preload("#SegmentFareAttributeId");
            $("#SegmentFareAttributeId").trigger('change')
            
            $("#SegmentINodeAttributeId")
                .empty()
                .append("<option value='-1'>None - Do not save segment base info</option>")
                .append(tool.preload_scenario_segment_attributes())
            inro.modeller.page.preload("#SegmentINodeAttributeId");
            $("#SegmentINodeAttributeId").trigger('change')
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if not self.XMLSchemaFile: raise NullPointerException("Fare Schema file not specified")
        if not self.VirtualNodeDomain: raise NullPointerException("Virtual Node Domain not specified")
        if not self.LinkFareAttributeId: raise NullPointerException("Link fare attribute not specified")
        if not self.SegmentFareAttributeId: raise NullPointerException("Segment fare attribute not specified")
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    
    @_m.method(return_type= bool)
    def check_415(self):
        if EMME_VERSION >= (4,1,5):
            return True
        return False
        
    def __call__(self, XMLSchemaFile, xtmf_BaseScenarioNumber, NewScenarioNumber,
                 TransferModeId, SegmentFareAttributeId, LinkFareAttributeId, 
                 VirtualNodeDomain, StationConnectorFlag):
        
        #---1 Set up scenario
        self.BaseScenario = _MODELLER.emmebank.scenario(xtmf_BaseScenarioNumber)
        if (self.BaseScenario is None):
            raise Exception("Base scenario %s was not found!" %xtmf_BaseScenarioNumber)
        
        if self.BaseScenario.extra_attribute(SegmentFareAttributeId) is None:
            att = self.BaseScenario.create_extra_attribute('TRANSIT_SEGMENT',
                                                           SegmentFareAttributeId)
            att.description = "SEGMENT transit fare"
            _m.logbook_write("Created segment fare attribute %s" %SegmentFareAttributeId)
            
        if self.BaseScenario.extra_attribute(LinkFareAttributeId) is None:
            att = self.BaseScenario.create_extra_attribute('LINK',
                                                           LinkFareAttributeId)
            att.description = "LINK transit fare"
            _m.logbook_write("Created link fare attribute %s" %LinkFareAttributeId)
        
        self.XMLSchemaFile = XMLSchemaFile
        self.NewScenarioNumber = NewScenarioNumber
        self.NewScenarioTitle = self.BaseScenario.title + " - FBTN"
        self.TransferModeId = TransferModeId
        self.SegmentFareAttributeId = SegmentFareAttributeId
        self.LinkFareAttributeId = LinkFareAttributeId
        self.VirtualNodeDomain = VirtualNodeDomain
        self.StationConnectorFlag = StationConnectorFlag
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            self._nextNodeId = self.VirtualNodeDomain
            
            root = _ET.parse(self.XMLSchemaFile).getroot()            
            
            #Validate the XML Schema File
            nGroups, nZones, nRules, nStationGroups = self._ValidateSchemaFile(root)
            self.TRACKER.completeTask()
            
            #Load the line groups and zones
            version = root.find('version').attrib['number']
            _m.logbook_write("Loading Fare Schema File version %s" %version)
            print "Loading Fare Schema File version %s" %version
            
            self.TRACKER.startProcess(nGroups + nZones)
            with nested (_util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_LINE', description= "Line Group"),
                         _util.tempExtraAttributeMANAGER(self.BaseScenario, 'NODE', description= "Fare Zone")) \
                     as (lineGroupAtt, zoneAtt):
                
                with _m.logbook_trace("Transit Line Groups"):
                    groupsElement = root.find('groups')
                    groupIds2Int, int2groupIds = self._LoadGroups(groupsElement, lineGroupAtt.id)
                    print "Loaded groups."
                
                stationGroupsElement = root.find('station_groups')
                if stationGroupsElement is not None:
                    with _m.logbook_trace("Station Groups"):
                        stationGroups = self._LoadStationGroups(stationGroupsElement)
                        print "Loaded station groups"
                
                zonesElement = root.find('zones')
                if zonesElement is not None:
                    with _m.logbook_trace("Fare Zones"):
                        zoneId2Int, int2ZoneId, nodeProxies = self._LoadZones(zonesElement, zoneAtt.id)
                        print "Loaded zones."
                else:
                    zoneId2Int, int2ZoneId, nodeProxies = {}, {}, {}
                self.TRACKER.completeTask() #Complete the group/zone loading task
                
                #Load and prepare the network.
                self.TRACKER.startProcess(2)
                network = self.BaseScenario.get_network()
                print "Loaded network."
                self.TRACKER.completeSubtask()
                self._PrepareNetwork(network, nodeProxies, lineGroupAtt.id)
                self.TRACKER.completeTask()
                print "Prepared base network."
            
            #Transform the network
            with _m.logbook_trace("Transforming hyper network"):
                transferGrid, zoneCrossingGrid = self._TransformNetwork(network, nGroups, nZones)
                #print transferGrid[0,1]
                if nStationGroups > 0:
                    self._IndexStationConnectors(network, transferGrid, stationGroups, groupIds2Int)
                print "Hyper network generated."            
            
            #Apply fare rules to network.
            with _m.logbook_trace("Applying fare rules"):
                self.TRACKER.startProcess(nRules + 1)
                fareRulesElement = root.find('fare_rules')
                self._ApplyFareRules(network, fareRulesElement, transferGrid, zoneCrossingGrid,
                                     groupIds2Int, zoneId2Int)
                self._CheckForNegativeFares(network)

                self.TRACKER.completeTask()
                print "Applied fare rules to network."
            
            #Publish the network
            bank = _MODELLER.emmebank
            if bank.scenario(self.NewScenarioNumber) is not None:
                bank.delete_scenario(self.NewScenarioNumber)
            newSc = bank.copy_scenario(self.BaseScenario.id, self.NewScenarioNumber, \
                                       copy_path_files=False, copy_strat_files=False)
            newSc.title = self.NewScenarioTitle
            newSc.publish_network(network, resolve_attributes= True)
            
            _MODELLER.desktop.refresh_needed(True) #Tell the desktop app that a data refresh is required

    ##########################################################################################################     
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    #---
    #---SCHEMA LOADING-----------------------------------------------------------------------------------
    
    def _ValidateSchemaFile(self, root):
        
        #Check the top-level of the file
        versionElem = root.find('version')
        if versionElem is None:
            raise XmlValidationError("Fare schema must specify a 'version' element.")
        
        groupsElement = root.find('groups')
        if groupsElement is None:
            raise XmlValidationError("Fare schema must specify a 'groups' element.")
        
        zonesElement = root.find('zones')
        
        fareRulesElement = root.find('fare_rules')
        if fareRulesElement is None:
            raise XmlValidationError("Fare schema must specify a 'fare_rules' element.")
    
        #Validate version
        try:
            version = versionElem.attrib['number']
        except KeyError:
            raise XmlValidationError("Version element must specify a 'number' attribute.")
        
        #Validate groups
        groupElements = groupsElement.findall('group')
        validGroupIds = set()
        if len(groupElements) == 0:
            raise XmlValidationError("Scehma must specify at least one group elements")
        for i, groupElement in enumerate(groupElements):
            if not 'id' in groupElement.attrib:
                raise XmlValidationError("Group element #%s must specify an 'id' attribute" %i)
            id = groupElement.attrib['id']
            if id in validGroupIds:
                raise XmlValidationError("Group id '%s' found more than once. Each id must be unique." %id)
            validGroupIds.add(id)
            
            selectionElements = groupElement.findall('selection')
            if len(selectionElements) == 0:
                raise XmlValidationError("Group element '%s' does not specify any 'selection' sub-elements" %id)
            
        #Validate zones, if required
        validZoneIds = set()
        if zonesElement is not None:
            shapeFileElements = zonesElement.findall('shapefile')
            zoneElements = zonesElement.findall('zone')
            
            shapeFileIds = set()
            for i, shapefileElement in enumerate(shapeFileElements):
                if not 'id' in shapefileElement.attrib:
                    raise XmlValidationError("Shapefile #%s element must specify an 'id' attribute" %i)
                
                id = shapefileElement.attrib['id']
                if id in shapeFileIds:
                    raise XmlValidationError("Shapefile id '%' found more than once. Each id must be unique" %id)
                shapeFileIds.add(id)
                
                if not 'path' in shapefileElement.attrib:
                    raise XmlValidationError("Sahpefile '%s' must specify a 'path' attribute" %id)
                p = shapefileElement.attrib['path']
                p = self._GetAbsoluteFilepath(p) #Joins the path if it is relative.
                
                if not path.exists(p):
                    raise XmlValidationError("File not found for id '%s' at %s" %(id, p))
            
            for i, zoneElement in enumerate(zoneElements):
                if not 'id' in zoneElement.attrib:
                    raise XmlValidationError("Zone element #%s must specify an 'id' attribute" %i)
                id = zoneElement.attrib['id']
                if id in validZoneIds:
                    raise XmlValidationError("Zone id '%s' found more than once. Each id must be unique" %id)
                validZoneIds.add(id)
                
                if not 'type' in zoneElement.attrib:
                    raise XmlValidationError("Zone '%s' must specify a 'type' attribute" %id)
                zoneType = zoneElement.attrib['type']
                if not zoneType in self.__ZONE_TYPES:
                    raise XmlValidationError("Zone type '%s' for zone '%s' is not recognized." %(zoneType, id))
                
                if zoneType == 'node_selection':
                    if len(zoneElement.findall('node_selector')) == 0:
                        raise XmlValidationError("Zone type 'node_selection' for zone '%s' must specify at least one 'node_selector' element." %id)
                elif zoneType == 'from_shapefile':
                    childElement = zoneElement.find('from_shapefile')
                    if childElement is None:
                        raise XmlValidationError("Zone type 'from_shapefile' for zone '%s' must specify exactly one 'from_shapefile' element." %id)
                    
                    if not 'id' in childElement.attrib:
                        raise XmlValidationError("from_shapefile element must specify an 'id' attribute.")
                    if not 'FID' in childElement.attrib:
                        raise XmlValidationError("from_shapefile element must specify a 'FID' attribute.")
                    
                    sid = childElement.attrib['id']
                    if not sid in shapeFileIds:
                        raise XmlValidationError("Could not find a shapefile with the id '%s' for zone '%s'." %(sid, id))
                    
                    try:
                        FID = int(childElement.attrib['FID'])
                        if FID < 0: raise Exception()
                    except:
                        raise XmlValidationError("FID attribute must be a positive integer.")
        else:
            zoneElements = []
        
        nStationGroups = 0
        stationGroupsElement = root.find('station_groups')
        if stationGroupsElement is not None:
            stationGroupElements = stationGroupsElement.findall('station_group')
            
            for element in stationGroupElements:
                forGroup = element.attrib['for']
                if not forGroup in validGroupIds:
                    raise XmlValidationError("Could not find a group '%s' for to associate with a station group" %forGroup)
                nStationGroups += 1

        fareElements = fareRulesElement.findall('fare')
        
        def checkGroupId(group, name):
            if not group in validGroupIds:
                raise XmlValidationError("Could not find a group with id '%s' for element '%s'" %(group, name))
            
        def checkZoneId(zone, name):
            if not zone in validZoneIds:
                raise XmlValidationError("Could not find a zone with id '%s' for element '%s'" %(zone, name))
            
        def checkIsBool(val, name):
            if not val.upper() in ['TRUE', 'T', 'FALSE', 'F']:
                raise XmlValidationError("Value '%s' for element '%s' must be True or False." %(val, name)) 
        
        for i, fareElement in enumerate(fareElements):
            if not 'cost' in fareElement.attrib:
                raise XmlValidationError("Fare element #%s must specify a 'cost' attribute" %i)
            if not 'type' in fareElement.attrib:
                raise XmlValidationError("Fare element #%s must specify a 'type' attribute" %i)
            
            try:
                cost = float(fareElement.attrib['cost'])
            except ValueError:
                raise XmlValidationError("Fare element #%s attribute 'cost' must be valid decimal number." %i)
            
            ruleType = fareElement.attrib['type']            
            if ruleType == 'initial_boarding':
                requiredChildren = {'group': checkGroupId}
                optionalChildren = {'in_zone': checkZoneId,
                                    'include_all_groups': checkIsBool}
            elif ruleType == 'transfer':
                requiredChildren = {'from_group': checkGroupId,
                                    'to_group': checkGroupId}
                optionalChildren = {'bidirectional': checkIsBool}
            elif ruleType == 'zone_crossing':
                requiredChildren = {'group': checkGroupId,
                                    'from_zone': checkZoneId,
                                    'to_zone': checkZoneId}
                optionalChildren = {'bidirectional': checkIsBool}
            elif ruleType == 'distance_in_vehicle':
                requiredChildren = {'group': checkGroupId}
                optionalChildren = {}
            else:
                raise XmlValidationError("Fare rule type '%s' not recognized." %ruleType)
            
            #Check required children
            for name, checkFunc in requiredChildren.iteritems():
                child = fareElement.find(name)
                if child is None:
                    raise XmlValidationError("Fare element #%s of type '%s' must specify a '%s' element" %(i, ruleType, name))
                
                text = child.text
                checkFunc(text, name)
            
            #Check optional children
            for name, checkFunc in optionalChildren.iteritems():
                child = fareElement.find(name)
                if child is None: continue
                
                text = child.text
                checkFunc(text, name)
        
        return len(groupElements), len(zoneElements), len(fareElements), nStationGroups
    
    def _LoadGroups(self, groupsElement, lineGroupAttId):
        groupIds2Int = {}
        int2groupIds ={}
        
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        def getSpec(number, selection):
            return {
                "result": lineGroupAttId,
                "expression": str(number),
                "aggregation": None,
                "selections": {
                    "transit_line": selection
                },
                "type": "NETWORK_CALCULATION"
            }
        
        for i, groupElement in enumerate(groupsElement.findall('group')):
            groupNumber = i + 1
            
            id = groupElement.attrib['id']
            groupIds2Int[id] = groupNumber
            int2groupIds[groupNumber] = id
            
            for selectionElement in groupElement.findall('selection'):
                selector = selectionElement.text
                spec = getSpec(groupNumber, selector)
                try:
                    tool(spec, scenario= self.BaseScenario)
                except ModuleError:
                    msg = "Emme runtime error processing line group '%s'." %id
                    _m.logbook_write(msg)
                    print msg
            
            msg = "Loaded group %s: %s" %(groupNumber, id)
            print msg
            _m.logbook_write(msg)
            
            self.TRACKER.completeSubtask()
        
        return groupIds2Int, int2groupIds
    
    def _LoadStationGroups(self, stationGroupsElement):
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
        stationGroups, ids = {}, []
        with _util.tempExtraAttributeMANAGER(self.BaseScenario, 'NODE', returnId=True) as attr:
            
            for i, stationGroupElement in enumerate(stationGroupsElement.findall('station_group')):
                forGroup = stationGroupElement.attrib['for']
                selector =  stationGroupElement.attrib['selection']
                
                spec = {
                        "result": attr,
                        "expression": str(i + 1), #Plus one since the attribute is initialized to 0
                        "aggregation": None,
                        "selections": {
                            "node": selector
                        },
                        "type": "NETWORK_CALCULATION"
                    }
                tool(spec, scenario= self.BaseScenario)
                stationGroups[forGroup] = set()
                ids.append(forGroup)
            
            indices, table = self.BaseScenario.get_attribute_values('NODE', [attr])
            for nodeNumber, index in indices.iteritems():
                value = int(table[index])
                if value == 0: continue
                stationGroups[ids[value - 1]].add(nodeNumber)
        
        return stationGroups            
        
    
    def _LoadZones(self, zonesElement, zoneAttributeId):
        '''
        Loads node zone numbers. This is a convoluted process in order to allow
        users to apply zones by BOTH selectors AND geometry. The first method
        applies changes directly to the base scenario, which the second requires
        knowing the node coordindates to work. 
        
        Much of this method (and associated sub-methods) is BLACK MAGIC
        '''
        zoneId2Int = {}
        int2ZoneId = {}
        
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
        shapefiles = self._LoadShapefiles(zonesElement)
        spatialIndex, nodes = self._IndexNodeGeometries()
        
        try:
            for number, zoneElement in enumerate(zonesElement.findall('zone')):
                id = zoneElement.attrib['id']
                typ = zoneElement.attrib['type']
                
                number += 1
                
                zoneId2Int[id] = number
                int2ZoneId[number] = id
                
                if typ == 'node_selection':
                    self._LoadZoneFromSelection(zoneElement, zoneAttributeId, tool, number, nodes)
                elif typ == 'from_shapefile':
                    self._LoadZoneFromGeometry(zoneElement, spatialIndex, shapefiles, number, nodes)
                
                msg = "Loaded zone %s: %s" %(number, id)
                _m.logbook_write(msg)
                print msg
                
                self.TRACKER.completeSubtask()
        finally: #Close the shapefile readers
            for reader in shapefiles.itervalues():
                reader.close()
        
        return zoneId2Int, int2ZoneId, nodes
        
    
    def _LoadShapefiles(self, zonesElement):
        shapefiles = {}
        try:
            for shapefileElement in zonesElement.findall('shapefile'):
                id = shapefileElement.attrib['id']
                pth = shapefileElement.attrib['path']
                pth = self._GetAbsoluteFilepath(pth) #Join the path if it is relative
                
                reader = Shapely2ESRI(pth, 'r')
                reader.open()
                if reader.getGeometryType() != 'POLYGON':
                    raise IOError("Shapefile %s does not contain POLYGONS" %pth)
                
                shapefiles[id] = reader
        except:
            for reader in shapefiles.itervalues():
                reader.close()
            raise
        
        return shapefiles
    
    
    
    def _IndexNodeGeometries(self):
        '''
        Uses get_attribute_values() (Scenario function) to create proxy objects for Emme nodes.
        
        This is done to allow node locations to be loaded IN THE ORDER SPECIFIED BY THE FILE,
        regardless of whether those nodes are specified by a selector or by geometry. 
        '''
        indices, xtable, ytable = self.BaseScenario.get_attribute_values('NODE', ['x', 'y'])
        
        extents = min(xtable), min(ytable), max(xtable), max(ytable)
        
        spatialIndex = GridIndex(extents, marginSize= 1.0)
        proxies = {}
        
        for nodeNumber, index in indices.iteritems():
            x = xtable[index]
            y = ytable[index]
            
            #Using a proxy class defined in THIS file, because we don't yet
            #have the full network loaded.
            nodeProxy = NodeSpatialProxy(nodeNumber, x, y)
            spatialIndex.insertPoint(nodeProxy)
            proxies[nodeNumber] = nodeProxy
        
        return spatialIndex, proxies
    
    def _LoadZoneFromSelection(self, zoneElement, zoneAttributeId, tool, number, nodes):
        id = zoneElement.attrib['id']
        
        for selectionElement in zoneElement.findall('node_selector'):
            spec = {
                    "result": zoneAttributeId,
                    "expression": str(number),
                    "aggregation": None,
                    "selections": {
                        "node": selectionElement.text
                    },
                    "type": "NETWORK_CALCULATION"
                }
            
            try:
                tool(spec, scenario= self.BaseScenario)
            except ModuleError, me:
                raise IOError("Error loading zone '%s': %s" %(id, me))
        
        #Update the list of proxy nodes with the network's newly-loaded zones attribute
        indices, table = self.BaseScenario.get_attribute_values('NODE', [zoneAttributeId])
        for number, index in indices.iteritems():
            nodes[number].zone = table[index]
    
    def _LoadZoneFromGeometry(self, zoneElement, spatialIndex, shapefiles, number, nodes):
        id = zoneElement.attrib['id']
        
        for fromShapefileElement in zoneElement.findall('from_shapefile'):
            sid = fromShapefileElement.attrib['id']
            fid = int(fromShapefileElement.attrib['FID'])
            
            reader = shapefiles[sid]
            polygon = reader.readFrom(fid)
            
            nodesToCheck = spatialIndex.queryPolygon(polygon)
            for proxy in nodesToCheck:
                point = proxy.geometry
                
                if polygon.intersects(point):
                    proxy.zone = number
    
    def _GetAbsoluteFilepath(self, otherPath):
        '''
        For the shapefile path, this function checks if it is a relative path or not.
        If it is a relative path, it returns a valid absolute path based on the
        location of the XML Schema File.
        '''
        if path.isabs(otherPath):
            return otherPath
        
        return path.join(path.dirname(self.XMLSchemaFile), otherPath)
    
    
    #---
    #---HYPER NETWORK GENERATION--------------------------------------------------------------------------
    
    def _PrepareNetwork(self, network, nodeProxies, lineGroupAttId):
        '''
        Prepares network attributes for transformation
        '''
        
        network.create_attribute('TRANSIT_LINE', 'group', 0)
        network.create_attribute('NODE', 'passing_groups', None) #Set of groups passing through but not stopping at the node
        network.create_attribute('NODE', 'stopping_groups', None) #Set of groups stopping at the node
        network.create_attribute('NODE', 'fare_zone', 0) #The number of the fare zone
        network.create_attribute('NODE', 'to_hyper_node', None) #Dictionary to get from the node to its hyper nodes
        network.create_attribute('LINK', 'role', 0) #Link topological role
        network.create_attribute('NODE', 'role', 0) #Node topological role
        
        #Initialize node attributes (incl. copying node zone)
        #Also, copy the zones loaded into the proxies
        for node in network.regular_nodes():
            node.passing_groups = set()
            node.stopping_groups = set()
            node.to_hyper_node = {}
            
            if node.number in nodeProxies:
                proxy = nodeProxies[node.number]
                node.fare_zone = proxy.zone
        
        #Determine stops & assign operators to nodes
        for line in network.transit_lines():
            group = int(line[lineGroupAttId])
            line.group = group
            
            for segment in line.segments(True):
                iNode = segment.i_node
                if segment.allow_boardings or segment.allow_alightings:
                    iNode.stopping_groups.add(group)
                    if group in iNode.passing_groups: iNode.passing_groups.remove(group)
                else:
                    if not group in iNode.stopping_groups: iNode.passing_groups.add(group)
        
        #Put this into a function to be able to break from deep loops using return
        def applyNodeRole(node):
            if not node.stopping_groups and not node.passing_groups:
                if node.is_centroid == False:
                    node.role = 1 #  Surface node without transit
                return #Skip nodes without an incident transit segment
            
            for link in node.outgoing_links():
                if link.i_node.is_centroid or link.j_node.is_centroid: continue
                for mode in link.modes:
                    if mode.type == 'AUTO':
                        node.role = 1 #Surface node
                        return
            for link in node.incoming_links():
                if link.i_node.is_centroid or link.j_node.is_centroid: continue
                for mode in link.modes:
                    if mode.type == 'AUTO':
                        node.role = 1 #Surface node
                        return
            node.role = 2 #Station node is a transit stop, but does NOT connect to any auto links

        #Determine node role. This needs to be done AFTER stops have been identified
        for node in network.regular_nodes(): applyNodeRole(node)
            
        #Determine link role. Needs to happen after node role's have been identified
        for link in network.links():
            i, j = link.i_node, link.j_node
            if i.is_centroid or j.is_centroid: continue #Link is a centroid connector    
            
            permitsWalk = False
            for mode in link.modes:
                if mode.type == 'AUX_TRANSIT': 
                    permitsWalk = True
                    break
            
            if i.role == 1 and j.role == 2 and permitsWalk: link.role = 1 #Station connector (access)
            elif i.role == 2 and j.role == 1 and permitsWalk: link.role = 1 #Station connector (egress)
            elif i.role == 2 and j.role == 2 and permitsWalk: link.role = 2 #Station transfer

    def _TransformNetwork(self, network, numberOfGroups, numberOfZones):
        
        totalNodes0 = network.element_totals['regular_nodes']
        totalLinks0 = network.element_totals['links']
        
        baseSurfaceNodes = []
        baseStationNodes = []
        for node in network.regular_nodes():
            if node.role == 1: baseSurfaceNodes.append(node)
            elif node.role == 2: baseStationNodes.append(node)
        
        transferGrid = grid(numberOfGroups + 1, numberOfGroups + 1, set())
        zoneCrossingGrid = grid(numberOfZones + 1, numberOfZones + 1, set())
        
        transferMode = network.mode(self.TransferModeId)
        
        lineIds = [line.id for line in network.transit_lines()]
        
        nTasks = 2 * (len(baseSurfaceNodes) + len(baseStationNodes)) + len(lineIds)
        self.TRACKER.startProcess(nTasks)
        for i, node in enumerate(baseSurfaceNodes):
            self._TransformSurfaceNode(node, transferGrid, transferMode)
            self.TRACKER.completeSubtask()
        
        print "Processed surface nodes"
        totalNodes1 = network.element_totals['regular_nodes']
        totalLinks1 = network.element_totals['links']
        _m.logbook_write("Created %s virtual road nodes." %(totalNodes1 - totalNodes0))
        _m.logbook_write("Created %s access links to virtual road nodes" %(totalLinks1 - totalLinks0))
        
        for i, node in enumerate(baseStationNodes):
            self._TransformStationNode(node, transferGrid, transferMode)
            self.TRACKER.completeSubtask()
        
        print "Processed station nodes"
        totalNodes2 = network.element_totals['regular_nodes']
        totalLinks2 = network.element_totals['links']
        _m.logbook_write("Created %s virtual transit nodes." %(totalNodes2 - totalNodes1))
        _m.logbook_write("Created %s access links to virtual transit nodes" %(totalLinks2 - totalLinks1))
        
        for node in baseSurfaceNodes:
            self._ConnectSurfaceOrStationNode(node, transferGrid)
            self.TRACKER.completeSubtask()
        for node in baseStationNodes:
            self._ConnectSurfaceOrStationNode(node, transferGrid)
            self.TRACKER.completeSubtask()
        
        print "Connected surface and station nodes"
        totalLinks3 = network.element_totals['links']
        _m.logbook_write("Created %s road-to-transit connector links" %(totalLinks3 - totalLinks2))
        
        if self.SegmentINodeAttributeId is not None:
            def saveFunction(segment, iNodeId):
                segment[self.SegmentINodeAttributeId] = iNodeId
        else:
            def saveFunction(segment, iNodeId):
                pass
        
        for lineId in lineIds:
            self._ProcessTransitLine(lineId, network, zoneCrossingGrid, saveFunction)
            self.TRACKER.completeSubtask()
        
        print "Processed transit lines"
        totalLinks4 = network.element_totals['links']
        _m.logbook_write("Created %s in-line virtual links" %(totalLinks4 - totalLinks3))
        
        self.TRACKER.completeTask()
        
        return transferGrid, zoneCrossingGrid
    
    def _GetNewNodeNumber(self, network, baseNodeNumber):
        testNode = network.node(self._nextNodeId)
        while testNode is not None:
            self._nextNodeId += 1
            testNode = network.node(self._nextNodeId)
        return self._nextNodeId
    
    def _TransformSurfaceNode(self, baseNode, transferGrid, transferMode):
        network = baseNode.network
        
        '''
        NOTE TO SELF: When copying attributes to new nodes, REMEMBER that the
        the "special" attributes created in _PrepareNetwork(...) get copied
        as well! This includes pointers to objects - specifically Dictionaries -
        so UNDER NO CIRCUMSTANCES modify a copy's 'to_hyper_network' attribute
        since that modifies the base's dictionary as well.
        '''
        
        createdNodes = []
        linksCreated = 0
        
        #Create the virtual nodes for stops
        for groupNumber in baseNode.stopping_groups:
            newNode = network.create_regular_node(self._GetNewNodeNumber(network, baseNode.number))
            
            #Copy the node attributes, including x, y coordinates
            for att in network.attributes('NODE'):
                newNode[att] = baseNode[att]
            #newNode.label = "RS%s" %int(groupNumber)
            newNode.label = baseNode.label
            
            
            #Attach the new node to the base node for later
            baseNode.to_hyper_node[groupNumber] = newNode
            createdNodes.append((newNode, groupNumber))
            
            #Connect base node to operator node
            inBoundLink = network.create_link(baseNode.number, newNode.number, [transferMode])
            outBoundLink = network.create_link(newNode.number, baseNode.number, [transferMode])
            linksCreated += 2
            
            #Attach the transfer links to the grid for indexing
            transferGrid[0, groupNumber].add(inBoundLink)
            transferGrid[groupNumber, 0].add(outBoundLink)
        
        #Connect the virtual nodes to each other
        for tup_a, tup_b in get_combinations(createdNodes, 2): #Iterate through unique pairs of nodes
            node_a, group_a = tup_a
            node_b, group_b = tup_b
            link_ab = network.create_link(node_a.number, node_b.number, [transferMode])
            link_ba = network.create_link(node_b.number, node_a.number, [transferMode])
            linksCreated += 2
            
            transferGrid[group_a, group_b].add(link_ab)
            transferGrid[group_b, group_a].add(link_ba)
        
        #Create any virtual non-stop nodes
        for groupNumber in baseNode.passing_groups:
            newNode = network.create_regular_node(self._GetNewNodeNumber(network, baseNode.number))
            
            #Copy the node attributes, including x, y coordinates
            for att in network.attributes('NODE'):
                newNode[att] = baseNode[att]
            #newNode.label = "RP%s" %int(groupNumber)
            newNode.label = baseNode.label
            
                
            #Attach the new node to the base node for later
            baseNode.to_hyper_node[groupNumber] = newNode
            
            #Don't need to connect the new node to anything right now
        
    def _TransformStationNode(self,  baseNode, transferGrid, transferMode):
        network = baseNode.network
        
        virtualNodes = []
        
        #Catalog and classify inbound and outbound links for copying
        outgoingLinks = []
        incomingLinks = []
        outgoingConnectors = []
        incomingConnectors = []
        for link in baseNode.outgoing_links():
            if link.role == 1:
                outgoingLinks.append(link)
            elif link.j_node.is_centroid: 
                if self.StationConnectorFlag:
                    outgoingLinks.append(link)
                else:
                    outgoingConnectors.append(link)
        for link in baseNode.incoming_links():
            if link.role == 1:
                incomingLinks.append(link)
            elif link.i_node.is_centroid:
                if self.StationConnectorFlag:
                    incomingLinks.append(link)
                else:
                    incomingConnectors.append(link)
        
        first = True
        for groupNumber in baseNode.stopping_groups:
            if first:
                #Assign the existing node to the first group
                baseNode.to_hyper_node[groupNumber] = baseNode
                virtualNodes.append((baseNode, groupNumber))
                
                #Index the incoming and outgoing links to the Grid
                for link in incomingLinks: transferGrid[0, groupNumber].add(link)
                for link in outgoingLinks: transferGrid[groupNumber, 0].add(link)
                
                first = False
                #baseNode.label = "TS%s" %int(groupNumber)
                
            else:
                virtualNode = network.create_regular_node(self._GetNewNodeNumber(network, baseNode.number))
            
                #Copy the node attributes, including x, y coordinates
                for att in network.attributes('NODE'): virtualNode[att] = baseNode[att]
                #virtualNode.label = "TS%s" %int(groupNumber)
                virtualNode.label = baseNode.label
                
                #Assign the new node to its group number
                baseNode.to_hyper_node[groupNumber] = virtualNode    
                virtualNodes.append((virtualNode, groupNumber))
                
                #Copy the base node's existing centroid connectors to the new virtual node
                if not self.StationConnectorFlag:
                    for connector in outgoingConnectors:
                        newLink = network.create_link(virtualNode.number, connector.j_node.number, connector.modes)
                        for att in network.attributes('LINK'): newLink[att] = connector[att]
                    for connector in incomingConnectors:
                        newLink = network.create_link(connector.i_node.number, virtualNode.number, connector.modes)
                        for att in network.attributes('LINK'): newLink[att] = connector[att]
                    
                #Copy the base node's existing station connectors to the new virtual node
                for connector in outgoingLinks:
                    newLink = network.create_link(virtualNode.number, connector.j_node.number, connector.modes)
                    for att in network.attributes('LINK'): newLink[att] = connector[att]
                    
                    transferGrid[groupNumber, 0].add(newLink) #Index the new connector to the Grid
                    
                for connector in incomingLinks:
                    newLink = network.create_link(connector.i_node.number, virtualNode.number, connector.modes)
                    for att in network.attributes('LINK'): newLink[att] = connector[att]
                    
                    transferGrid[0, groupNumber].add(newLink) #Index the new connector to the Grid
                                 
        #Connect the virtual nodes to each other
        for tup_a, tup_b in get_combinations(virtualNodes, 2): #Iterate through unique pairs of nodes
            node_a, group_a = tup_a
            node_b, group_b = tup_b

            link_ab = network.create_link(node_a.number, node_b.number, [transferMode])
            link_ba = network.create_link(node_b.number, node_a.number, [transferMode])

            transferGrid[group_a, group_b].add( link_ab )
            transferGrid[group_b, group_a].add( link_ba )
        
        for group in baseNode.passing_groups:
            newNode = network.create_regular_node(self._GetNewNodeNumber(network, baseNode.number))
            
            for att in network.attributes('NODE'): newNode[att] = baseNode[att]
            #newNode.label = "TP%s" %int(group)
            newNode.label = baseNode.label
            
            baseNode.to_hyper_node[group] = newNode
    
    def _ConnectSurfaceOrStationNode(self, baseNode1, transferGrid):
        network = baseNode1.network
        
        #Theoretically, we should only need to look at outgoing links,
        #since one node's outgoing link is another node's incoming link.
        for link in baseNode1.outgoing_links():
            if link.role == 0: continue #Skip non-connector links
            
            baseNode2 = link.j_node
            
            for groupNumber1 in baseNode1.stopping_groups:
                virtualNode1 = baseNode1.to_hyper_node[groupNumber1]
                
                for groupNumber2 in baseNode2.stopping_groups:
                    virtualNode2 = baseNode2.to_hyper_node[groupNumber2]
                    
                    if network.link(virtualNode1.number, virtualNode2.number) is not None:
                        #Link already exists. Index it just in case
                        if groupNumber1 != groupNumber2:
                            transferGrid[groupNumber1, groupNumber2].add(network.link(virtualNode1.number, virtualNode2.number))
                        continue 
                    
                    newLink = network.create_link(virtualNode1.number, virtualNode2.number, link.modes)
                    for att in network.attributes('LINK'): newLink[att] = link[att]
                    
                    #Only index if the group numbers are different. Otherwise, this is the only
                    #part of the code where intra-group transfers are identified, so DON'T do
                    #it to have the matrix be consistent.
                    if groupNumber1 != groupNumber2:
                        transferGrid[groupNumber1, groupNumber2].add(newLink)
    
    def _ProcessTransitLine(self, lineId, network, zoneTransferGrid, saveFunction):
        line = network.transit_line(lineId)
        group = line.group
        lineMode = set([line.mode])
        
        baseLinks = [segment.link for segment in line.segments(False)]
        newItinerary = [baseLinks[0].i_node.to_hyper_node[group].number]
        for baseLink in baseLinks:
            iv = baseLink.i_node.to_hyper_node[group].number
            jv = baseLink.j_node.to_hyper_node[group].number
            
            newItinerary.append(jv)
            
            vLink = network.link(iv, jv)
            if vLink is None:
                vLink = network.create_link(iv, jv, lineMode)
                for att in network.attributes('LINK'): vLink[att] = baseLink[att]
            else:
                vLink.modes |= lineMode
                
        newLine = network.create_transit_line('temp', line.vehicle.id, newItinerary)
        for att in network.attributes('TRANSIT_LINE'): newLine[att] = line[att]
        
        for segment in line.segments(True):
            newSegment = newLine.segment(segment.number)
            for att in network.attributes('TRANSIT_SEGMENT'): newSegment[att] = segment[att]
            
            saveFunction(newSegment, segment.i_node.number)
            
            link = segment.link
            if link is not None:
                fzi = link.i_node.fare_zone
                fzj = link.j_node.fare_zone
                
                if fzi != fzj and fzi != 0 and fzj != 0:
                    #Add the segment's identifier, since changeTransitLineId de-references
                    #the line copy.
                    zoneTransferGrid[fzi, fzj].add((lineId, segment.number))
        
        network.delete_transit_line(lineId)
        _editing.changeTransitLineId(newLine, lineId)
    
    def _IndexStationConnectors(self, network, transferGrid, stationGroups, groupIds2Int):
        print "Indexing station connectors"        
        for lineGroupId, stationCentroids in stationGroups.iteritems():
            idx = groupIds2Int[lineGroupId]
            
            for nodeId in stationCentroids:
                centroid = network.node(nodeId)
                if not centroid.is_centroid: continue #Skip non-zones
                
                for link in centroid.outgoing_links():
                    if idx in link.j_node.stopping_groups:
                        transferGrid[0, idx].add(link)
                for link in centroid.incoming_links():
                    if idx in link.i_node.stopping_groups:
                        transferGrid[idx, 0].add(link)
            print "Indexed connectors for group %s" %lineGroupId
                
    
    #---              
    #---LOAD FARE RULES-----------------------------------------------------------------------------------
    
    def _ApplyFareRules(self, network, fareRulesElement,
                        groupTransferGrid, zoneCrossingGrid,
                        groupIds2Int, zoneId2sInt):
        
        linesIdexedByGroup = {}
        for line in network.transit_lines():
            group = line.group
            
            if group in linesIdexedByGroup:
                linesIdexedByGroup[group].append(line)
            else:
                linesIdexedByGroup[group] = [line]
        
        for fareElement in fareRulesElement.findall('fare'):
            typ = fareElement.attrib['type']
            
            if typ == 'initial_boarding':
                self._ApplyInitialBoardingFare(fareElement, groupIds2Int, zoneId2sInt, groupTransferGrid)
            elif typ == 'transfer':
                self._ApplyTransferBoardingFare(fareElement, groupIds2Int, groupTransferGrid)
            elif typ == 'distance_in_vehicle':
                self._ApplyFareByDistance(fareElement, groupIds2Int, linesIdexedByGroup)
            elif typ == 'zone_crossing':
                self._ApplyZoneCrossingFare(fareElement, groupIds2Int, zoneId2sInt, zoneCrossingGrid, network)
            
            self.TRACKER.completeSubtask()
            
            
    def _ApplyInitialBoardingFare(self, fareElement, groupIds2Int, zoneId2sInt, transferGrid):
        cost = float(fareElement.attrib['cost'])
        
        with _m.logbook_trace("Initial Boarding Fare of %s" %cost):
            groupId = fareElement.find('group').text
            _m.logbook_write("Group: %s" %groupId)
            
            groupNumber = groupIds2Int[groupId]
            
            inZoneElement = fareElement.find('in_zone')
            if inZoneElement is not None:
                zoneId = inZoneElement.text
                zoneNumber = zoneId2sInt[zoneId]
                _m.logbook_write("In zone: %s" %zoneId)
                
                checkLink = lambda link: link.i_node.fare_zone == zoneNumber
            else:
                checkLink = lambda link: True
            
            includeAllElement = fareElement.find('include_all_groups')
            if includeAllElement is not None:
                includeAll = self.__BOOL_PARSER[includeAllElement.text]
                _m.logbook_write("Include all groups: %s" %includeAll)
            else:
                includeAll = True
            
            count = 0
            if includeAll:
                for xIndex in xrange(transferGrid.x):
                    for link in transferGrid[xIndex, groupNumber]:
                        if checkLink(link): 
                            link[self.LinkFareAttributeId] += cost
                            count += 1
            else:
                for link in transferGrid[0, groupNumber]:
                    if checkLink(link):
                        link[self.LinkFareAttributeId] += cost
                        count += 1   
            _m.logbook_write("Applied to %s links." %count)
    
    def _ApplyTransferBoardingFare(self, fareElement, groupIds2Int, transferGrid):
        cost = float(fareElement.attrib['cost'])
        
        with _m.logbook_trace("Transfer Boarding Fare of %s" %cost):
            fromGroupId = fareElement.find('from_group').text
            fromNumber = groupIds2Int[fromGroupId]
            _m.logbook_write("From Group: %s" %fromGroupId)
            
            toGroupId = fareElement.find('to_group').text
            toNumber = groupIds2Int[toGroupId]
            _m.logbook_write("To Group: %s" %toGroupId)
            
            bidirectionalElement = fareElement.find('bidirectional')
            if bidirectionalElement is not None:
                bidirectional = self.__BOOL_PARSER[bidirectionalElement.text.upper()]
                _m.logbook_write("Bidirectional: %s" %bidirectional)
            else:
                bidirectional = False
            
            count = 0
            for link in transferGrid[fromNumber, toNumber]:
                link[self.LinkFareAttributeId] += cost
                count += 1
            
            if bidirectional:
                for link in transferGrid[toNumber, fromNumber]:
                    link[self.LinkFareAttributeId] += cost
                    count += 1
            _m.logbook_write("Applied to %s links." %count)
    
    def _ApplyFareByDistance(self, fareElement, groupIds2Int, linesIdexedByGroup):
        cost = float(fareElement.attrib['cost'])
        
        with _m.logbook_trace("Fare by Distance of %s" %cost):
            groupId = fareElement.find('group').text
            groupNumber = groupIds2Int[groupId]
            _m.logbook_write("Group: %s" %groupId)
            
            count = 0
            for line in linesIdexedByGroup[groupNumber]:
                for segment in line.segments(False):
                    segment[self.SegmentFareAttributeId] += segment.link.length * cost
                    count += 1
            _m.logbook_write("Applied to %s segments." %count)
    
    def _ApplyZoneCrossingFare(self, fareElement, groupIds2Int, zoneId2sInt, crossingGrid, network):
        cost = float(fareElement.attrib['cost'])
        
        with _m.logbook_trace("Zone Crossing Fare of %s" %cost):
            groupId = fareElement.find('group').text
            groupNumber = groupIds2Int[groupId]
            _m.logbook_write("Group: %s" %groupId)
            
            fromZoneId = fareElement.find('from_zone').text
            fromNumber = zoneId2sInt[fromZoneId]
            _m.logbook_write("From Zone: %s" %fromZoneId)
            
            toZoneId = fareElement.find('to_zone').text
            toNumber = zoneId2sInt[toZoneId]
            _m.logbook_write("To Zone: %s" %toZoneId)
            
            bidirectionalElement = fareElement.find('bidirectional')
            if bidirectionalElement is not None:
                bidirectional = self.__BOOL_PARSER[bidirectionalElement.text.upper()]
                _m.logbook_write("Bidirectional: %s" %bidirectional)
            else:
                bidirectional = False
            
            count = 0
            for lineId, segmentNumber in crossingGrid[fromNumber, toNumber]:
                line = network.transit_line(lineId)
                if line.group != groupNumber: continue
                line.segment(segmentNumber)[self.SegmentFareAttributeId] += cost
                count += 1
                
            if bidirectional:
                for lineId, segmentNumber in crossingGrid[toNumber, fromNumber]:
                    line = network.transit_line(lineId)
                    if line.group != groupNumber: continue
                    line.segment(segmentNumber)[self.SegmentFareAttributeId] += cost
                    count += 1
                    
            _m.logbook_write("Applied to %s segments." %count)
        
    def _CheckForNegativeFares(self, network):
        negativeLinks = []
        negativeSegments = []
        
        for link in network.links():
            cost = link[self.LinkFareAttributeId]
            if cost < 0.0: negativeLinks.append(link)
        
        for segment in network.transit_segments():
            cost = segment[self.SegmentFareAttributeId]
            if cost < 0.0: negativeSegments.append(segment)
        
        
        if (len(negativeLinks) + len(negativeSegments)) > 0:
            print "WARNING: Found %s links and %s segments with negative fares" %(len(negativeLinks), len(negativeSegments))
            
            pb = _m.PageBuilder(title="Negative Fares Report")
            h = HTML()
            h.h2("Links with negative fares")
            t = h.table()
            r = t.tr()
            r.th("link")
            r.th("cost")
            for link in negativeLinks:
                r = t.tr()
                r.td(str(link))
                r.td(str(link[self.LinkFareAttributeId]))
            
            h.h2("Segments with negative fares")
            t = h.table()
            r = t.tr()
            r.th("segment")
            r.th("cost")
            for segment in negativeSegments:
                r = t.tr()
                r.td(segment.id)
                r.td(segment[self.SegmentFareAttributeId])
            
            pb.wrap_html(body=str(h))
            
            _m.logbook_write("LINKS AND SEGMENTS WITH NEGATIVE FARES", value=pb.render())

    #---              
    #---MODELLER INTERFACE FUNCTIONS----------------------------------------------------------------------      
    
    @_m.method(return_type=unicode)
    def preload_auxtr_modes(self):
        options = []
        h = HTML()
        for id, type, description in _util.getScenarioModes(self.BaseScenario,  ['AUX_TRANSIT']):
            text = "%s - %s" %(id, description)
            options.append(str(h.option(text, value= id)))
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def preload_scenario_link_attributes(self):
        options = []
        h = HTML()
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'LINK': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append(str(h.option(text, value= exatt.name)))
        return "\n".join(options)

    @_m.method(return_type=unicode)
    def preload_scenario_segment_attributes(self):
        options = []
        h = HTML()
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'TRANSIT_SEGMENT': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append(str(h.option(text, value= exatt.name)))
        return "\n".join(options)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        