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
Full Network Set Generator

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    This tool takes in a base network with zones and
    generates a full set of usable cleaned time
    period networks. The goal is that this tool
    will replace the standard TMG workflow from
    base to time period networks.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-02-09 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from html import HTML
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

removeExtraNodes = _MODELLER.tool('tmg.network_editing.remove_extra_nodes')
prorateTransitSpeed = _MODELLER.tool('tmg.network_editing.prorate_transit_speed')
createTimePeriod = _MODELLER.tool('tmg.network_editing.time_of_day_changes.create_transit_time_period')

##########################################################################################################

class FullNetworkSetGenerator(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
                
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    BaseScenario = _m.Attribute(_m.InstanceType) 
        
    Scen1UnNumber = _m.Attribute(int)
    Scen1UnDescription = _m.Attribute(str)
    Scen1Number = _m.Attribute(int)
    Scen1Description = _m.Attribute(str)    
    Scen1Start = _m.Attribute(int)
    Scen1End = _m.Attribute(int)

    Scen2UnNumber = _m.Attribute(int)
    Scen2UnDescription = _m.Attribute(str)
    Scen2Number = _m.Attribute(int)
    Scen2Description = _m.Attribute(str)    
    Scen2Start = _m.Attribute(int)
    Scen2End = _m.Attribute(int)

    Scen3UnNumber = _m.Attribute(int)
    Scen3UnDescription = _m.Attribute(str)
    Scen3Number = _m.Attribute(int)
    Scen3Description = _m.Attribute(str)    
    Scen3Start = _m.Attribute(int)
    Scen3End = _m.Attribute(int)

    Scen4UnNumber = _m.Attribute(int)
    Scen4UnDescription = _m.Attribute(str)
    Scen4Number = _m.Attribute(int)
    Scen4Description = _m.Attribute(str)    
    Scen4Start = _m.Attribute(int)
    Scen4End = _m.Attribute(int)

    Scen5UnNumber = _m.Attribute(int)
    Scen5UnDescription = _m.Attribute(str)
    Scen5Number = _m.Attribute(int)
    Scen5Description = _m.Attribute(str)    
    Scen5Start = _m.Attribute(int)
    Scen5End = _m.Attribute(int)
    
    TransitServiceTableFile = _m.Attribute(str)
    AggTypeSelectionFile = _m.Attribute(str)
    DefaultAgg = _m.Attribute(str)  
    
    PublishFlag = _m.Attribute(bool)
    
    NodeFilterAttributeId = _m.Attribute(str)
    StopFilterAttributeId = _m.Attribute(str)
    ConnectorFilterAttributeId = _m.Attribute(str)
    
    AttributeAggregatorString = _m.Attribute(str)

    LineFilterExpression = _m.Attribute(str)     
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario

        self.Scen1UnNumber = 10
        self.Scen1UnDescription = "AM Uncleaned"
        self.Scen1Number = 11
        self.Scen1Description = "AM Cleaned"    
        self.Scen1Start = 600
        self.Scen1End = 900

        self.Scen2UnNumber = 20
        self.Scen2UnDescription = "MD Uncleaned"
        self.Scen2Number = 21
        self.Scen2Description = "MD Cleaned"    
        self.Scen2Start = 900
        self.Scen2End = 1500
                
        self.Scen3UnNumber = 30
        self.Scen3UnDescription = "PM Uncleaned"
        self.Scen3Number = 31
        self.Scen3Description = "PM Cleaned"    
        self.Scen3Start = 1500
        self.Scen3End = 1900

        self.Scen4UnNumber = 40
        self.Scen4UnDescription = "EV Uncleaned"
        self.Scen4Number = 41
        self.Scen4Description = "EV Cleaned"    
        self.Scen4Start = 1900
        self.Scen4End = 2400

        self.Scen5UnNumber = 49
        self.Scen5UnDescription = "ON Uncleaned"
        self.Scen5Number = 50
        self.Scen5Description = "ON Cleaned"    
        self.Scen5Start = 0
        self.Scen5End = 600
        
        self.DefaultAgg = 'n'
        
        self.PublishFlag = True 
        
        lines = ["vdf: force",
                 "length: sum",
                 "type: first",
                 "lanes: force",
                 "ul1: avg",
                 "ul2: force",
                 "ul3: force",
                 "dwt: sum",
                 "dwfac: force",
                 "ttf: force",
                 "us1: avg_by_length",
                 "us2: avg",
                 "us3: avg",
                 "ui1: avg",
                 "ui2: avg",
                 "ui3: avg",
                 "@stn1: force",
                 "@stn2: force"]
        
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
        
        # by default, prorate all transit speeds except TTC rail and GO rail
        self.LineFilterExpression = "line=______ xor line=TS____ xor line=GT____" 

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Full Network Set Generator v%s" %self.version,
                     description="Builds a full set of cleaned time period network \
                         from a single base network. Make sure that the base network \
                         includes a zone system before running the tool. \
                         <br><b>Warning: this tool will overwrite scenarios in the  \
                         selected locations!</b>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)

        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='TransitServiceTableFile',
                           window_type='file', file_filter='*.csv',
                           title="Transit service table",
                           note="Requires three columns:\
                               <ul><li>emme_id</li>\
                               <li>trip_depart</li>\
                               <li>trip_arrive</li></ul>")

        pb.add_select_file(tool_attribute_name='AggTypeSelectionFile',
                           window_type='file', file_filter='*.csv',
                           title="Aggregation Type Selection",
                           note="Requires two columns:\
                               <ul><li>emme_id</li>\
                               <li>agg_type</li></ul>")

        keyval1 = {'n':'Naive', 'a':'Average'}
        pb.add_radio_group(tool_attribute_name='DefaultAgg', 
                           keyvalues= keyval1,
                           title= "Default Aggregation Type",
                           note="Used if line not in\
                               agg selection file")

        pb.add_header("SCENARIOS")

        with pb.add_table(False) as t:
        
            t.add_table_header(['Scenario', 'Number', 'Description'])

            with t.table_cell():
                pb.add_html("Scenario 1 uncleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1UnNumber',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1UnDescription',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 1 cleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1Number',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1Description',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 2 uncleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2UnNumber',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2UnDescription',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 2 cleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2Number',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2Description',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 3 uncleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3UnNumber',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3UnDescription',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 3 cleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3Number',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3Description',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 4 uncleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4UnNumber',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4UnDescription',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 4 cleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4Number',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4Description',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 5 uncleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5UnNumber',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5UnDescription',
                                size=40)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 5 cleaned")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5Number',
                                size=10)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5Description',
                                size=40)
        
        pb.add_checkbox(tool_attribute_name= 'PublishFlag',
                        label= "Publish network?")

        pb.add_header("TIME PERIODS")
        pb.add_html("In integer hours e.g. 2:30 PM = 1430")

        with pb.add_table(False) as t:
        
            t.add_table_header(['Scenario', 'Start', 'End'])

            with t.table_cell():
                pb.add_html("Scenario 1")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1Start',
                                size=4)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen1End',
                                size=4)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 2")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2Start',
                                size=4)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen2End',
                                size=4)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 3")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3Start',
                                size=4)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen3End',
                                size=4)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 4")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4Start',
                                size=4)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen4End',
                                size=4)
            t.new_row()

            with t.table_cell():
                pb.add_html("Scenario 5")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5Start',
                                size=4)
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='Scen5End',
                                size=4)
                    
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
       
        pb.add_text_box(tool_attribute_name='LineFilterExpression',
                        title="Line Filter Expression",
                        note='Select set of lines to prorate transit speeds.',
                        size=100, multi_line=True) 
        
        pb.add_header("AGGREGATION FUNCTIONS")
        
        h = HTML()
        ul = h.ul
        ul.li("first - Uses the first element's attribute")
        ul.li("last - Uses the last element's attribute")
        ul.li("sum - Add the two attributes")
        ul.li("avg - Averages the two attributes")
        ul.li("avg_by_length - Average the two attributes, weighted by link length")
        ul.li("min - The minimum of the two attributes")
        ul.li("max - The maximum of the two attributes")
        ul.li("and - Boolean AND")
        ul.li("or - Boolean OR")
        ul.li("force - Forces the tool to keep the node if the two attributes are different")
        
        pb.add_text_box(tool_attribute_name='AttributeAggregatorString',
                        size= 500, multi_line=True,
                        title= "Attribute Aggregation Functions",
                        note= "List of network NODE, LINK, and TRANSIT SEGMENT attributes to named \
                        aggregator functions. These functions are applied when links or segments are \
                        aggregated. Links inherit the attributes of their i-node.\
                        <br><br><b>Syntax:</b> [<em>attribute name</em>] : [<em>function</em>] , ... \
                        <br><br>Separate (attribute-function) pairs with a comma or new line. Either \
                        the Emme Desktop attribute names (e.g. 'lanes') or the Modeller API names \
                        (e.g. 'num_lanes') can be used. Accepted functions are: " + str(ul) + \
                        "The default function for unspecified extra attribtues is 'sum.'")

        return pb.render()

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
          
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
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
                        
            network = self.BaseScenario.get_network()
            
            firstScenario = (self.Scen1UnNumber, self.Scen1Number, self.Scen1UnDescription, self.Scen1Description,
                             self.Scen1Start, self.Scen1End)
            secondScenario = (self.Scen2UnNumber, self.Scen2Number, self.Scen2UnDescription, self.Scen2Description,
                             self.Scen2Start, self.Scen2End)
            thirdScenario = (self.Scen3UnNumber, self.Scen3Number, self.Scen3UnDescription, self.Scen3Description,
                             self.Scen3Start, self.Scen3End)
            fourthScenario = (self.Scen4UnNumber, self.Scen4Number, self.Scen4UnDescription, self.Scen4Description,
                             self.Scen4Start, self.Scen4End)
            fifthScenario = (self.Scen5UnNumber, self.Scen5Number, self.Scen5UnDescription, self.Scen5Description,
                             self.Scen5Start, self.Scen5End)
            scenarioSet = [firstScenario, secondScenario, thirdScenario, fourthScenario, fifthScenario]
            
            # Create time period networks in all the unclean scenario spots
            # Calls create_transit_time_period
            for scenarios in scenarioSet:
                createTimePeriod(self.BaseScenario, scenarios[0], scenarios[2], self.TransitServiceTableFile,
                                 self.AggTypeSelectionFile, self.DefaultAgg, scenarios[4], scenarios[5])

            print "Created uncleaned time period networks"

            # Prorate the transit speeds in all uncleaned networks
            for scenarios in scenarioSet:
                prorateTransitSpeed(scenarios[0], self.LineFilterExpression)

            print "Prorated transit speeds"

            for scenarios in scenarioSet:
                removeExtraNodes(scenarios[0], scenarios[1], scenarios[3], self.PublishFlag, self.NodeFilterAttributeId,
                                 self.StopFilterAttributeId, self.ConnectorFilterAttributeId, self.AttributeAggregatorString)
            
            print "Cleaned networks"
                
            self.BaseScenario.publish_network(network)
            self.TRACKER.completeTask()



    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg