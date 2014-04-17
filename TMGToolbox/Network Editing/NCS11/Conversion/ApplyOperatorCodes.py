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
Apply Operator Codes

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-04-16 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ApplyOperatorCodes(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    AttributeId = _m.Attribute(str)
    CodeOption = _m.Attribute(int)
    
    LINE_GROUPS_ALPHA_OP = [(1, "line=B_____", "Brampton"),
                            (2, "line=HB____", "Burlington"),
                               (3, "line=D_____", "Durham"),
                               (4, "mode=gr", "GO"),
                               (5, "line=H_____", "Halton"),
                               (6, "line=W_____", 'Hamilton'),
                               (7, "line=HM____", "Milton"),
                               (8, "line=M_____", "Mississauga"),
                               (9, "line=HO____", "Oakville"),
                               (10, "line=T_____", "TTC"),
                               (11, "line=Y_____", "YRT")]
    
    LINE_GROUPS_ALPHA_OP_MODE = [(1, "line=B_____", "Brampton"),
                                  (2, "line=HB____", "Burlington"),
                               (3, "line=D_____", "Durham"),
                               (4, "mode=g", "GO Bus"),
                               (5, "mode=r", "GO Train"),
                               (6, "line=W_____", 'Hamilton'),
                               (7, "line=HM____", "Milton"),
                               (8, "line=M_____", "Mississauga"),
                               (9, "line=HO____", "Oakville"),
                               (10, "line=T_____ and mode=b", "TTC Bus"),
                               (11, "mode=s", "TTC Streetcar"),
                               (12, "mode=m", "TTC Subway"),
                               (14, "line=Y_____", "YRT"),
                               (13, "line=YV____", "VIVA")]
    
    LINE_GROUPS_NCS11 = [(24, "line=B_____", "Brampton"),
                           (80, "line=D_____", "Durham"),
                           (65, "mode=g", "GO Bus"),
                           (90, "mode=r", "GO Train"),
                           (46, "line=HB____", "Burlington"),
                           (44, "line=HM____", "Milton"),
                           (42, "line=HO____", "Oakville"),
                           (60, "line=W_____", 'Hamilton'),
                           (20, "line=M_____", "Mississauga"),
                           (26, "line=T_____", "TTC"),
                           (70, "line=Y_____", "YRT")]
    
    LINE_GROUPS_GTAMV4 = [(1, "line=B_____", "Brampton"),
                           (2, "line=D_____", "Durham"),
                           (3, "mode=g", "GO Bus"),
                           (4, "mode=r", "GO Train"),
                           (5, "line=H_____", "Halton"),
                           (6, "line=W_____", 'Hamilton'),
                           (7, "line=M_____", "Mississauga"),
                           (8, "mode=s", "Streetcar"),
                           (9, "mode=m", "Subway"),
                           (10, "line=T_____ and mode=b", "TTC Bus"),
                           (12, "line=Y_____", "YRT"),
                           (11, "line=YV____", "VIVA")]
    
    __options = {1: LINE_GROUPS_NCS11,
                 2: LINE_GROUPS_ALPHA_OP,
                 3: LINE_GROUPS_ALPHA_OP_MODE,
                 4: LINE_GROUPS_GTAMV4}
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Apply Operator Codes v%s" %self.version,
                     description="Applies a numerical operator code to groups of lines, \
                         for several pre-set line groups. The code can be saved to the \
                         standard UT1 attribute, or any transit line extra attribute. \
                         The grouping scheme is written to the logbook.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        keyval = {'ut1': 'ut1 - STANDARD - Line data 1'}
        for att in self.Scenario.extra_attributes():
            if att.type != 'TRANSIT_LINE': continue
            val = "%s - EXTRA - %s" %(att.name, att.description)
            keyval[att.name] = val
        pb.add_select(tool_attribute_name='AttributeId',
                      keyvalues=keyval,
                      title="Attribute To Save Into",
                      note="Can select UT1 or any transit line extra attribute")
        
        keyval2 = {1: "1: NCS11 Operator Codes",
                   2: "2: Alphabetical by operator",
                   3: "3: Alphabetical by operator and mode",
                   4: "4: GTAModel V4 Operator Codes"}
        pb.add_select(tool_attribute_name='CodeOption',
                      keyvalues=keyval2,
                      title="Grouping Scheme")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {        
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#AttributeId")
                .empty()
                .append(tool.get_line_attributes())
            inro.modeller.page.preload("#AttributeId");
            $("#AttributeId").trigger('change');
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
            
            groupings = self.__options[self.CodeOption]
            
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
            def flagGroup(value, selector, descr):
                spec= {
                        "result": self.AttributeId,
                        "expression": str(value),
                        "aggregation": None,
                        "selections": {
                            "transit_line": selector
                        },
                        "type": "NETWORK_CALCULATION"
                    }
                with _m.logbook_trace("Flagging %s lines as %s" %(descr, value)):
                    tool(spec, scenario=self.Scenario)
            
            self.TRACKER.startProcess(len(groupings))
            for value, selector, description in groupings:
                flagGroup(value, selector, description)
                self.TRACKER.completeSubtask()
                
            self._WriteTableReport(groupings)

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _WriteTableReport(self, groupings):
        pb = _m.PageBuilder()
        
        html = "<table><tr><th>Group<th>Code</tr>"
        for value, selector, description in groupings:
            html += "<tr><td>%s<td>%s</tr>" %(description, value)
        html += "</table>"
        
        pb.wrap_html(title="Grouping Table", body=html, note="Codes saved into transit line attribute %s" %self.AttributeId)
        
        _m.logbook_write("Value Table", value=pb.render())
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def get_line_attributes(self):
        options = ["<option value='ut1'>ut1 - STANDARD - Line data 1</option>"]
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'TRANSIT_LINE':
                options.append('<option value="%s">%s - %s</option>' %(exatt.id, exatt.id, exatt.description))
        return "\n".join(options)
        
        