'''
    Copyright 2015-2016 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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

    Authors: mattaustin222, JamesVaughan, nasterska

    Latest revision by: nasterska
    
    
    This tool takes in a base network with zones and
    generates a full set of usable cleaned time
    period networks. The goal is that this tool
    will replace the standard TMG workflow from
    base to time period networks.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-02-09 by mattaustin222
    0.1.0 Created on 2015-02-18 by mattaustin222 Made callable by XTMF
    0.1.1 Added ability to apply .nup files to uncleaned time period networks
    0.2.0 Added an optional custom scenario definition list. This removes the restriction
        of using exactly five time periods. Note that the call function no longer supports
        the old system. However, the original form is still available through the modeller
        interface.
    0.3.0 Added the ability to load in multiple alt files, this helps enhance work flow by not
        requiring all edits to be in the same document.  Typically this will get used by having
        a master alt file, and then an additional one containing scenario specific changes.
    0.3.1 Added call to remove_extra_links tool. 2016-08-24
    
'''

import inro.modeller as _m
import traceback as _traceback
import os
from contextlib import contextmanager
from contextlib import nested
from html import HTML
from re import split as _regex_split
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

removeExtraNodes = _MODELLER.tool('tmg.network_editing.remove_extra_nodes')
removeExtraLinks = _MODELLER.tool('tmg.network_editing.remove_extra_links')
prorateTransitSpeed = _MODELLER.tool('tmg.network_editing.prorate_transit_speed')
createTimePeriod = _MODELLER.tool('tmg.network_editing.time_of_day_changes.create_transit_time_period')
applyNetUpdate = _MODELLER.tool('tmg.input_output.import_network_update')
lineEdit = _MODELLER.tool('tmg.XTMF_internal.apply_batch_line_edits')

##########################################################################################################

