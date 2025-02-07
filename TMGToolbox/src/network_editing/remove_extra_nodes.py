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
[TITLE]

    Authors: pkucirek

    Latest revision by: nasterska
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-05-06 by pkucirek
    
    1.0.0 Published with proper documentation on 2014-05-29

    1.0.1 Copy of scenario is not created 2016-08-24
        
'''

import inro.modeller as _m
import traceback as _traceback
from re import split as _regex_split
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_editing = _MODELLER.module('tmg.common.network_editing')
ForceError = _editing.ForceError
InvalidNetworkOperationError = _editing.InvalidNetworkOperationError
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class RemoveExtraNodes(_m.Tool()):
    
    NAMED_AGGREGATORS = _editing.NAMED_AGGREGATORS
    
    @staticmethod
    def AVERAGE_BY_LENGTH_LINKS(att, link1, link2):
        a1 = link1[att]
        a2 = link2[att]
        l1 = link1.length
        l2 = link2.length
        
        return (a1 * l1 + a2 * l2) / (l1 + l2)
    
    @staticmethod
    def AVERAGE_BY_LENGTH_SEGMENTS(att, segment1, segment2):
        a1 = segment1[att]
        a2 = segment2[att]
        l1 = segment1.link.length
        l2 = segment2.link.length
        
        return (a1 * l1 + a2 * l2) / (l1 + l2)
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    BaseScenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    baseScen = _m.Attribute(int)
    
    NodeFilterAttributeId = _m.Attribute(str)
    StopFilterAttributeId = _m.Attribute(str)
    ConnectorFilterAttributeId = _m.Attribute(str)
    
    AttributeAggregatorString = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        
        lines = ["vdf: force",
                 "length: sum",
                 "type: first",
                 "lanes: avg",
                 "ul1: avg",
                 "ul2: force",
                 "ul3: avg",
                 "dwt: sum",
                 "dwfac: force",
                 "ttf: force",
                 "us1: avg_by_length",
                 "us2: avg",
                 "us3: avg",
                 "ui1: avg",
                 "ui2: avg",
                 "ui3: avg"]
        
        domains = set(['NODE', 'LINK', 'TRANSIT_SEGMENT'])
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type in domains:
                lines.append("%s: avg" %exatt.name)
        self.AttributeAggregatorString = "\n".join(lines)
        
        #Set to -1 as this will be interpreted in the HTML
        # as 'null' (which should get converted in Python to
        # 'None'
        self.NodeFilterAttributeId = -1
        self.StopFilterAttributeId = -1
        self.ConnectorFilterAttributeId = -1
        
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Remove Extra Nodes v%s" %self.version,
                     description="Removes unnecessary (i.e., cosmetic) nodes from the network. \
                                Only candidate nodes (nodes with a degree of 2) will be removed \
                                from the network, however the tool can be configured to \
                                expand and/or contract the set of candidate nodes. Three filter \
                                attributes are used: <ul>\
                                <li>Node filter attribute: Contracts the set of candidate nodes, \
                                to only those candidate nodes whose attribute value is nonzero.\
                                <li>Stop filter attribute: Expands the set of candidate nodes to \
                                include candidate nodes with transit stops whose attribute value \
                                is nonzero. Otherwise nodes with transit stops will be excluded \
                                from the set of candidate nodes.\
                                <li>Connector filter attribute: Expands the set of candidate \
                                nodes to include candidate nodes attached to centroid connectors \
                                whose attribute value are all nonzero. Otherwise, all centroid \
                                connectors are preserved. </ul>\
                                <br>Additionally, this tool allows the user to specify \
                                functions used to aggregate LINK and TRANSIT SEGMENT attributes. \
                                Attributes can be named using either their Emme Desktop names \
                                (e.g. 'lanes') or their Network API names  (e.g. 'num_lanes'). \
                                See below for a description of accepted function names. Note \
                                that the function <b>force</b> can be used to keep nodes when \
                                attribute values differ (e.g. to preserve lane change locations).",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title="Scenario",
                               allow_none=False)      
        
        pb.add_header("NETWORK FILTERS")
        
        nodeKV = [(-1, 'No attribute')]
        connectorKV = [(-1, 'No attribute')]
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type == 'NODE':
                v = "%s - %s" %(exatt.name, exatt.description)
                nodeKV.append((exatt.name, v))
            elif exatt.type == 'LINK':
                v = "%s - %s" %(exatt.name, exatt.description)
                connectorKV.append((exatt.name, v))
                
        pb.add_select(tool_attribute_name= 'NodeFilterAttributeId',
                      keyvalues= nodeKV,
                      title="Node Filter Attribute",
                      note="Only remove candidate nodes whose attribute value != 0. Select 'No attribute' to remove all candidate nodes.")
        #Excludes candidate nodes whose attribute value == 0. Select 'No attribute' to accept all nodes
        
        pb.add_select(tool_attribute_name= 'StopFilterAttributeId',
                      keyvalues= nodeKV,
                      title="Stop Filter Attribute",
                      note= "Remove candidate transit stop nodes whose attribute value != 0. Select 'No attribute' to preserve all transit stops")
        
        pb.add_select(tool_attribute_name= 'ConnectorFilterAttributeId',
                      keyvalues= connectorKV,
                      title="Connector Filter Attribute",
                      note="Remove centroid connectors attached to candidate nodes whose attribute value != 0. Select 'No attribute' to preserve all centroid connectors")
        
        pb.add_header("AGGREGATION FUNCTIONS")
        
        def add_li(li):
            return "<li>" + li + "<\\li>"
        aggregation_options = add_li("first - Uses the first element's attribute")
        aggregation_options += add_li("last - Uses the last element's attribute")
        aggregation_options += add_li("sum - Add the two attributes")
        aggregation_options += add_li("avg - Averages the two attributes")
        aggregation_options += add_li("avg_by_length - Average the two attributes, weighted by link length")
        aggregation_options += add_li("min - The minimum of the two attributes")
        aggregation_options += add_li("max - The maximum of the two attributes")
        aggregation_options += add_li("and - Boolean AND")
        aggregation_options += add_li("or - Boolean OR")
        aggregation_options += add_li("force - Forces the tool to keep the node if the two attributes are different")
        aggregation_options = "<ul>" + aggregation_options + "<\\ul>"
        
        pb.add_text_box(tool_attribute_name='AttributeAggregatorString',
                        size= 500, multi_line=True,
                        title= "Attribute Aggregation Functions",
                        note= "List of network NODE, LINK, and TRANSIT SEGMENT attributes to named \
                        aggregator functions. These functions are applied when links or segments are \
                        aggregated. Links inherit the attributes of their i-node.\
                        <br><br><b>Syntax:</b> [<em>attribute name</em>] : [<em>function</em>] , ... \
                        <br><br>Separate (attribute-function) pairs with a comma or new line. Either \
                        the Emme Desktop attribute names (e.g. 'lanes') or the Modeller API names \
                        (e.g. 'num_lanes') can be used. Accepted functions are: " + aggregation_options + \
                        "The default function for unspecified extra attribtues is 'sum.'")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s);
    
        //Modeller likes to make multi-line text boxes very
        //short, so this line changes the default height
        //to something a little more visible.
        $("#AttributeAggregatorString").css({height: '90px'});
        
        $("#BaseScenario").bind('change', function()
        {
            $(this).commit();
            $("#NodeFilterAttributeId")
                .empty()
                .append(tool.get_scenario_node_attributes())
            inro.modeller.page.preload("#NodeFilterAttributeId");
            $("#NodeFilterAttributeId").trigger('change')
                
            $("#StopFilterAttributeId")
                .empty()
                .append(tool.get_scenario_node_attributes())
            inro.modeller.page.preload("#StopFilterAttributeId");
            $("#StopFilterAttributeId").trigger('change')
            
            $("#ConnectorFilterAttributeId")
                .empty()
                .append(tool.get_scenario_link_attributes())
            inro.modeller.page.preload("#ConnectorFilterAttributeId");
            $("#ConnectorFilterAttributeId").trigger('change')
        });
        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()

    ##########################################################################################################
        
    def __call__(self, baseScen, NodeFilterAttributeId, StopFilterAttributeId, ConnectorFilterAttributeId, AttributeAggregatorString):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        self.BaseScenario = _MODELLER.emmebank.scenario(baseScen)
        self.NodeFilterAttributeId = NodeFilterAttributeId
        self.StopFilterAttributeId = StopFilterAttributeId
        self.ConnectorFilterAttributeId = ConnectorFilterAttributeId
        self.AttributeAggregatorString = AttributeAggregatorString

        try:
            
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")    

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
            
            self._ParseSegmentAggregators()
            self.TRACKER.completeTask()
            
            network = self.BaseScenario.get_network()
            self.TRACKER.completeTask()
            
            nodesToDelete = self._GetCandidateNodes(network)
            if len(nodesToDelete) > 0:               
                if self.ConnectorFilterAttributeId:
                    self._RemoveCandidateCentroidConnectors(nodesToDelete)            
                log = self._RemoveNodes(network, nodesToDelete)
                self._WriteReport(log)
                self.TRACKER.completeTask()
                self.TRACKER.startProcess(2)
                self.BaseScenario.publish_network(network, True)
                self.TRACKER.completeSubtask()
            
            _MODELLER.desktop.refresh_needed(True)
            self.TRACKER.completeTask()

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Base Scenario" : str(self.BaseScenario.id),
                "Node Filter Attribute": self.NodeFilterAttributeId,
                "Stop Filter Attribute": self.StopFilterAttributeId,
                "Connector Filter Attribute": self.ConnectorFilterAttributeId,
                "Attribute Aggregations": self.AttributeAggregatorString,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _ParseSegmentAggregators(self):
        
        #Setup the translation dictionary to get from Emme Desktop attribute names
        #to Modeller Python attribute names. Extra attributes are named the same.
        translator = {'length': 'length',
                        'type': 'type',
                        'lanes': 'num_lanes',
                        'vdf': 'volume_delay_func',
                        'ul1': 'data1_l',
                        'ul2': 'data2_l',
                        'ul3': 'data3_l',
                        'dwt': 'dwell_time',
                        'dwfac': 'factor_dwell_time_by_length',
                        'ttf': 'transit_time_func',
                        'us1': 'data1_s',
                        'us2': 'data2_s',
                        'us3': 'data3_s',
                        'data1_l': 'data1_l',
                        'data2_l': 'data2_l',
                        'data3_l': 'data3_l',
                        'ui1': 'data1_n',
                        'ui2': 'data2_n',
                        'ui3': 'data3_n',
                        'dwell_time': 'dwell_time',
                        'factor_dwell_time_by_length': 'factor_dwell_time_by_length',
                        'transit_time_func': 'transit_time_func',
                        'data1_s': 'data1_s',
                        'data2_s': 'data2_s',
                        'data3_s': 'data3_s',
                        'data1': 'data1',
                        'data2': 'data2',
                        'data3': 'data3',
                        'noali': 'allow_alightings',
                        'noboa': 'allow_boardings'}
        multipleDomainAttributes = ['data1', 'data2', 'data3']
        validFuncNames = ['sum','avg','or','and','min','max','first','last','zero','avg_by_length','force']
        
        #Setup default aggregator function names
        linkExtraAttributes = []
        segmentExtraAttributes = []
        nodeExtraAttributes = []
        
        for exatt in self.BaseScenario.extra_attributes():
            id = exatt.name
            t = exatt.type
            if t == 'NODE': nodeExtraAttributes.append(id)
            elif t == 'TRANSIT_SEGMENT': segmentExtraAttributes.append(id)
            elif t == 'LINK': linkExtraAttributes.append(id)
        
        self._linkAggregators = {'length': 'sum',
                                'data1_l': 'zero',
                                'data2_l': 'avg_by_length',
                                'data3_l': 'avg'}
        for att in linkExtraAttributes: 
            self._linkAggregators[att] = 'avg'
            translator[att] = att
        
        self._segmentAggregators = {'dwell_time': 'sum',
                                    'factor_dwell_time_by_length': 'and',
                                    'transit_time_func': 'force',
                                    'data1_s': 'avg_by_length',
                                    'data2_s': 'zero',
                                    'data3_s': 'zero'}
        for att in segmentExtraAttributes:
            self._segmentAggregators[att] = 'avg'
            translator[att] = att #Save extra attribute names into the translator for recognition
        
        self._nodeAggregators = {}
        for att in nodeExtraAttributes:
            self._nodeAggregators[att] = 'avg'
            translator[att] = att
        
        #Parse the argument string
        trimmedString = self.AttributeAggregatorString.replace(" ", '') #Clear spaces
        components = _regex_split('\n|,', trimmedString) #Supports newline and/or commas
        
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 2:
                msg = "Error parsing attribute aggregators: Separate attribute name from function with exactly one colon ':'"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            
            attName, funcName = parts
            if attName not in translator:
                raise IOError("Error parsing attribute aggregators: attribute '%s' not recognized." %attName)
            attName = translator[attName] 
            
            if not funcName in validFuncNames:
                raise IOError("Error parsing attribute aggregators: function '%s' not recognized for attribute '%s'" %(funcName, attName))
            
            if attName in self._linkAggregators:
                self._linkAggregators[attName] = funcName
            elif attName in self._segmentAggregators:
                self._segmentAggregators[attName] = funcName
            elif attName in self._nodeAggregators:
                self._nodeAggregators[attName] = funcName
            elif attName in multipleDomainAttributes:
                self._linkAggregators[attName] = funcName
                self._segmentAggregators[attName] = funcName
                self._nodeAggregators[attName] = funcName
        
        def fix_key_end(dictionary, end_sequency):
            to_change = []
            for key in six.iterkeys(dictionary):
                if key.endswith(end_sequency):
                    to_change.append(key)
            for key in to_change:
                newKey = key.replace(end_sequency, "")
                val = dictionary.pop(key)
                dictionary[newKey] = val

        fix_key_end(self._linkAggregators, "_l")
        fix_key_end(self._segmentAggregators, "_s")
        fix_key_end(self._nodeAggregators, "_n")

        def assign_function(dictionary, func_name, func_type):
            to_change = []
            for att, funcName in six.iteritems(dictionary):
                if funcName == func_name:
                    to_change.append((att, func_type))
                else:
                    try:
                        to_change.append((att, _editing.NAMED_AGGREGATORS[funcName]))
                    except KeyError as ke:
                        print("Error assigning function: %s from _editing" %funcName)
                        print(dictionary)
                        raise
            

            for key, to_assign in to_change:
                try:
                    dictionary[key] = to_assign
                except KeyError as ke:
                    print("Error assigning function: %s" %key)
                    print(dictionary)
                    raise
            

        assign_function(self._linkAggregators, 'avg_by_length', self.AVERAGE_BY_LENGTH_LINKS)
        assign_function(self._segmentAggregators, 'avg_by_length', self.AVERAGE_BY_LENGTH_LINKS)
        # This one should only set the func type to the _editing.NAMED_AGGREGATORS.
        assign_function(self._nodeAggregators, None, None)
    
    def _GetCandidateNodes(self, network):
        
        network.create_attribute('NODE', 'is_stop', False)
        for segment in network.transit_segments():
            if segment.allow_boardings or segment.allow_alightings:
                segment.i_node.is_stop = True
            
        
        #Setup filter functions. True to delete node, False to preserve
        if self.NodeFilterAttributeId:
            checkNode1 = lambda n: bool(n[self.NodeFilterAttributeId])
        else:
            checkNode1 = lambda n: True
        
        if self.StopFilterAttributeId:
            #True if node is not a stop or node is flagged
            checkNode2 = lambda n: not n.is_stop or n[self.StopFilterAttributeId]
        else:
            checkNode2 = lambda n: not n.is_stop
            
        if self.ConnectorFilterAttributeId:
            checkConnector = lambda l: bool(l[self.ConnectorFilterAttributeId])
        else:
            checkConnector = lambda l: False
        
        def checkNode(node):
            if checkNode1(node) and checkNode2(node):
                neighbours = set()
                nLinks = 0
                
                for link in node.outgoing_links():
                    if link.j_node.is_centroid: #is Connector
                        if checkConnector(link): continue #Make this link 'invisible'
                        
                        #Connector not flagged for deletion, therefore cannot delete
                        #this node
                        return False 
                    
                    neighbours.add(link.j_node.number)
                    nLinks += 1
                    
                for link in node.incoming_links():
                    if link.i_node.is_centroid:
                        if checkConnector: continue 
                        return False 
                    
                    neighbours.add(link.i_node.number)
                    nLinks += 1
                
                if len(neighbours) != 2: return False #Needs to have a degree of 2
                if nLinks != 2 and nLinks != 4: return False #Needs to be connected to either 2 or 4 links
                
                #Ok, so now we know this node is a candidate for deletion
                #For it to be selected for deletion, it must pass the two conditions
                return checkNode1(node) and checkNode2(node)
        
        retval = []
        
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        for node in network.regular_nodes():
            if checkNode(node): retval.append(node)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        _m.logbook_write("%s nodes were selected for deletion." %len(retval))
        return retval
    
    def _RemoveCandidateCentroidConnectors(self, nodesToDelete):
        network = nodesToDelete[0].network
        linkIdsToDelete = []
        for node in nodesToDelete:
            for link in node.incoming_links():
                if link.i_node.is_centroid and link[self.ConnectorFilterAttributeId]:
                    linkIdsToDelete.append((link.i_node.number, node.number))
            for link in node.outgoing_links():
                if link.j_node.is_centroid and link[self.ConnectorFilterAttributeId]:
                    linkIdsToDelete.append((node.number, link.j_node.number))
        for i, j in linkIdsToDelete:
            network.delete_link(i, j, True)
    
    def _RemoveNodes(self, network, nodesToDelete):
        
        log = []
        deepErrors = []
        deletedNodes = 0
        
        self.TRACKER.startProcess(len(nodesToDelete))
        for node in nodesToDelete:
            nid = node.number
            try:
                _editing.mergeLinks(node, deleteStop= True, vertex = True, linkAggregators= self._linkAggregators, segmentAggregators= self._segmentAggregators)
                deletedNodes += 1
            except ForceError as fe:
                #User specified to keep these nodes
                log.append("Node %s not deleted. User-specified aggregator for '%s' detected changes." %(nid, fe))
            except InvalidNetworkOperationError as inee:
                log.append(str(inee))
            except Exception as e:
                log.append("Deep error processing node %s: %s" %(nid, e))
                deepErrors.append(_traceback.format_exc())
            
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        
        _m.logbook_write("Removed %s nodes from the network." %deletedNodes)
        
        return log


    
    def _WriteReport(self, log):
        pb = _m.PageBuilder(title="Error log")
        
        doc = "<br>".join(log)
        pb.wrap_html(body=doc)
        
        _m.logbook_write("Error report", value=pb.render())
    
    @_m.method(return_type=six.text_type)
    def get_scenario_node_attributes(self):
        options = ['<option value="-1">No attribute</option>']
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'NODE': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.name, text)) 
        
        return "\n".join(options)
    
    @_m.method(return_type=six.text_type)
    def get_scenario_link_attributes(self):
        options = ['<option value="-1">No attribute</option>']
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'LINK': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.name, text)) 
        
        return "\n".join(options)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        