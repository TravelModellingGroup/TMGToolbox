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

'''
Analysis Tool for Extracting Select Line Matrix

    Author: Peter Kucirek

'''

#---VERSION HISTORY
'''
    0.1.0 Created
    
    0.2.0 Fixed up with new MatrixResultId parameter, and new utilities
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExtractSelectLineMatrix(_m.Tool()):
    
    version = '0.2.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    xtmf_MatrixResultNumber = _m.Attribute(int)
    MatrixResultId = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Select Line Matrix",
                     description="Extracts a select-line matrix for transit lines flagged\
                         by <b>@lflag</b>.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_new_matrix(tool_attribute_name='MatrixResultId',
                                 overwrite_existing=True,
                                 title="Result Matrix")
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete. Results stored in matrix %s." %self.MatrixResultId)        
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_MatrixResultNumber):
        
        self.Scenario = _m.Modeller().emmebank.Scenario(xtmf_ScenarioNumber)
        if self.Scenario == None:
            raise Exception("Could not find Scenario %s!" %xtmf_ScenarioNumber)
    
        self.MatrixResultId = "mf%s" %xtmf_MatrixResultNumber
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
        
    def _execute(self):
        with _m.logbook_trace(name="Extract select line matrix v%s" %self.version,
                                     attributes={
                                                 "Scenario" : self.Scenario.id,
                                                 "Result Matrix": self.MatrixResultId,
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            resultMatrix = _util.initializeMatrix(self.MatrixResultId, name='slctOD', 
                                             description="Transit select line analysis result")
            
            try:
                strategyAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.strategy_based_analysis')
            except Exception, e:
                strategyAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
            
            self.TRACKER.runTool(strategyAnalysisTool,
                                 self._getAnalysisSpec(), self.Scenario)    
    
    def _getAnalysisSpec(self):
        
        spec = {
                "trip_components": {
                                    "boarding": "@lflag", #---Boarding attribute
                                    "in_vehicle": None,
                                    "aux_transit": None,
                                    "alighting": None
                                    },
                "sub_path_combination_operator": ".max.", #---Path operator
                "sub_strategy_combination_operator": ".max.", #---Strategy operator
                "selected_demand_and_transit_volumes": {
                                                        "sub_strategies_to_retain": "FROM_COMBINATION_OPERATOR",
                                                        "selection_threshold": {
                                                                                "lower": 1,
                                                                                "upper": 1
                                                                                }
                                                        },
                "analyzed_demand": None, #---Analyzed demand (this may need to be changed)
                "constraint": None,
                "results": {
                    "strategy_values": self.MatrixResultId, #---Strategy results
                    "selected_demand": None, #---Demand results
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        
        return spec
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()