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
[TITLE]

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-05-05 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ExportNetworkBatchFile(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    xtmf_FileName = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Export Network Batch File",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_FileName):
        
        #---1 Set up scenario
        scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            self._Execute(scenario, xtmf_FileName)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self, scenario, filename):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes={"Scenario": str(scenario),
                                                 "Version": self.version,
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            tool = _MODELLER.tool('inro.emme.data.network.base.export_base_network')
            self.TRACKER.runTool(tool, export_file= filename, scenario= scenario)

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        