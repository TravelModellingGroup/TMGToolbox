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
Export Countpost Results

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-16 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class ExportCountpostResults(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    CountpostAttributeId = _m.Attribute(str)
    AlternateCountpostAttributeId = _m.Attribute(str)
    
    ExportFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.CountpostAttributeId = "@stn1"
        self.AlternateCountpostAttributeId = "@stn2"
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Countpost Results v%s" %self.version,
                     description="Exports traffic assignment results on links flagged with \
                         a countpost number.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        keyval = {}
        for att in _MODELLER.scenario.extra_attributes():
            if att.type == 'LINK':
                keyval[att.id] = "%s - %s" %(att.id, att.description)
        
        pb.add_select(tool_attribute_name='CountpostAttributeId',
                      keyvalues=keyval,
                      title="Countpost Attribute",
                      note="LINK attribute containing countpost id numbers")
        
        pb.add_select(tool_attribute_name='AlternateCountpostAttributeId',
                      keyvalues=keyval,
                      title="Alternate Countpost Attribute",
                      note="Alternate countpost attribute for multiple post per link")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           file_filter="*.txt; *.csv",
                           title="Export File")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            
            $("#CountpostAttributeId")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#CountpostAttributeId");
            $("#CountpostAttributeId").trigger('change');
            
            $("#AlternateCountpostAttributeId")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#AlternateCountpostAttributeId");
            $("#AlternateCountpostAttributeId").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        if not self.Scenario.has_traffic_results:
            raise Exception("Scenario %s has no traffic assignment results" %self.Scenario.number)
        
        if self.CountpostAttributeId == None: raise NullPointerException("Countpost Attribute not specified")
        if self.AlternateCountpostAttributeId == None: raise NullPointerException("Alternate Countpost Attribute not specified")
        if self.ExportFile == None: raise NullPointerException("Export File not specified")
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
                
    def __call__(self, xtmf_ScenarioNumber, CountpostAttributeId, AlternateCountpostAttributeId,
                 ExportFile):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        if not self.Scenario.has_traffic_results:
            raise Exception("Scenario %s has no traffic assignment results" %self.Scenario.number)
        
        linkAtts = set([att.id for att in self.Scenario.extra_attributes() if att.type == 'LINK'])
        
        if not CountpostAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %CountpostAttributeId)
        if not AlternateCountpostAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %AlternateCountpostAttributeId)
        
        self.CountpostAttributeId = CountpostAttributeId
        self.AlternateCountpostAttributeId = AlternateCountpostAttributeId
        self.ExportFile = ExportFile
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            self.TRACKER.reset()
            
            network = self.Scenario.get_network()
            self.tool_run_msg = "Network loaded. Processing traffic results"
            
            with open(self.ExportFile, 'w') as writer:
                writer.write("Countpost,Link,VOLAU,VOLAD,TIMAU")
                
                posts = 0
                self.TRACKER.startProcess(network.element_totals['links'])
                for link in network.links():
                    post1 = link[self.CountpostAttributeId]
                    post2 = link[self.AlternateCountpostAttributeId]
                    
                    if post1 > 0:
                        data = [post1, link.id, link.auto_volume, link.additional_volume, link.auto_time]
                        writer.write("\n" + ",".join(data))
                        post += 1
                    if post2 > 0:
                        data = [post2, link.id, link.auto_volume, link.additional_volume, link.auto_time]
                        writer.write("\n" + ",".join(data))
                        post += 1
                    
                    self.TRACKER.completeSubtask()
            

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Countpost Attribute": self.CountpostAttributeId,
                "Alternate Countpost Attribute": self.AlternateCountpostAttributeId,
                "Export File": self.ExportFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    @_m.method(return_type=unicode)
    def _GetSelectAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            label = "{id} - {name}".format(id=att.name, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        