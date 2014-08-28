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
ESTIMATE NETWORK SIZE

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-05-09 by pkucirek
    
    1.0.0 Published on 2014-05-29. This version calculates # of nodes, but the logic for correctly
        calculating the number of links eludes me. Therefore, it "estimates" the number of links
        required, slightly conservatively. My ballpark figure is over by < 1%
    
    1.0.1 Fixed a bug in PrepareNetwork which only considers segments that permit alightings as 
        'stops.' We want to catch both boardings AND alightings 
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from math import factorial
from xml.etree import ElementTree as _ET
from os import path
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

def choose(setSize, n):
    if n > setSize: return 0
    return factorial(setSize) / (factorial(n) * factorial(setSize - n)) 

class XmlValidationError(Exception):
    pass

class EstimateHyperNetworkSize(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    BaseScenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    XMLSchemaFile = _m.Attribute(str)
    
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
        
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Estimate FBTNetwork Size v%s" %self.version,
                     description="Without actually editing the network, this tool estimates \
                         the required total link and nodes in a fare-based transit network \
                         (FBTN). This can be important, as the FBTN is quite large and in \
                         some cases can exceed the current size of the databank.\
                         <br><br>The number of nodes reported is calculated accurately, however \
                         the number of links is estimated. Trial runs indicate that the \
                         number of links is over-estimated by less than 1%.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='XMLSchemaFile', window_type='file',
                           file_filter="*.xml", title="Fare Schema File")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            retval = self._Execute()
            msg = "The hyper network will contain exactly %s nodes and approximately %s links." %retval
            self.tool_run_msg = _m.PageBuilder.format_info(msg)
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            
            root = _ET.parse(self.XMLSchemaFile).getroot() 
            self._ValidateSchemaFile(root)
            
            with _util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_LINE', description= "Line group") \
                    as lineGroupAtt:
                
                with _m.logbook_trace("Line groups"):
                    groupsElement = root.find('groups')
                    self._LoadGroups(groupsElement, lineGroupAtt.id)
                
                network = self.BaseScenario.get_network()
            _MODELLER.desktop.refresh_needed(False)
            
            self._PrepareNetwork(network, lineGroupAtt.id)
            
            return self._CalcNetworkSize(network)
                

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "BaseScenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _ValidateSchemaFile(self, root):
        
        #Check the top-level of the file
        versionElem = root.find('version')
        if versionElem == None:
            raise XmlValidationError("Fare schema must specify a 'version' element.")
        
        groupsElement = root.find('groups')
        if groupsElement == None:
            raise XmlValidationError("Fare schema must specify a 'groups' element.")
        
        zonesElement = root.find('zones')
        
        fareRulesElement = root.find('fare_rules')
        if fareRulesElement == None:
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
        if zonesElement != None:
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
                    if childElement == None:
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
                if child == None:
                    raise XmlValidationError("Fare element #%s of type '%s' must specify a '%s' element" %(i, ruleType, name))
                
                text = child.text
                checkFunc(text, name)
            
            #Check optional children
            for name, checkFunc in optionalChildren.iteritems():
                child = fareElement.find(name)
                if child == None: continue
                
                text = child.text
                checkFunc(text, name)
        
        return len(groupElements), len(zoneElements), len(fareElements)
    
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
                    raise
            
            msg = "Loaded group %s: %s" %(groupNumber, id)
            print msg
            _m.logbook_write(msg)
            
            self.TRACKER.completeSubtask()
        
        return groupIds2Int, int2groupIds
    
    def _PrepareNetwork(self, network, lineGroupAttId):
        '''
        Prepares network attributes for transformation
        '''
        
        network.create_attribute('TRANSIT_LINE', 'group', 0)
        network.create_attribute('NODE', 'passing_groups', None) #Set of groups passing through but not stopping at the node
        network.create_attribute('NODE', 'stopping_groups', None) #Set of groups stopping at the node
        network.create_attribute('LINK', 'role', 0) #Link topological role
        network.create_attribute('NODE', 'role', 0) #Node topological role
        
        #Initialize node attributes (incl. copying node zone)
        #Also, copy the zones loaded into the proxies
        for node in network.regular_nodes():
            node.passing_groups = set()
            node.stopping_groups = set()
        
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
            elif i.role == 2 and j.role == 2:
                if permitsWalk: link.role = 2 #Station transfer
                else: link.role = 3 #Existing hyper link
    
    def _CalcNetworkSize(self, network):
        baseSurfaceNodes = []
        baseStationNodes = []
        for node in network.regular_nodes():
            if node.role == 1: baseSurfaceNodes.append(node)
            elif node.role == 2: baseStationNodes.append(node)
        
        baseNodes = network.element_totals['regular_nodes']
        baseLinks = network.element_totals['links']
        
        nVirtualSurfaceNodes, nBaseConnectorLinks = 0, 0
        self.TRACKER.startProcess(len(baseSurfaceNodes) + len(baseStationNodes))
        for node in baseSurfaceNodes:
            addNodes, addLinks = self._CalcSurfaceNode(node)
            nVirtualSurfaceNodes += addNodes
            nBaseConnectorLinks += addLinks
            self.TRACKER.completeSubtask()
        print "%s virtual road nodes" %nVirtualSurfaceNodes
        print "%s access links to virtual road nodes" %nBaseConnectorLinks
        
        nVirtualStationNodes, nStationConnectorLinks = 0, 0
        for node in baseStationNodes:
            addNodes, addLinks = self._CalcStationNode(node)
            nVirtualStationNodes += addNodes
            nStationConnectorLinks += addLinks
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        print "%s virtual station nodes" %nVirtualStationNodes
        print "%s access links to virtual station nodes" %nStationConnectorLinks
        
        nConnectorLinks = 0
        for node in baseStationNodes + baseSurfaceNodes:
            nConnectorLinks += self._CalcStationToSurfaceConnectors(node)
        print "%s road-to-transit connector links." %nConnectorLinks
        
        inVehicleLinks = 0
        network.create_attribute('LINK', 'copies', None)
        for link in network.links():
            link.copies = set()
        
        for line in network.transit_lines():
            group = line.group
            for segment in line.segments():
                segment.link.copies.add(group)
        for link in network.links():
            if link.role == 3: #Is existing hyper link
                inVehicleLinks += max(len(link.copies) - 1, 0)
            else:
                inVehicleLinks += len(link.copies)
        print "%s in-vehicle links" %inVehicleLinks
        
        totalNodes = baseNodes + nVirtualStationNodes + nVirtualSurfaceNodes
        totalLinks = baseLinks + nBaseConnectorLinks + nConnectorLinks + nStationConnectorLinks + inVehicleLinks
        
        _m.logbook_write("The hyper network will contain exactly %s total nodes and approximately %s links" %(totalNodes, totalLinks))
        
        return totalNodes, totalLinks
    
    def _CalcSurfaceNode(self, node):
        nStoppingGroups = len(node.stopping_groups)
        nPassingGroups = len(node.passing_groups)
        
        nVirtualNodes = nStoppingGroups + nPassingGroups
        
        nBaseConnectorLinks = 2 * nStoppingGroups
        nVirtualTransferLinks = 2 * choose(nStoppingGroups, 2)
        
        '''
        nSurfaceToStationLinks = 0
        for link in node.outgoing_links():
            if link.j_node.role != 2: continue
            
            nStationStoppingGroups = len(link.j_node.stopping_groups)
            nSurfaceToStationLinks += 2 * nStationStoppingGroups * nStoppingGroups
            #By multiplying by 2, this accounts for both directions
        
        nVirtualLinks = nBaseConnectorLinks + nVirtualTransferLinks + nSurfaceToStationLinks
        '''
        
        nVirtualLinks = nBaseConnectorLinks + nVirtualTransferLinks
        
        return nVirtualNodes, nVirtualLinks
    
    def _CalcStationNode(self, node):
        nStoppingGroups = len(node.stopping_groups)
        nPassingGroups = len(node.passing_groups)
        
        if nStoppingGroups == 0:
            return nPassingGroups, 0
        
        nVirtualNodes = nStoppingGroups + nPassingGroups - 1
        
        if nVirtualNodes > 0:
            interStationConnectorLinks = choose(nVirtualNodes + 1, 2)
            
            nIncomingRole1Links = 0
            for link in node.incoming_links():
                if link.role == 1: nIncomingRole1Links += 1
                elif link.i_node.is_centroid: nIncomingRole1Links += 1
            nOutgoingRole1Links = 0
            for link in node.outgoing_links():
                if link.role == 1: nOutgoingRole1Links += 1
                elif link.j_node.is_centroid: nOutgoingRole1Links += 1
            
            nRole1LinkCopies = nVirtualNodes * (nIncomingRole1Links + nOutgoingRole1Links)
        else: 
            interStationConnectorLinks = 0
            nRole1LinkCopies = 0
        
        return nVirtualNodes, interStationConnectorLinks + nRole1LinkCopies
    
    def _CalcStationToSurfaceConnectors(self, node):
        nStoppingGroups = len(node.stopping_groups)
        nPassingGroups = len(node.passing_groups)
        
        '''
        if node.role == 2:
            if nStoppingGroups == 0: return 0
            nVirtualNodes = nStoppingGroups - 1
        else:
            nVirtualNodes = nStoppingGroups
        '''
        nVirtualNodes = nStoppingGroups
        
        nConnectorLinks = 0
        for link in node.outgoing_links():
            if link.role == 0 or link.role == 3: continue
            
            otherNode = link.j_node
            '''
            if otherNode.role == 2:
                if len(otherNode.stopping_groups) == 0: nOtherVirtualNodes = 0
                else: nOtherVirtualNodes = len(otherNode.stopping_groups) - 1
            elif otherNode.role == 1:
                nOtherVirtualNodes = len(otherNode.stopping_groups)
            '''
            nOtherVirtualNodes = len(otherNode.stopping_groups)
            
            nConnectorLinks += nOtherVirtualNodes * nVirtualNodes
        return nConnectorLinks
    
    def _CalcTransitLine(self, line, groupLinks):
        group = line.group
        if group in groupLinks:
            linkSet = groupLinks[group]
        else:
            linkSet = set()
            groupLinks[group] = linkSet
        
        for segment in line.segments():
            OD = segment.i_node.number, segment.link.j_node.number
            linkSet.add(OD)
    
    '''
    DEPRECATED
    '''
    def _OldCalculateNetworkSize(self, network):        
        baseSurfaceNodes = []
        baseStationNodes = []
        for node in network.regular_nodes():
            if node.role == 1: baseSurfaceNodes.append(node)
            elif node.role == 2: baseStationNodes.append(node)
        
        totalStops = 0
        numberOfVirtualRole1Nodes = 0
        numberOfVirtualRole2Nodes = 0
        numberOfVirtualRole1Links = 0
        numberOfVirtualRole2Links = 0
        virtualRole3Links = set()
        
        for node in baseSurfaceNodes:
            numberOfStoppingGroups = len(node.stopping_groups)
            numberOfPassingGroups = len(node.passing_groups)
            totalStops += numberOfStoppingGroups
            
            numberOfVirtualRole1Nodes += numberOfPassingGroups + numberOfStoppingGroups
            numberOfVirtualRole1Links += 2 * numberOfStoppingGroups
            numberOfVirtualRole2Links += permute(numberOfStoppingGroups, 2)
        
        for node in baseStationNodes:
            numberOfStoppingGroups = len(node.stopping_groups)
            numberOfPassingGroups = len(node.passing_groups)
            totalStops += numberOfStoppingGroups
            
            numberOfOutboundRole1Links = 0
            connectedNodes = []
            for link in node.outgoing_links():
                if link.role == 1: numberOfOutboundRole1Links += 1
                if link.role != 0: connectedNodes.append(link.j_node)
            
            if numberOfStoppingGroups == 0:
                print "Found no stopping groups for station node %s %s" %(node, node.passing_groups)
                numberOfVirtualRole2Nodes += numberOfPassingGroups - 1
            else:
                numberOfVirtualRole2Nodes += numberOfPassingGroups + numberOfStoppingGroups - 1
                
                numberOfVirtualRole1Links += (numberOfStoppingGroups - 1) * numberOfOutboundRole1Links
                numberOfVirtualRole2Links += permute(numberOfStoppingGroups - 1, 2)
                
                for otherNode in connectedNodes:
                    otherStoppingGroups = len(otherNode.stopping_groups)
                    
                    numberOfVirtualRole2Links += otherStoppingGroups * numberOfStoppingGroups
        
        for line in network.transit_lines():
            group = line.group
            
            first = True
            for segment in line.segments(True):
                if first:
                    prevNode = segment.i_node.number
                    first = False
                else:
                    node = segment.i_node.number
                    linkTuple = (group, prevNode, node)
                    virtualRole3Links.add(linkTuple)
                    prevNode = node
                        
        print "Average groups per node: %s" %(float(totalStops) / len(baseSurfaceNodes))
        print "Number of new virtual role 1 nodes: %s" %numberOfVirtualRole1Nodes
        print "Number of new virtual role 2 nodes: %s" %numberOfVirtualRole2Nodes
        print "Number of new virtual role 1 links: %s" %numberOfVirtualRole1Links
        print "Number of new virtual role 2 links: %s" %numberOfVirtualRole2Links
        print "Number of new virtual role 3 links: %s" %len(virtualRole3Links)
        print "Estimated total nodes: %s" %(network.element_totals['regular_nodes'] + numberOfVirtualRole1Nodes + numberOfVirtualRole2Nodes)
        print "Estimated total links: %s" %(network.element_totals['links'] + numberOfVirtualRole1Links + numberOfVirtualRole2Links + len(virtualRole3Links))
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        