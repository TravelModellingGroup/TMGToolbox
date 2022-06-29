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

'''
Analysis Tool for Extracting Travel Time Matrices, constrained by transit feasibility.

    Author: Peter Kucirek

'''
#---VERSION HISTORY
'''
    0.1.1 [Undocumented History]
    
    0.1.2 Modified to use new Modeller page objects
    
    0.2.0 Modified to optionally only constrain the walk matrix

    0.2.1 Updated to allow for multi-threaded matrix calcs in 4.2.1+
    
'''
import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from datetime import datetime as _dt
from multiprocessing import cpu_count
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

EMME_VERSION = _util.getEmmeVersion(tuple) 
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

class ExtractConstrainedLOSMatrices(_m.Tool()):
    
    version = '0.2.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    xtmf_ModeString = _m.Attribute(str)
    modeller_ModeList = _m.Attribute(_m.ListType) # parameter used by Modeller only
    
    InVehicleTimeMatrixId = _m.Attribute(str)
    WalkTimeMatrixId = _m.Attribute(str)
    WaitTimeMatrixId = _m.Attribute(str)
    BoardingTimeMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    
    WalkTimeCutoff = _m.Attribute(float)
    WaitTimeCutoff = _m.Attribute(float)
    TotalTimeCutoff = _m.Attribute(float)
    FarePerception = _m.Attribute(float)
    
    RunTitle = _m.Attribute(str)

    NumberOfProcessors = _m.Attribute(int)
    
    #========================================
        
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.FarePerception = 0
        self.WalkTimeCutoff = 40
        self.WaitTimeCutoff = 40
        self.TotalTimeCutoff = 150
        self.RunTitle = ""
        self.NumberOfProcessors = cpu_count()
        self.modeller_ModeList = []
            
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Constrained LOS Matrices",
                     description="Extracts average in-vehicle, walking, waiting, boarding time, \
                     and cost matrices from a fare-based assignment. Matrices will be multiplied by a \
                     feasibility matrices (where 0 = infeasible and 1 = feasible).",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='RunTitle',
                        size=25, title="Run Title",
                        note="Max. 25 chars")
        
        scId = _MODELLER.scenario.id
        pb.add_select_mode(tool_attribute_name='modeller_ModeList',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Modes',
                           note="<font color=blue><b>Note:</b></font> Only modes from the current \
                           scenario (%s) will be visible." %scId)
        
        pb.add_header("FEASIBILITY PARAMETERS")
        #----------------------------------
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='WalkTimeCutoff',
                                size=8,
                                title='Walk Time Cutoff:')
            with t.table_cell():    
                pb.add_text_box(tool_attribute_name='WaitTimeCutoff',
                                size=8,
                                title='Wait Time Cutoff:')
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='TotalTimeCutoff',
                                size=8,
                                title='Total Time Cutoff:')
                
        pb.add_text_box(tool_attribute_name='FarePerception',
                        size=6,
                        title='Fare perception:',
                        note="Enter '0' to disable fare-based impedances.")
        
        pb.add_header("RESULT MATRICES")
        #----------------------------------
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='InVehicleTimeMatrixId',
                                         title="IVTT Matrix",
                                         overwrite_existing=True,
                                         allow_none=True)
                
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='WalkTimeMatrixId',
                                         title="Walk Matrix",
                                         overwrite_existing=True,
                                         allow_none=True)
                
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='WaitTimeMatrixId',
                                         title="Wait Matrix",
                                         overwrite_existing=True,
                                         allow_none=True)
            
            t.new_row()
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='BoardingTimeMatrixId',
                                         title="Boarding Matrix",
                                         overwrite_existing=True,
                                         allow_none=True)
                
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='CostMatrixId',
                                         title="Cost Matrix",
                                         overwrite_existing=True,
                                         allow_none=True)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        
        # Convert the list of mode objects to a list of mode characters
        modes = [m.id for m in self.modeller_ModeList]
        
        # Run the tool
        try:
            self._execute(modes)
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete")
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_ModeString,
                 WalkTimeCutoff, WaitTimeCutoff, TotalTimeCutoff,
                 InVehicleTimeMatrixId, CostMatrixId,
                 WalkTimeMatrixId, WaitTimeMatrixId, BoardingTimeMatrixId,
                 FarePerception, RunTitle, modeller_ModeList):
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.modeller_ModeList = modeller_ModeList
        
        #---2 Pass in remaining args
        self.RunTitle = RunTitle[:25]
        self.WalkTimeCutoff = WalkTimeCutoff
        self.WaitTimeCutoff = WaitTimeCutoff
        self.TotalTimeCutoff = TotalTimeCutoff
        self.FarePerception = FarePerception
        
        self.BoardingTimeMatrixId = BoardingTimeMatrixId
        self.CostMatrixId = CostMatrixId
        self.InVehicleTimeMatrixId = InVehicleTimeMatrixId
        self.WaitTimeMatrixId = WaitTimeMatrixId
        self.WalkTimeMatrixId = WalkTimeMatrixId
        
        #For this tool only, split the modes
        modes = [c for c in xtmf_ModeString]
        
        try:
            self._execute(modes)
        except Exception as e:
            raise Exception(_traceback.format_exc())
    
    def _execute(self, modes):
        with _m.logbook_trace(name="%s (%s v%s)" %(self.RunTitle, self.__class__.__name__, self.version),
                                     attributes=self._GetAtts(modes)):
            
            self._assignmentCheck()
            
            #Create three temporary matrix managers
            with _util.tempMatrixMANAGER(description="Feasibility matrix") as feasibilityMatrix, _util.tempMatrixMANAGER(description="Line fares matrix") as lineFaresMatrix, _util.tempMatrixMANAGER(description="Access fares matrix") as accessFaresMatrix:
                
                self.TRACKER.completeTask()
                
                #--------------------------------------------------
                if self.BoardingTimeMatrixId != 'null':
                    _util.initializeMatrix(self.BoardingTimeMatrixId, description="TRANSIT BOARD: %s" %self.RunTitle)
                if self.InVehicleTimeMatrixId != 'null':
                    _util.initializeMatrix(self.InVehicleTimeMatrixId, description="TRANSIT IVTT: %s" %self.RunTitle)
                if self.WaitTimeMatrixId != 'null':
                    _util.initializeMatrix(self.WaitTimeMatrixId, description="TRANSIT WAIT: %s" %self.RunTitle)                    
                if self.WalkTimeMatrixId != 'null':
                    _util.initializeMatrix(self.WalkTimeMatrixId, description="TRANSIT WALK: %s" %self.RunTitle)
                
                calcFares = False
                if self.CostMatrixId != 'null':
                    _util.initializeMatrix(self.CostMatrixId, description="TRANSIT COST %s" %self.RunTitle)
                    if self.FarePerception != 0:
                        calcFares = True    
                self.TRACKER.completeTask()
                #--------------------------------------------------
                
                # Setup tools
                try:
                    matrixAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
                    matrixCalcTool = _m.Modeller().tool('inro.emme.matrix_calculation.matrix_calculator')
                    strategyAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
                except Exception as e:
                    matrixAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
                    matrixCalcTool = _m.Modeller().tool('inro.emme.standard.matrix_calculation.matrix_calculator')
                    strategyAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.strategy_based_analysis')
                
                with _m.logbook_trace("Extracting travel time matrices."):
                    self.TRACKER.runTool(matrixAnalysisTool, self._getTimesAnalysisSpec(modes), self.Scenario)
                
                if calcFares:
                    with _m.logbook_trace("Extracting cost matrices."):
                        self.TRACKER.runTool(strategyAnalysisTool, self._getInLineFaresAnalysisSpec(lineFaresMatrix.id), scenario=self.Scenario)
                        _m.logbook_write("In-line fares matrix extracted.")
                        
                        self.TRACKER.runTool(strategyAnalysisTool, self._getBoardingFaresAnalysisSpec(accessFaresMatrix.id), scenario=self.Scenario)
                        _m.logbook_write("Access fares matrix extracted.")
                        
                        if EMME_VERSION >= (4,2,1):
                            self.TRACKER.runTool(matrixCalcTool, self._getCostSumSpec(lineFaresMatrix.id, accessFaresMatrix.id), scenario=self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        else:
                            self.TRACKER.runTool(matrixCalcTool, self._getCostSumSpec(lineFaresMatrix.id, accessFaresMatrix.id), scenario=self.Scenario)
                        _m.logbook_write("Cost components added.")
                
                    with _m.logbook_trace("Subtracting fares from impedances to get times."):
                        fareFactor = self._calculateFareFactor()
                        if EMME_VERSION >= (4,2,1):
                            self.TRACKER.runTool(matrixCalcTool, self._getFixIVTTSpec(lineFaresMatrix.id, fareFactor), scenario=self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        else:
                            self.TRACKER.runTool(matrixCalcTool, self._getFixIVTTSpec(lineFaresMatrix.id, fareFactor), scenario=self.Scenario)
                        _m.logbook_write("IVTT matrix fixed.")
                        
                        if EMME_VERSION >= (4,2,1):
                            self.TRACKER.runTool(matrixCalcTool, self._getFixWalkSpec(accessFaresMatrix.id, fareFactor), scenario=self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        else:
                            self.TRACKER.runTool(matrixCalcTool, self._getFixWalkSpec(accessFaresMatrix.id, fareFactor), scenario=self.Scenario)
                        _m.logbook_write("Walk matrix fixed.")
                else:
                    for i in range(5):
                        self.TRACKER.completeTask() #Skip these 5 tasks
                
                with _m.logbook_trace("Extracting temporary feasibility matrix."):
                    if EMME_VERSION >= (4,2,1):
                        self.TRACKER.runTool(matrixCalcTool, self._getFeasibilityMatrixSpec(feasibilityMatrix.id), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                    else:
                        self.TRACKER.runTool(matrixCalcTool, self._getFeasibilityMatrixSpec(feasibilityMatrix.id), self.Scenario)
                
                with _m.logbook_trace("Applying feasibility constraint matrix."):
                    matrixIdsToConstrain = {'boarding times': self.BoardingTimeMatrixId,
                                            'IVTT': self.InVehicleTimeMatrixId,
                                            'wait times': self.WaitTimeMatrixId,
                                            'walk times': self.WalkTimeMatrixId}
                    if calcFares:
                        matrixIdsToConstrain['Cost'] = self.CostMatrixId
                    
                    self.TRACKER.startProcess(len(matrixIdsToConstrain))
                    for (name, id) in six.iteritems(matrixIdsToConstrain):
                        if id == 'null': #Cannot return None from combobox, so need to check for string nullity
                            self.TRACKER.completeSubtask()
                        if EMME_VERSION >= (4,2,1):
                            matrixCalcTool(self._getMatrixMultiplicationSpec(feasibilityMatrix.id, id), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        else:
                            matrixCalcTool(self._getMatrixMultiplicationSpec(feasibilityMatrix.id, id), self.Scenario)
                        _m.logbook_write("Constrained %s matrix." %name)
                        self.TRACKER.completeSubtask()
    
    #----SUB FUNCTIONS--------------------------------------------------------------------------------- 
    
    def _GetAtts(self, modes):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Modes": str(modes),
                 "Walk Time Cutoff" : self.WalkTimeCutoff,
                 "Wait Time Cutoff": self.WaitTimeCutoff,
                 "Total Time Cutoff": self.TotalTimeCutoff,
                 "IVTT Matrix": self.InVehicleTimeMatrixId,
                 "Walk Time Matrix": self.WalkTimeMatrixId,
                 "Wait Time Matrix": self.WaitTimeMatrixId,
                 "Boarding Time Matrix": self.WaitTimeMatrixId,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    #----
    
    def _assignmentCheck(self):
        if self.Scenario.transit_assignment_type != 'EXTENDED_TRANSIT_ASSIGNMENT':
            raise Exception("No extended transit assignment results were found for scenario %s!" %self.Scenario.id)
    
    def _calculateFareFactor(self):
        if self.FarePerception != 0:
            return 60.0 / self.FarePerception
    
    def _getTimesAnalysisSpec(self, modes):
        
        spec = {
                "by_mode_subset": {
                                   "modes": modes,
                                   "actual_total_boarding_times": self.BoardingTimeMatrixId,
                                   "actual_in_vehicle_times": self.InVehicleTimeMatrixId,
                                   "actual_aux_transit_times": self.WalkTimeMatrixId
                                   },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": self.WaitTimeMatrixId
                }
        
        return spec
    
    def _getInLineFaresAnalysisSpec(self, lineFaresMatrixId):
        spec = {
                "trip_components": {
                                    "boarding": None,
                                    "in_vehicle": "us3", #---In-line fare
                                    "aux_transit": None, #---Boarding fare
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
                "analyzed_demand": self.InVehicleTimeMatrixId, #---No analyzed demand is required
                "constraint": None,
                "results": {
                    "strategy_values": lineFaresMatrixId, #---RESULT MATRIX
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return spec
    
    def _getBoardingFaresAnalysisSpec(self, accessFaresMatrixId):
        spec = {
                "trip_components": {
                                    "boarding": None,
                                    "in_vehicle": None, #---In-line fare
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
                "analyzed_demand": self.InVehicleTimeMatrixId, #---No analyzed demand is required
                "constraint": None,
                "results": {
                    "strategy_values": accessFaresMatrixId, #---RESULT MATRIX
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return spec
    
    def _getFixIVTTSpec(self, lineFaresMatrixId, fareFactor):
        spec = {
                "expression": "({0} - {1} * {2}).max.0".format(self.InVehicleTimeMatrixId,
                                                               lineFaresMatrixId,
                                                               fareFactor),
                "result": self.InVehicleTimeMatrixId,
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
        return spec
    
    def _getFixWalkSpec(self, accessFaresMatrixId, fareFactor):
        spec = {
                "expression": "({0} - {1} * {2}).max.0".format(self.WalkTimeMatrixId,
                                                               accessFaresMatrixId,
                                                               fareFactor),
                "result": self.WalkTimeMatrixId,
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
        return spec
    
    def _getFeasibilityMatrixSpec(self, feasibilityMatrixId):
        #          (walk < cutoff) AND (wait < cutoff) AND ((walk + wait + ivtt) < cutoff)   
        expression = "({0} < {3}) && ({1} < {4}) && (({0} + {1} + {2}) < {5})".format(self.WalkTimeMatrixId,
                                                                                    self.WalkTimeMatrixId,
                                                                                    self.InVehicleTimeMatrixId,
                                                                                    str(self.WalkTimeCutoff),
                                                                                    str(self.WaitTimeCutoff),
                                                                                    str(self.TotalTimeCutoff))
        
        spec = {
                "expression": expression,
                "result": feasibilityMatrixId,
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
        return spec
    
    def _getMatrixMultiplicationSpec(self, feasibilityMatrixId, matrixId):
        
        spec = {
                "expression": "0",
                "result": matrixId,
                "constraint": {
                                "by_value": {
                                            "interval_min": 0,
                                            "interval_max": 0,
                                            "condition": "INCLUDE",
                                            "od_values": feasibilityMatrixId
                                            },
                                "by_zone": None
                                },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
        return spec
    
    def _getCostSumSpec(self, lineFaresMatrixId, accessFaresMatrixId):
        spec = {
                "expression": "{0} + {1}".format(lineFaresMatrixId, lineFaresMatrixId),
                "result": self.CostMatrixId,
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
        return spec
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
    
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
   