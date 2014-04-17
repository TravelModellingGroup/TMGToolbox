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
Analysis Tool for Extracting Cost Matrix

    Author: Peter Kucirek

'''
import inro.modeller as _m
import traceback as _traceback
_util = _m.Modeller().module('TMG2.Common.Utilities')

class ExtractCostMatrix(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    MatrixResultNumber = _m.Attribute(int)
    
    #---Special instance types, used only from Modeller
    scenario = _m.Attribute(_m.InstanceType)
    matrixResult = _m.Attribute(_m.InstanceType)
    
    def __init__(self):
        self.databank = _m.Modeller().emmebank
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Extract Cost Matrix",
                     description="Extracts average total cost (fares) matrix from a fare-based transit assignment,\
                     assuming that operator-access fares are stored on walk links in '@tfare', and that in-line or\
                     zonal fares are stored in 'us3'.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name='matrixResult',
                             title='Result Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        return pb.render()
    
    def run(self):
        '''Run is called from Modeller.'''
        self.tool_run_msg = ""
        self.isRunningFromXTMF = False
        
        # Initialize the result matrix
        #(id=None, default=0, name="", description="", matrix_type='FULL')
        self.matrixResult = _util.initializeMatrix(id= self.matrixResult, matrix_type='FULL',
                                              description="Transit avg total cost",
                                              name="trcost")
            
        # Run the tool
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete. Results stored in matrix %s." %self.matrixResult.id)
    
    def __call__(self, ScenarioNumber, MatrixResultNumber):
        
        # Get the scenario
        self.scenario = self.databank.scenario(ScenarioNumber)
        if self.scenario == None:
            raise Exception("Could not find scenario %s!" %ScenarioNumber)
        
        # Prepare the result matrix
        self.matrixResult = _util.initializeMatrix(id= MatrixResultNumber, matrix_type='FULL',
                                              description="Transit avg total cost",
                                              name="trcost")
        
        self.isRunningFromXTMF = True
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))

    def _execute(self):
        
        with _m.logbook_trace(name="Extract cost matrix v%s" %self.version,
                                     attributes={
                                                 "Scenario" : self.scenario.id,
                                                 "Result Matrix": self.matrixResult.id,
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            try:
                self.strategyAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.strategy_based_analysis')
            except Exception, e:
                self.strategyAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
            
            self.strategyAnalysisTool(self._getStrategyAnalysisSpec(), self.scenario)
            
    def _getStrategyAnalysisSpec(self):
                
        spec = {
                "trip_components": {
                                    "boarding": None,
                                    "in_vehicle": "us3", #---In-line fare
                                    "aux_transit": "@tfare", #---Boarding fare
                                    "alighting": None
                                    },
                "sub_path_combination_operator": "+",
                "sub_strategy_combination_operator": "average",
                "selected_demand_and_transit_volumes": {
                                                        "sub_strategies_to_retain": "ALL",
                                                        "selection_threshold": {
                                                                                "lower": 0,
                                                                                "upper": 999999
                                                        }
                },
                "analyzed_demand": None, #---No analyzed demand is required
                "constraint": None,
                "results": {
                    "strategy_values": self.matrixResult.id, #---RESULT MATRIX
                    "selected_demand": None,
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