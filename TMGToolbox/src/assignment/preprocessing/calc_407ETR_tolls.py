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
CALC 407 ETR TOLLS

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Calculates a link toll attribute for the 407ETR highway in the GTHA.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
    1.0.0 Switched to new versioning system. Also: added searchability to comboboxes
            and added tool defaults.
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
NullPointerException = _util.NullPointerException
#import utility function for python2 to python3 conversion
#initalize python3 types
import six
_util.initalizeModellerTypes(_m)
##########################################################################################################

class Calc407ETRTolls(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters necessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get initialized during construction (__init__)
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ResultAttributeId = _m.Attribute(str)
    TollZoneAttributeId = _m.Attribute(str)

    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only

    LightZoneToll = _m.Attribute(float)
    RegularZoneToll = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.LightZoneToll = 0.0
        self.RegularZoneToll = 0.0
        
        self.ResultAttributeId = "@toll"
        self.TollZoneAttributeId = "@z407"
        
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Calculate 407 ETR Tolls v%s" %self.version,
                     description="Calculates a link extra attribute for the 407ETR toll highway\
                     which uses a two-zone system.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)

        pb.add_header("ATTRIBUTES")

        keyval = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'LINK':
                continue
            descr = "{id} - LINK - {desc}".format(id=att.id, desc=att.description)
            keyval[att.id] = descr

        pb.add_select(tool_attribute_name='ResultAttributeId',
                              keyvalues=keyval,
                              title="Result Attribute",
                              note="Link attribute to save results into",
                              searchable= True)
        pb.add_select(tool_attribute_name='TollZoneAttributeId',
                              keyvalues=keyval,
                              title="Toll Zone Attribute",
                              note="Flag indicating which toll zone: \
                              <br>   1: Light toll zone\
                              <br>   2: Regular toll zone\
                              <br> All other values are assumed not to be tolled.",
                              searchable= True)

        pb.add_header("TOLL COSTS")

        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='LightZoneToll', size=12, 
                                title="Light zone toll",
                                note="In $/km, applied to toll zone 1")

            with t.table_cell():
                pb.add_text_box(tool_attribute_name='RegularZoneToll',
                                size=12,
                                title="Regular zone toll",
                                note="In $/km, applied to toll zone 2")

        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {        
        var tool = new inro.modeller.util.Proxy(%s) ;
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            var options = tool.getExtraAttributes();
            
            $("#ResultAttributeId")
                .empty()
                .append(options)
            inro.modeller.page.preload("#ResultAttributeId");
            $("#ResultAttributeId").trigger('change');

            $("#TollZoneAttributeId")
                .empty()
                .append(options)
            inro.modeller.page.preload("#TollZoneAttributeId");
            $("#TollZoneAttributeId").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if self.ResultAttributeId is None: raise NullPointerException("Result attribute not specified")
        if self.TollZoneAttributeId is None: raise NullPointerException("Toll zone attribute not specified")
        if self.LightZoneToll is None: raise NullPointerException("Light zone toll not specified")
        if self.RegularZoneToll is None: raise NullPointerException("Regular zone toll not specified")
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, xtmf_ScenarioNumber, ResultAttributeId, TollZoneAttributeId,
                 LightZoneToll, RegularZoneToll):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        linkAtts = set([att.id for att in self.Scenario.extra_attributes() if att.type == 'LINK'])

        if not ResultAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %ResultAttributeId)
        if not TollZoneAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %TollZoneAttributeId)
        
        self.ResultAttributeId = ResultAttributeId
        self.TollZoneAttributeId = TollZoneAttributeId
        self.LightZoneToll = LightZoneToll
        self.RegularZoneToll = RegularZoneToll

        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')

            with _m.logbook_trace("Calulating light zone tolls"):
                self.TRACKER.runTool(tool, scenario=self.Scenario,
                                 specification=self._GetZoneSpec(1, self.LightZoneToll))

            with _m.logbook_trace("Calculating regular zone tolls"):
                self.TRACKER.runTool(tool, scenario=self.Scenario,
                                 specification=self._GetZoneSpec(2, self.RegularZoneToll))

    ##########################################################################################################   
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _GetZoneSpec(self, zone, toll):
        return {
                "result": self.ResultAttributeId,
                "expression": "%s * length" %toll,
                "aggregation": None,
                "selections": {
                                "link": "%s=%s" %(self.TollZoneAttributeId, zone)
                            },
                "type": "NETWORK_CALCULATION"
                }
    @_m.method(return_type=six.text_type)
    def getExtraAttributes(self):
        keyvals = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'LINK':
                continue
            descr = "{id} - LINK - {desc}".format(id=att.id, desc=att.description)
            keyvals[att.id] = descr
        
        options = []
        for tuple in six.iteritems(keyvals):
            html = '<option value="%s">%s</option>' %tuple
            options.append(html)
            
        return "\n".join(options)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg