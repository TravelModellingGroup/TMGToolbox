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
    0.0.1 Created on 2014-06-16 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

EMME_VERSION = _util.getEmmeVersion(float)
changeModeTool = _MODELLER.tool('inro.emme.data.network.mode.change_mode')
emmebank = _MODELLER.emmebank

##########################################################################################################

class SetWalkSpeed(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenarios = _m.Attribute(list) # common variable or parameter
    
    WalkSpeed = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenarios = [_MODELLER.scenario] #Default is primary scenario
        self.WalkSpeed = 4.0
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Set Walk Speed v%s" %self.version,
                     description="Sets the speed factor of all auxiliary transit modes to the \
                        specified value",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenarios',
                               title='Scenarios',
                               allow_none=False)
        
        units = emmebank.unit_of_length + "/hr"
        
        pb.add_text_box(tool_attribute_name= 'WalkSpeed',
                        title= "Walking speed in %s" %units)
        
        return pb.render()
    
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
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber):
        
        #---1 Set up scenario
        sc = emmebank.scenario(xtmf_ScenarioNumber)
        self.Scenarios = [sc]
        if (sc == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            self.TRACKER.startProcess(len(self.Scenarios))
            if EMME_VERSION < 4.1:
                for scenario in self.Scenarios:
                    self._ProcessScenario4p0(scenario)
                    self.TRACKER.completeSubtask()
            else:
                for scenario in self.Scenarios:
                    self._ProcessScenario4p1(scenario)
                    self.TRACKER.completeSubtask()

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenarios" : str(self.Scenarios),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts

    def _ProcessScenario4p0(self, scenario):
        for mode in scenario.modes():
            if mode.type != 'AUX_TRANSIT': continue
            changeModeTool(mode,
                           mode_speed= self.WalkSpeed,
                           scenario= scenario)
    
    def _ProcessScenario4p1(self, scenario):
        partialNetwork = scenario.get_partial_network(['MODE'], True)
        
        for mode in partialNetwork.modes():
            if mode.type != 'AUX_TRANSIT': continue
            mode.speed = self.WalkSpeed
        
        baton = partialNetwork.get_attribute_values('MODE', ['speed'])
        scenario.set_attribute_values('MODE', ['speed'], baton)
        