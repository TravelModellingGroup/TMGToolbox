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
    0.0.1 Created on 2014-10-22 by pkucirek
    
'''

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from json import loads as _parsedict

import inro.modeller as _m
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExtractRawIvttMatrix(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    CONGESTED_ASSIGNMENT_TYPES = set(['CONGESTED_TRANSIT_ASSIGNMENT',
                                      'CAPACITATED_TRANSIT_ASSIGNMENT'])
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
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
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Raw In-Vehicle Times Matrix v%s" %self.version,
                     description="Extracts real (raw) transit in-vehicle times matrix from \
                         any type of Extended Transit Assignment. In particular, this tool \
                         auto-detects if a congested or capacitated assignment has been run \
                         and compensates for the additional crowding term.\
                         <br><br><b>Temporary storage requirements:</b> One full matrix.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_output_matrix(tool_attribute_name= 'ResultMatrixId',
                                    title= "Result Matrix",
                                    include_none= False,
                                    include_existing= True,
                                    include_new= True)
        
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
    
    def short_description(self):
        return "<em>Extracts true transit in-vehicle time matrix.</em>"
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, ResultMatrixId):

        try:
            #---1 Set up scenario
            self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
            if (self.Scenario == None):
                raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
            
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
        return
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if not self.Scenario.has_transit_results:
                raise Exception("Scenario %s has no transit results." %self.Scenario)
            
            if self.Scenario.transit_assignment_type =='STANDARD_TRANSIT_ASSIGNMENT':
                raise Exception("Cannot analyze standard transit assignment. Extended transit assignment only.")
            
            _util.initializeMatrix(id= self.ResultMatrixId, \
                                   description= "Real transit IVTT from scenario %s" %self.Scenario,
                                   preserve_description= True)
            
            print "Extracting real transit in-vehicle times."
            
            assignmentType = self._GetAssignmentType()
            
            self._ExtractAssignmentMatrix()
            
            if assignmentType in self.CONGESTED_ASSIGNMENT_TYPES:
                with _util.tempMatrixMANAGER(description= "Congestion matrix") as tempMatrix:
                    self._ExtractCongestionMatrix(tempMatrix.id)
                    self._CalculateTrueMatrix(tempMatrix.id)
            else:
                self.TRACKER.completeTask()
                self.TRACKER.completeTask()

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario),
                "Result MAtrix": self.ResultMatrixId,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _GetAssignmentType(self):
        if not self.Scenario.has_transit_results: return None
        
        strategies = self.Scenario.transit_strategies
        data = strategies.data
        return data['type']
    
    def _ExtractAssignmentMatrix(self):
        spec = {
                "by_mode_subset": {
                    "modes": ['*'],
                    "actual_in_vehicle_times": self.ResultMatrixId
                },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS"
            }
        
        matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')
        self.TRACKER.runTool(matrixResultsTool, spec, scenario= self.Scenario)
        
    def _ExtractCongestionMatrix(self, tempMatrixId):
        spec = {
            "trip_components": {
                "boarding": None,
                "in_vehicle": "@ccost",
                "aux_transit": None,
                "alighting": None
            },
            "sub_path_combination_operator": "+",
            "sub_strategy_combination_operator": "average",
            "selected_demand_and_transit_volumes": {
                "sub_strategies_to_retain": "ALL",
                "selection_threshold": {
                    "lower": -999999,
                    "upper": 999999
                }
            },
            "analyzed_demand": None,
            "constraint": None,
            "results": {
                "strategy_values": tempMatrixId,
                "selected_demand": None,
                "transit_volumes": None,
                "aux_transit_volumes": None,
                "total_boardings": None,
                "total_alightings": None
            },
            "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
        }
        stratTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
        self.TRACKER.runTool(stratTool, spec, scenario= self.Scenario)
        
    def _CalculateTrueMatrix(self, tempMatrixId):
        
        expression = "{congested_time} - {congestion}".format(congested_time= self.ResultMatrixId,
                                                              congestion= tempMatrixId)
        spec = {
                    "expression": expression,
                    "result": self.ResultMatrixId,
                    "constraint": {
                        "by_value": None,
                        "by_zone": None
                    },
                    "aggregation": {
                        "origins": None,
                        "destinations": None
                    },
                    "type": "MATRIX_CALCULATION"
                }
        matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
        self.TRACKER.runTool(matrixCalcTool, spec, scenario= self.Scenario)
        