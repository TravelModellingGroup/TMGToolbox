from __future__ import print_function
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
    0.0.1 Created on 2014-08-26 by pkucirek
    
'''
import traceback as _traceback

import inro.modeller as _m

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ExtractGoInVehicleTime(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    ResultMatrixId = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="[TOOL NAME] v%s" %self.version,
                     description="[DESCRIPTION]",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        '''
        def add_select_output_matrix(self, tool_attribute_name,
                                 matrix_types= ['FULL'],
                                 title= "", note= "",
                                 include_none= True,
                                 include_next= True,
                                 include_existing= False,
                                 include_new= False):
        '''
        
        pb.add_select_output_matrix(tool_attribute_name= 'ResultMatrixId',
                                    include_none= False, include_existing= True,
                                    include_new= True, 
                                    title= "Result Matrix")
        
        return pb.render()
    
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
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, ResultMatrixId):
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
        return
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            print("Extracting GO-rail in-vehicle times matrix")
            
            #def initializeMatrix(id=None, default=0, name="", description="", matrix_type='FULL'):
            _util.initializeMatrix(id= self.ResultMatrixId, description= "GO rail in-vehicle travel time")
            
            spec = self._GetSpec()
            self.TRACKER.runTool(matrixResultsTool, specification= spec, scenario= self.Scenario)

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Result Matrix": self.ResultMatrixId,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _GetSpec(self):
        return {
                "by_mode_subset": {
                    "modes": ["r"],
                    "actual_in_vehicle_times": self.ResultMatrixId
                },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS"
            }