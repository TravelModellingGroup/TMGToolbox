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
Import from Database

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    This tool provides XTMF-callable access to the Inro tool
    "Import from database". It imports all functions, but
    does not import matrices or partitions.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-07-13 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
import inro.emme.database.emmebank as _emmebank
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
InroImport = _MODELLER.tool('inro.emme.data.database.import_from_database')
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

class ImportFromDatabase(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here

    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumbers = _m.Attribute(str) #should be a comma-separated list of numbers

    Increment = _m.Attribute(str) 

    DatabasePath = _m.Attribute(str)

    OverwriteFlag = _m.Attribute(bool)

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker   
        self.Scenarios = []    
        self.FunctionList = []
        self.OverwriteFlag = False
    
    def page(self):
                
        pb = _m.ToolPageBuilder(self, title="Import from Database (XTMF Internal)",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
    
    def __call__(self, xtmf_ScenarioNumbers, Increment, DatabasePath, OverwriteFlag):

        if EMME_VERSION < (4,0,8):
            raise Exception("Tool not compatible. Please upgrade to version 4.0.8+")
        
        #---1 Parse scenario list
        self.Scenarios = xtmf_ScenarioNumbers.split(',')

        #---2 Set up other parameters
        self.Increment = Increment
        self.DatabasePath = DatabasePath
        self.OverwriteFlag = OverwriteFlag

        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):

            if self.OverwriteFlag:
                self._DeleteScenarios()
            
            InroImport(src_database=self.DatabasePath, 
                       src_scenario_ids=self.Scenarios,
                       increment_scenario_ids=self.Increment,
                       src_function_ids=self._RetrieveFunctionIds(),
                       increment_function_ids=0)

            self.TRACKER.completeTask()


    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _DeleteScenarios(self):
        for sc in self.Scenarios:
            toDelete = sc + self.Increment
            if _m.Modeller().emmebank.scenario(toDelete): 
                _m.Modeller().emmebank.delete_scenario(toDelete)
                _m.logbook_write("Scenario %s deleted" %toDelete)
            
    def _RetrieveFunctionIds(self):
        functionList = []
        with _emmebank.Emmebank(self.DatabasePath) as emmebank:
            for funcs in emmebank.functions():
                functionList.append(funcs.id)

        return functionList         

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
            