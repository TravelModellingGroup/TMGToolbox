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
Assign V4 Boarding Penalties

    Authors: pkucirek

    Latest revision by: mattaustin222
    
    
    Assigns line-specific boarding penalties (stored in UT3) based on specified
    groupings, for transit assignment estimation.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-14 by pkucirek
    
    1.0.0 Cleaned and published. Now accepts a list of scenarios, for easy use (Modeller only).
            Also changed the order of parameters to better match the order of groups used in
            GTAModel V4.
            
    1.0.1 Added short description

    1.1.0 Line groups are no longer hard-coded. Instead, user-inputted selector expressions are used
            and the number of line groups is open-ended.
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from re import split as _regex_split
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class AssignV4BoardingPenalties(_m.Tool()):
    
    version = '1.1.0'
    tool_run_msg = ""
    number_of_tasks = 15 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumbers = _m.Attribute(str) # parameter used by XTMF only
    Scenarios = _m.Attribute(_m.ListType) # common variable or parameter
    
    PenaltyFilterString = _m.Attribute(str)

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        lines = ["GO Train: mode=r: 1.0",
                 "GO Bus: mode=g: 1.0",
                 "Subway: mode=m: 1.0",
                 "Streetcar: mode=s: 1.0",
                 "TTC Bus: line=T_____ and mode=bp: 1.0",
                 "YRT: line=Y_____: 1.0",
                 "VIVA: line=YV____: 1.0",
                 "Brampton: line=B_____: 1.0",
                 "MiWay: line=M_____: 1.0",
                 "Durham: line=D_____: 1.0",
                 "Halton: line=H_____: 1.0",
                 "Hamilton: line=W_____: 1.0"]

        self.PenaltyFilterString = "\n".join(lines)
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Assign V4 Boarding Penalties v%s" %self.version,
                     description="Assigns line-specific boarding penalties (stored in UT3) \
                         based on specified line groupings.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenarios',
                               title='Scenarios:')

        pb.add_text_box(tool_attribute_name='PenaltyFilterString', 
                        size= 500, multi_line=True,
                        title = "Line Group Boarding Penalties",
                        note= "List of filters and boarding penalties for line groups. \
                        <br><br><b>Syntax:</b> [<em>label (line group name)</em>] : [<em>network selector expression</em>] \
                        : [<em>boarding penalty</em>] ... \
                        <br><br>Separate (label-filter-penalty) groups with a comma or new line.\
                        <br><br>Note that order matters, since penalties are applied sequentially.")

        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s);
    
        //Modeller likes to make multi-line text boxes very
        //short, so this line changes the default height
        //to something a little more visible.
        $("#PenaltyFilterString").css({height: '200px'});
        $("#PenaltyFilterString").css({width: '400px'});
        
        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        try:
            if len(self.Scenarios) == 0: raise Exception("No scenarios selected.")
            if self.PenaltyFilterString == None: raise NullPointerException("Penalties not specified")                
            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumbers,
                 PenaltyFilterString):
        
        #---1 Set up scenarios
        self.Scenarios = []
        for number in xtmf_ScenarioNumbers.split(','):
            sc = _MODELLER.emmebank.scenario(number)
            if (sc == None):
                raise Exception("Scenarios %s was not found!" %number)
            self.Scenarios.append(sc)
        
        self.PenaltyFilterString = PenaltyFilterString
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
            
            self.TRACKER.reset(len(self.Scenarios))

            filterList = self._ParseFilterString(self.PenaltyFilterString)
            
            for scenario in self.Scenarios:
                with _m.logbook_trace("Processing scenario %s" %scenario):
                    self._ProcessScenario(scenario, filterList)
                self.TRACKER.completeTask()
                
            _MODELLER.desktop.refresh_needed(True)
            
    ##########################################################################################################
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenarios" : str(self.Scenarios),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _ParseFilterString(self, filterString):
        penaltyFilterList = []
        components = _regex_split('\n|,', filterString) #Supports newline and/or commas
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 3:
                msg = "Error parsing penalty and filter string: Separate label, filter and penalty with colons label:filter:penalty"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            strippedParts = [item.strip() for item in parts]
            penaltyFilterList.append(strippedParts)

        return penaltyFilterList

    
    def _ProcessScenario(self, scenario, penaltyFilterList):
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
        self.TRACKER.startProcess(len(penaltyFilterList) + 1)
        
        with _m.logbook_trace("Resetting UT3 to 0"):
            tool(specification=self._GetClearAllSpec(), scenario=scenario)
            self.TRACKER.completeSubtask()

        for group in penaltyFilterList:
            with _m.logbook_trace("Applying " + group[0] + " BP"):
                tool(specification=self._GetGroupSpec(group), scenario=scenario)
                self.TRACKER.completeSubtask()
    
    def _GetClearAllSpec(self):
        return {
                    "result": "ut3",
                    "expression": "0",
                    "aggregation": None,
                    "selections": {
                        "transit_line": "all"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetGroupSpec(self, group):
        return {
                    "result": "ut3",
                    "expression": group[2],
                    "aggregation": None,
                    "selections": {
                        "transit_line": group[1]
                    },
                    "type": "NETWORK_CALCULATION"
                }
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def short_description(self):
        return "Assign boarding penalties to line groups."