class FullNetworkSetGenerator(_m.Tool()):
    
    version = '0.3.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
                
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    BaseScenario = _m.Attribute(_m.InstanceType) 
        
    Scen1UnNumber = _m.Attribute(int)
    Scen1UnDescription = _m.Attribute(str)    
    Scen1Number = _m.Attribute(int)
    Scen1Description = _m.Attribute(str)    
    Scen1Start = _m.Attribute(int)
    Scen1End = _m.Attribute(int)
    Scen1NetworkUpdateFile = _m.Attribute(str)

    Scen2UnNumber = _m.Attribute(int)
    Scen2UnDescription = _m.Attribute(str)
    Scen2Number = _m.Attribute(int)
    Scen2Description = _m.Attribute(str)    
    Scen2Start = _m.Attribute(int)
    Scen2End = _m.Attribute(int)    
    Scen2NetworkUpdateFile = _m.Attribute(str)

    Scen3UnNumber = _m.Attribute(int)
    Scen3UnDescription = _m.Attribute(str)
    Scen3Number = _m.Attribute(int)
    Scen3Description = _m.Attribute(str)    
    Scen3Start = _m.Attribute(int)
    Scen3End = _m.Attribute(int)    
    Scen3NetworkUpdateFile = _m.Attribute(str)

    Scen4UnNumber = _m.Attribute(int)
    Scen4UnDescription = _m.Attribute(str)
    Scen4Number = _m.Attribute(int)
    Scen4Description = _m.Attribute(str)    
    Scen4Start = _m.Attribute(int)
    Scen4End = _m.Attribute(int)
    Scen4NetworkUpdateFile = _m.Attribute(str)

    Scen5UnNumber = _m.Attribute(int)
    Scen5UnDescription = _m.Attribute(str)
    Scen5Number = _m.Attribute(int)
    Scen5Description = _m.Attribute(str)    
    Scen5Start = _m.Attribute(int)
    Scen5End = _m.Attribute(int)
    Scen5NetworkUpdateFile = _m.Attribute(str)
    
    TransitServiceTableFile = _m.Attribute(str)
    AggTypeSelectionFile = _m.Attribute(str)
    AlternativeDataFile = _m.Attribute(str)
    AdditionalAlternativeDataFiles = _m.Attribute(str)
    BatchEditFile = _m.Attribute(str)
    DefaultAgg = _m.Attribute(str) 
    
    TransferModesString = _m.Attribute(str) 
    TransferModeList = _m.Attribute(_m.ListType)
    
    PublishFlag = _m.Attribute(bool)
    OverwriteScenarioFlag = _m.Attribute(bool)
    
    NodeFilterAttributeId = _m.Attribute(str)
    StopFilterAttributeId = _m.Attribute(str)
    ConnectorFilterAttributeId = _m.Attribute(str)
    
    AttributeAggregatorString = _m.Attribute(str)

    CustomScenarioSetString = _m.Attribute(str)
    CustomScenarioSetFlag = _m.Attribute(bool)

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
        self.OverwriteScenarioFlag = False
        
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
                 "ui3: avg"]
        
        domains = set(['NODE', 'LINK', 'TRANSIT_SEGMENT'])
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type in domains:
                if exatt.name == "@stn1" or exatt.name == "@stn2":
                    lines.append("%s: force" %exatt.name)
                else:
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

        self.CustomScenarioSetFlag = False

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Full Network Set Generator v%s" %self.version,
                     description="Builds a full set of cleaned time period network \
                         from a single base network. Make sure that the base network \
                         includes a zone system before running the tool. \
                         <br><b>Warning: this tool will overwrite scenarios in the  \
                         selected locations!</b> \
                         <br><b>Warning: changing the base scenario may cause \
                         errors. It is recommended that you make your desired \
                         base scenario active first.</b>",
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

        pb.add_select_file(tool_attribute_name='AlternativeDataFile',
                           window_type='file', file_filter='*.csv',
                           title="Data for non-service table lines (optional)",
                           note="Requires columns as follows,\
                               where xxxx corresponds to\
                               the desired time period start:\
                               <ul><li>emme_id</li>\
                               <li>xxxx_hdw</li>\
                               <li>xxxx_spd</li></ul>\
                               Note: this will override\
                               values calculated from\
                               the service table")

        pb.add_select_file(tool_attribute_name='AggTypeSelectionFile',
                           window_type='file', file_filter='*.csv',
                           title="Aggregation Type Selection",
                           note="Requires two columns:\
                               <ul><li>emme_id</li>\
                               <li>agg_type</li></ul>")

        pb.add_select_file(tool_attribute_name='BatchEditFile',
                           window_type='file', file_filter='*.csv',
                           title="Batch Line Editing (optional)",
                           note="Requires at least three columns\
                               (multiple additional hdw/spd pairs can\
                               be added; x refers to a scenario number):\
                               <ul><li>filter</li>\
                               <li>x_hdwchange</li>\
                               <li>x_spdchange</li></ul>")

        keyval1 = {'n':'Naive', 'a':'Average'}
        pb.add_radio_group(tool_attribute_name='DefaultAgg', 
                           keyvalues= keyval1,
                           title= "Default Aggregation Type",
                           note="Used if line not in\
                               agg selection file")

        pb.add_header("SCENARIOS")         
        
        pb.add_checkbox(tool_attribute_name='OverwriteScenarioFlag',
                           label="Overwrite Full Scenarios?")
        
        pb.add_checkbox(tool_attribute_name= 'PublishFlag',
                        label= "Publish network?")
        
        pb.add_checkbox(tool_attribute_name='CustomScenarioSetFlag',
                           label="Use custom scenario list?")

        pb.add_text_box(tool_attribute_name='CustomScenarioSetString',
                        size= 500, multi_line=True,
                        title= "Custom Scenario List",
                        note= "Definitions for a custom set of scenarios.\
                        Use the following syntax. The .nup file is optional.\
                        <br><br><b>Syntax:</b> [<em>Uncleaned scenario number</em>] : [<em>Cleaned scenario number</em>] : [<em>Uncleaned scenario description</em>] : [<em>Cleaned scenario description</em>] : [<em>Scenario start</em>] : [<em>Scenario End</em>] : [<em>.nup file</em>]\
                        <br><br>Use integer hours for start and end times e.g. 2:30 PM = 1430")              
        
        with pb.add_table(False) as t:
        
            pb.add_text_element("Note that network update files (*.nup) are applied to the uncleaned scenarios.")
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
                pb.add_html("")

            with t.table_cell():
                pb.add_html("Scenario 1 network update file")
            
            with t.table_cell():
                pb.add_select_file(tool_attribute_name='Scen1NetworkUpdateFile',
                           window_type='file', file_filter='*.nup')

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
                pb.add_html("")

            with t.table_cell():
                pb.add_html("Scenario 2 network update file")
            
            with t.table_cell():
                pb.add_select_file(tool_attribute_name='Scen2NetworkUpdateFile',
                           window_type='file', file_filter='*.nup')

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
                pb.add_html("")

            with t.table_cell():
                pb.add_html("Scenario 3 network update file")
            
            with t.table_cell():
                pb.add_select_file(tool_attribute_name='Scen3NetworkUpdateFile',
                           window_type='file', file_filter='*.nup')
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
                pb.add_html("")

            with t.table_cell():
                pb.add_html("Scenario 4 network update file")
            
            with t.table_cell():
                pb.add_select_file(tool_attribute_name='Scen4NetworkUpdateFile',
                           window_type='file', file_filter='*.nup')

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

            t.new_row()

            with t.table_cell():
                pb.add_html("")

            with t.table_cell():
                pb.add_html("Scenario 5 network update file")
            
            with t.table_cell():
                pb.add_select_file(tool_attribute_name='Scen5NetworkUpdateFile',
                           window_type='file', file_filter='*.nup')

        pb.add_header("TIME PERIODS")
        

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
                    
        pb.add_text_element("In integer hours e.g. 2:30 PM = 1430")

        pb.add_header("TRANSFER MODES")

        self.TransferModeList = [self.BaseScenario.mode('u'),
                            self.BaseScenario.mode('t'),
                            self.BaseScenario.mode('y')]

        pb.add_select_mode(tool_attribute_name='TransferModeList',
                           filter=[ 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Transfer Modes:',
                           note='Select all transfer modes.')

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
        
        if (tool.check_scen_set_flag())
        {
            $("#CustomScenarioSetString").prop('disabled', false);
            $("#Scen1UnNumber").prop('disabled', true);
            $("#Scen1UnDescription").prop('disabled', true);
            $("#Scen1Number").prop('disabled', true);
            $("#Scen1Description").prop('disabled', true);
            $("#Scen1Start").prop('disabled', true);
            $("#Scen1End").prop('disabled', true);
            $("#Scen1NetworkUpdateFile").prop('disabled', true);
            $("#Scen2UnNumber").prop('disabled', true);
            $("#Scen2UnDescription").prop('disabled', true);
            $("#Scen2Number").prop('disabled', true);
            $("#Scen2Description").prop('disabled', true);
            $("#Scen2Start").prop('disabled', true);
            $("#Scen2End").prop('disabled', true);
            $("#Scen2NetworkUpdateFile").prop('disabled', true);
            $("#Scen3UnNumber").prop('disabled', true);
            $("#Scen3UnDescription").prop('disabled', true);
            $("#Scen3Number").prop('disabled', true);
            $("#Scen3Description").prop('disabled', true);
            $("#Scen3Start").prop('disabled', true);
            $("#Scen3End").prop('disabled', true);
            $("#Scen3NetworkUpdateFile").prop('disabled', true);
            $("#Scen4UnNumber").prop('disabled', true);
            $("#Scen4UnDescription").prop('disabled', true);
            $("#Scen4Number").prop('disabled', true);
            $("#Scen4Description").prop('disabled', true);
            $("#Scen4Start").prop('disabled', true);
            $("#Scen4End").prop('disabled', true);
            $("#Scen4NetworkUpdateFile").prop('disabled', true);
            $("#Scen5UnNumber").prop('disabled', true);
            $("#Scen5UnDescription").prop('disabled', true);
            $("#Scen5Number").prop('disabled', true);
            $("#Scen5Description").prop('disabled', true);
            $("#Scen5Start").prop('disabled', true);
            $("#Scen5End").prop('disabled', true);
            $("#Scen5NetworkUpdateFile").prop('disabled', true);
        } else {
            $("#CustomScenarioSetString").prop('disabled', true);
            $("#Scen1UnNumber").prop('disabled', false);
            $("#Scen1UnDescription").prop('disabled', false);
            $("#Scen1Number").prop('disabled', false);
            $("#Scen1Description").prop('disabled', false);
            $("#Scen1Start").prop('disabled', false);
            $("#Scen1End").prop('disabled', false);
            $("#Scen1NetworkUpdateFile").prop('disabled', false);
            $("#Scen2UnNumber").prop('disabled', false);
            $("#Scen2UnDescription").prop('disabled', false);
            $("#Scen2Number").prop('disabled', false);
            $("#Scen2Description").prop('disabled', false);
            $("#Scen2Start").prop('disabled', false);
            $("#Scen2End").prop('disabled', false);
            $("#Scen2NetworkUpdateFile").prop('disabled', false);
            $("#Scen3UnNumber").prop('disabled', false);
            $("#Scen3UnDescription").prop('disabled', false);
            $("#Scen3Number").prop('disabled', false);
            $("#Scen3Description").prop('disabled', false);
            $("#Scen3Start").prop('disabled', false);
            $("#Scen3End").prop('disabled', false);
            $("#Scen3NetworkUpdateFile").prop('disabled', false);
            $("#Scen4UnNumber").prop('disabled', false);
            $("#Scen4UnDescription").prop('disabled', false);
            $("#Scen4Number").prop('disabled', false);
            $("#Scen4Description").prop('disabled', false);
            $("#Scen4Start").prop('disabled', false);
            $("#Scen4End").prop('disabled', false);
            $("#Scen4NetworkUpdateFile").prop('disabled', false);
            $("#Scen5UnNumber").prop('disabled', false);
            $("#Scen5UnDescription").prop('disabled', false);
            $("#Scen5Number").prop('disabled', false);
            $("#Scen5Description").prop('disabled', false);
            $("#Scen5Start").prop('disabled', false);
            $("#Scen5End").prop('disabled', false);
            $("#Scen5NetworkUpdateFile").prop('disabled', false);
        }

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

        $("#CustomScenarioSetFlag").bind('change', function()
        {
            $(this).commit();
            var not_flag = ! tool.check_scen_set_flag();
            var flag = tool.check_scen_set_flag();
            
            $("#CustomScenarioSetString").prop('disabled', not_flag);
            $("#Scen1UnNumber").prop('disabled', flag);
            $("#Scen1UnDescription").prop('disabled', flag);
            $("#Scen1Number").prop('disabled', flag);
            $("#Scen1Description").prop('disabled', flag);
            $("#Scen1Start").prop('disabled', flag);
            $("#Scen1End").prop('disabled', flag);
            $("#Scen1NetworkUpdateFile").prop('disabled', flag);
            $("#Scen2UnNumber").prop('disabled', flag);
            $("#Scen2UnDescription").prop('disabled', flag);
            $("#Scen2Number").prop('disabled', flag);
            $("#Scen2Description").prop('disabled', flag);
            $("#Scen2Start").prop('disabled', flag);
            $("#Scen2End").prop('disabled', flag);
            $("#Scen2NetworkUpdateFile").prop('disabled', flag);
            $("#Scen3UnNumber").prop('disabled', flag);
            $("#Scen3UnDescription").prop('disabled', flag);
            $("#Scen3Number").prop('disabled', flag);
            $("#Scen3Description").prop('disabled', flag);
            $("#Scen3Start").prop('disabled', flag);
            $("#Scen3End").prop('disabled', flag);
            $("#Scen3NetworkUpdateFile").prop('disabled', flag);
            $("#Scen4UnNumber").prop('disabled', flag);
            $("#Scen4UnDescription").prop('disabled', flag);
            $("#Scen4Number").prop('disabled', flag);
            $("#Scen4Description").prop('disabled', flag);
            $("#Scen4Start").prop('disabled', flag);
            $("#Scen4End").prop('disabled', flag);
            $("#Scen4NetworkUpdateFile").prop('disabled', flag);
            $("#Scen5UnNumber").prop('disabled', flag);
            $("#Scen5UnDescription").prop('disabled', flag);
            $("#Scen5Number").prop('disabled', flag);
            $("#Scen5Description").prop('disabled', flag);
            $("#Scen5Start").prop('disabled', flag);
            $("#Scen5End").prop('disabled', flag);
            $("#Scen5NetworkUpdateFile").prop('disabled', flag);
        });

        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()

    ##########################################################################################################
    def __call__(self, xtmf_ScenarioNumber, CustomScenarioSetString,
                 TransitServiceTableFile, AggTypeSelectionFile, AlternativeDataFile, BatchEditFile,
                 DefaultAgg, PublishFlag, TransferModesString, OverwriteScenarioFlag, NodeFilterAttributeId,
                 StopFilterAttributeId, ConnectorFilterAttributeId, AttributeAggregatorString,
                 LineFilterExpression, AdditionalAlternativeDataFiles):

        #---1 Set up scenario
        self.BaseScenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.BaseScenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        #---2 Set up attributes
        if NodeFilterAttributeId.lower() == "none":
            self.NodeFilterAttributeId = None
        else:
            if self.BaseScenario.extra_attribute(NodeFilterAttributeId) is None:
                raise Exception("Node filter attribute %s does not exist" %NodeFilterAttributeId)
            self.NodeFilterAttributeId = NodeFilterAttributeId

        if StopFilterAttributeId.lower() == "none":
            self.StopFilterAttributeId = None
        else:
            if self.BaseScenario.extra_attribute(StopFilterAttributeId) is None:
                raise Exception("Stop filter attribute %s does not exist" %StopFilterAttributeId)
            self.StopFilterAttributeId = StopFilterAttributeId
        if ConnectorFilterAttributeId.lower() == "none":
            self.ConnectorFilterAttributeId = None
        else:
            if self.BaseScenario.extra_attribute(ConnectorFilterAttributeId) is None:
                raise Exception("Connector filter attribute %s does not exist" %ConnectorFilterAttributeId)
            self.ConnectorFilterAttributeId = ConnectorFilterAttributeId
        
        #--3 Set up other parameters
        if TransitServiceTableFile.lower() == "none":
            self.TransitServiceTableFile = None
        else:
            self.TransitServiceTableFile = TransitServiceTableFile
        if AggTypeSelectionFile.lower() == "none":
            self.AggTypeSelectionFile = None
        else:
            self.AggTypeSelectionFile = AggTypeSelectionFile
        if AlternativeDataFile.lower() == "none":
            self.AlternativeDataFile = None
        else:
            self.AlternativeDataFile = AlternativeDataFile
        if BatchEditFile.lower() == "none":
            self.BatchEditFile = None
        else:
            self.BatchEditFile = BatchEditFile

        self.TransferModesString = TransferModesString

        self.DefaultAgg = DefaultAgg
        self.PublishFlag = PublishFlag
        self.OverwriteScenarioFlag = OverwriteScenarioFlag
        self.AttributeAggregatorString = AttributeAggregatorString
        self.LineFilterExpression = LineFilterExpression
        
        self.CustomScenarioSetFlag = True
        self.CustomScenarioSetString = CustomScenarioSetString
        self.AdditionalAlternativeDataFiles = AdditionalAlternativeDataFiles


        print "Running full network set generation"
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
        
        print "Done full network generation"

        
    ##########################################################################################################          
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        self.AdditionalAlternativeDataFiles = None
        self.TransferModeList = ""

        if self.TransferModeList:
            for mode in self.TransferModeList:
                self.TransferModesString += mode.id

        try:
            self._Execute()           
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise        
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")

    @_m.method(return_type= bool)
    def check_scen_set_flag(self):
        return self.CustomScenarioSetFlag

    @_m.method(return_type=unicode)
    def get_scenario_node_attributes(self):
        options = ['<option value="-1">No attribute</option>']
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'NODE': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.name, text)) 
        
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def get_scenario_link_attributes(self):
        options = ['<option value="-1">No attribute</option>']
        for exatt in self.BaseScenario.extra_attributes():
            if exatt.type != 'LINK': continue
            text = "%s - %s" %(exatt.name, exatt.description)
            options.append('<option value="%s">%s</option>' %(exatt.name, text)) 
        
        return "\n".join(options)

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
                        
            network = self.BaseScenario.get_network()
            
            if not self.CustomScenarioSetFlag:
                firstScenario = [self.Scen1UnNumber, self.Scen1Number, self.Scen1UnDescription, self.Scen1Description,
                                 self.Scen1Start, self.Scen1End, self.Scen1NetworkUpdateFile]
                secondScenario = [self.Scen2UnNumber, self.Scen2Number, self.Scen2UnDescription, self.Scen2Description,
                                 self.Scen2Start, self.Scen2End, self.Scen2NetworkUpdateFile]
                thirdScenario = [self.Scen3UnNumber, self.Scen3Number, self.Scen3UnDescription, self.Scen3Description,
                                 self.Scen3Start, self.Scen3End, self.Scen3NetworkUpdateFile]
                fourthScenario = [self.Scen4UnNumber, self.Scen4Number, self.Scen4UnDescription, self.Scen4Description,
                                 self.Scen4Start, self.Scen4End, self.Scen4NetworkUpdateFile]
                fifthScenario = [self.Scen5UnNumber, self.Scen5Number, self.Scen5UnDescription, self.Scen5Description,
                                 self.Scen5Start, self.Scen5End, self.Scen5NetworkUpdateFile]
                scenarioSet = [firstScenario, secondScenario, thirdScenario, fourthScenario, fifthScenario]

            else:
                scenarioSet = self._ParseCustomScenarioSet()
            
            if self.OverwriteScenarioFlag:
                self._DeleteOldScenarios(scenarioSet)
            
            # Create time period networks in all the unclean scenario spots
            # Calls create_transit_time_period
            for scenarios in scenarioSet:
                createTimePeriod(self.BaseScenario, scenarios[0], scenarios[2], self.TransitServiceTableFile,
                                 self.AggTypeSelectionFile, self.AlternativeDataFile,
                                 self.DefaultAgg, scenarios[4], scenarios[5], self.AdditionalAlternativeDataFiles)
                if not (scenarios[6] is None or scenarios[6].lower() == "none"):
                    applyNetUpdate(str(scenarios[0]),scenarios[6])                

            print "Created uncleaned time period networks and applied network updates"

            if self.BatchEditFile:
                for scenarios in scenarioSet:
                    lineEdit(scenarios[0], self.BatchEditFile) #note that batch edit file should use uncleaned scenario numbers
                print "Edited transit line data"

            # Prorate the transit speeds in all uncleaned networks
            for scenarios in scenarioSet:
                prorateTransitSpeed(scenarios[0], self.LineFilterExpression)

            print "Prorated transit speeds"

            for scenarios in scenarioSet:
                removeExtraLinks(scenarios[0], self.TransferModesString, True, scenarios[1], scenarios[3])
                
                removeExtraNodes(scenarios[1], self.NodeFilterAttributeId, self.StopFilterAttributeId, self.ConnectorFilterAttributeId, self.AttributeAggregatorString)
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

    def _DeleteOldScenarios(self, scenarios):
        bank = _MODELLER.emmebank
        for items in scenarios:
            if bank.scenario(items[0]):
                bank.delete_scenario(items[0])
            if bank.scenario(items[1]):
                bank.delete_scenario(items[1])

    def _ParseCustomScenarioSet(self):
        scenarioDataList = []
        components = _regex_split('\n|,', self.CustomScenarioSetString) #Supports newline and/or commas
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) not in [6,7]:
				if len(parts) == 8:
					checkPath = parts[6] + ":" + parts[7]
					if os.path.exists(os.path.dirname(checkPath)):
						parts[6]=checkPath
						del parts[7]
					else:				
						msg = "Please verify that your scenario set is separated correctly and/or that the .nup file has a valid path"
						msg += ". [%s]" %component 
						raise SyntaxError(msg)
				else:
					msg = "Error parsing scenario set: Separate components with colons \
							Uncleaned scenario number:Cleaned scenario number:Uncleaned scenario description:Cleaned scenario description:Scenario start:Scenario End:.nup file"
					msg += ". [%s]" %component 
					raise SyntaxError(msg)
            partsList = [int(parts[0]), int(parts[1]), parts[2], parts[3], int(parts[4]), int(parts[5])]
            if len(parts) == 7:
                if parts[6].lower() == 'none':
                    partsList.append(None)                    
                    scenarioDataList.append(partsList)
                    continue
                if not parts[6].strip()[-4:] == ".nup":
                    msg = "Network update file must be in the .nup format"
                    msg += ". [%s]" %component 
                    raise SyntaxError(msg)
                partsList.append(parts[6])
            else:
                partsList.append(None)
            scenarioDataList.append(partsList)

        return scenarioDataList
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
