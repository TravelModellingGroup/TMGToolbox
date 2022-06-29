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
EXTRACT SELECT LINE COMPONENT MATRICES

    Author: Peter Kucirek
    
    Analysis Tool for extracting travel time component matrices and
    transit fare matrix for flagged lines.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created.
    
    0.2.0 Updated to use context managers
    
    0.2.1 Fixed bug where component matrices were overwriting the select line matrix
    
    0.3.0 Updated to recover fares from a LegacyFBTA
    
    0.3.1 Fixed a bug in which unselected optional matrices caused a null reference exception.

    0.3.2 Updated to allow multi-threaded matrix calcs in 4.2.1+
'''

import inro.modeller as _m
import traceback as _traceback
from multiprocessing import cpu_count
_util = _m.Modeller().module('tmg.common.utilities')
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')

EMME_VERSION = _util.getEmmeVersion(tuple) 

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ExtractSelectLineTimesAndCosts(_m.Tool()):
    
    version = '0.3.2'
    tool_run_msg = ""
    
    # Variables marked with a '#' are used in the main block, and are assigned by both run and call
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    InVehicleTimeMatrixNumber = _m.Attribute(int)
    WalkTimeMatrixNumber = _m.Attribute(int)
    WaitTimeMatrixNumber = _m.Attribute(int)
    BoardingTimeMatrixNumber = _m.Attribute(int)
    CostMatrixNumber = _m.Attribute(int)
    WalkTimeCutoff = _m.Attribute(float)
    WaitTimeCutoff = _m.Attribute(float)
    TotalTimeCutoff = _m.Attribute(float)
    FarePerception = _m.Attribute(float)

    NumberOfProcessors = _m.Attribute(int)
    #---Special Modeller types
    scenario = _m.Attribute(_m.InstanceType) #
    modes = _m.Attribute(_m.ListType) 
    ivttMatrix = _m.Attribute(_m.InstanceType) #
    walkMatrix = _m.Attribute(_m.InstanceType) #
    waitMatrix = _m.Attribute(_m.InstanceType) #
    boardingMatrix = _m.Attribute(_m.InstanceType) #
    costMatrix = _m.Attribute(_m.InstanceType) #    
    
    #---Private variables
    _modeList = [] #
    
    def __init__(self):
        self.databank = _m.Modeller().emmebank
                
        self.NumberOfProcessors = cpu_count()

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Select Line Matrices",
                     description="Extracts average in-vehicle, walking, waiting, and boarding time\
                     matrices from a strategy-based assignment, for transit lines flagged by attribute\
                     <b>@lflag</b>. <br><br>To calculate costs, the network must have transfer fares\
                     stored in <b>@tfare</b> and in-line fares stored in <b>us3</b>.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("ANALYSIS OPTIONS")
        
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_mode(tool_attribute_name='modes',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Modes:')
        
        pb.add_text_box(tool_attribute_name='FarePerception',
                        size=6,
                        title='Fare perception:',
                        note="The fare perception used in the assignment. Enter '0' to disable recovery of \
                            walk times and IVTTs.")
        
        pb.add_header("FEASIBILITY PARAMETERS")
        #----------------------------------
        pb.add_text_box(tool_attribute_name='WalkTimeCutoff',
                        size=4,
                        title='Walk Time Cutoff:')
        
        pb.add_text_box(tool_attribute_name='WaitTimeCutoff',
                        size=4,
                        title='Wait Time Cutoff:')
        
        pb.add_text_box(tool_attribute_name='TotalTimeCutoff',
                        size=4,
                        title='Total Time Cutoff:')
        
        pb.add_header("RESULTS")
        
        pb.add_select_matrix(tool_attribute_name='ivttMatrix',
                             filter=['FULL'],
                             title="Select IVTT matrix",
                             allow_none=False)
            
        pb.add_select_matrix(tool_attribute_name='walkMatrix',
                             filter=['FULL'],
                             title="Select walk matrix",
                             allow_none=False)

        pb.add_select_matrix(tool_attribute_name='waitMatrix',
                             filter=['FULL'],
                             title="Select wait matrix",
                             allow_none=False)
            
        pb.add_select_matrix(tool_attribute_name='boardingMatrix',
                             filter=['FULL'],
                             title="Select boarding matrix",
                             allow_none=False)

        pb.add_select_matrix(tool_attribute_name='costMatrix',
                             filter=['FULL'],
                             title="Select cost matrix",
                             allow_none=False)
        
        return pb.render()
        
    ##########################################################################################################        
    
    def run(self):
        '''Run is called from Modeller.'''
        self.tool_run_msg = ""
        self.isRunningFromXTMF = False
        
        # Convert the list of mode objects to a list of mode characters
        for m in self.modes:
            self._modeList.append(m.id)
        
        # Initialize blank matrices if needed.
        if self.ivttMatrix is None:
            self._initIVTT(self.databank.available_matrix_identifier('FULL'))
        if self.walkMatrix is None:
            self._initWalk(self.databank.available_matrix_identifier('FULL'))
        if self.waitMatrix is None:
            self._initWait(self.databank.available_matrix_identifier('FULL'))
        if self.boardingMatrix is None:
            self._initBoard(self.databank.available_matrix_identifier('FULL'))
        if self.costMatrix is None:
            self._initCost(self.databank.available_matrix_identifier('FULL'))
        
        # Run the tool
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete.")
    
    def __call__(self, ScenarioNumber, ModeString, InVehicleTimeMatrixNumber, WalkTimeMatrixNumber, 
                 WaitTimeMatrixNumber, BoardingTimeMatrixNumber, CostMatrixNumber, WalkTimeCutoff,
                 WaitTimeCutoff, TotalTimeCutoff, FarePerception):
        
        # Get the scenario object
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.scenario is None:
            raise Exception("Could not find scenario %s!" %ScenarioNumber)
        
        # Convert the mode string to a list of characters
        for i in range(0, len(ModeString)):
            self._modeList.append(ModeString[i])
        
        # Initialize matrices
        self._initIVTT("mf%s" %InVehicleTimeMatrixNumber)
        self._initWalk("mf%s" %WalkTimeMatrixNumber)
        self._initWait("mf%s" %WaitTimeMatrixNumber)
        self._initBoard("mf%s" %BoardingTimeMatrixNumber)
        self._initCost("mf%s" %CostMatrixNumber)
        
        
        self.WaitTimeCutoff = WaitTimeCutoff
        self.WalkTimeCutoff = WalkTimeCutoff
        self.TotalTimeCutoff = TotalTimeCutoff
        self.FarePerception = FarePerception
        self.isRunningFromXTMF = True
        
        #Execute the tool
        try:
            self._execute()
        except Exception as e:
            raise Exception(_traceback.format_exc())
    
    ##########################################################################################################
    
    def _execute(self):
        with _m.logbook_trace(name="Extract Select Line Costs and Times v%s" %self.version,
                                     attributes={
                                                 "Scenario" : self.scenario.id,
                                                 "Modes": str(self._modeList),
                                                 "IVTT Matrix": str(self.ivttMatrix),
                                                 "Walk Time Matrix": str(self.walkMatrix),
                                                 "Wait Time Matrix": str(self.waitMatrix),
                                                 "Boarding Time Matrix": str(self.boardingMatrix),
                                                 "Cost Matrix": str(self.costMatrix),
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            self._assignmentCheck()
            
            strategyAnalysisTool = None
            matrixAnalysisTool = None
            matrixCalcTool = None
            try:
                strategyAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
                matrixAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
                matrixCalcTool = _m.Modeller().tool('inro.emme.matrix_calculation.matrix_calculator')
            except Exception as e:
                strategyAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.strategy_based_analysis')
                matrixAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
                matrixCalcTool = _m.Modeller().tool('inro.emme.standard.matrix_calculation.matrix_calculator')
            
            #Create four temporary matrix managers
            with _util.tempMatrixMANAGER(description="Select-line matrix") as self._selectLineMatrix,\
                        _util.tempMatrixMANAGER(description="Line fares matrix") as self.lineFaresMatrix,\
                        _util.tempMatrixMANAGER(description="Access fares matrix") as self.accessFaresMatrix,\
                        _util.tempMatrixMANAGER(description="Feasibility matrix") as self.feasibilityMatrix:
                
                with _m.logbook_trace("Extracting select-line matrix:"):
                    strategyAnalysisTool(self._getSelectLineAnalysisSpec(), self.scenario)
                    if EMME_VERSION >= (4,2,1):
                        matrixCalcTool(self._getMatrixCleanupSpec(), self.scenario,
                                             num_processors=self.NumberOfProcessors)
                    else:
                        matrixCalcTool(self._getMatrixCleanupSpec(), self.scenario)
                
                with _m.logbook_trace("Extracting travel component matrices:"):
                    matrixAnalysisTool(self._getTimeComponentAnalysisSpec(), self.scenario)
                    strategyAnalysisTool(self._getCostAnalysisSpec(), self.scenario)
                
                with _m.logbook_trace("Extracting temporary feasibility matrix:"):
                    if EMME_VERSION >= (4,2,1):
                        matrixCalcTool(self._getFeasibilityMatrixSpec(), self.scenario,
                                             num_processors=self.NumberOfProcessors)
                    else:
                        matrixCalcTool(self._getFeasibilityMatrixSpec(), self.scenario)

                #---Recover walk and in-vehicle times if a fare-based assignment has been run.
                if self.FarePerception != 0:
                    with _m.logbook_trace("Extracting line-fares matrix:"):
                        strategyAnalysisTool(self._getInLineFaresAnalysisSpec(), scenario=self.scenario)
                    
                    with _m.logbook_trace("Extracting access-fare matrix:"):
                        strategyAnalysisTool(self._getBoardingFaresAnalysisSpec(), scenario=self.scenario)
                        
                    with _m.logbook_trace("Recovering in-vehicle times:"):
                        self._calculateFareFactor()
                        if EMME_VERSION >= (4,2,1):
                            matrixCalcTool(self._getFixIVTTSpec(), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                            _m.logbook_write("IVTT matrix fixed.")
                            matrixCalcTool(self._getFixWalkSpec(), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                            _m.logbook_write("Walk matrix fixed.")
                        else:
                            matrixCalcTool(self._getFixIVTTSpec(), self.scenario)
                            _m.logbook_write("IVTT matrix fixed.")
                            matrixCalcTool(self._getFixWalkSpec(), self.scenario)
                            _m.logbook_write("Walk matrix fixed.")
                        
                with _m.logbook_trace("Applying the constraint matrices to component matrices:"):
                    if EMME_VERSION >= (4,2,1):
                        matrixCalcTool(self._getApplyConstraintSpec(self.boardingMatrix), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                        matrixCalcTool(self._getApplyConstraintSpec(self.costMatrix), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                        matrixCalcTool(self._getApplyConstraintSpec(self.ivttMatrix), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                        matrixCalcTool(self._getApplyConstraintSpec(self.walkMatrix), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                        matrixCalcTool(self._getApplyConstraintSpec(self.waitMatrix), self.scenario,
                                                 num_processors=self.NumberOfProcessors)
                    else:
                        matrixCalcTool(self._getApplyConstraintSpec(self.boardingMatrix), self.scenario)
                        matrixCalcTool(self._getApplyConstraintSpec(self.costMatrix), self.scenario)
                        matrixCalcTool(self._getApplyConstraintSpec(self.ivttMatrix), self.scenario)
                        matrixCalcTool(self._getApplyConstraintSpec(self.walkMatrix), self.scenario)
                        matrixCalcTool(self._getApplyConstraintSpec(self.waitMatrix), self.scenario)

    ##########################################################################################################
    
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
                    
    def _initIVTT(self, mtxId):
        self.ivttMatrix = _util.initializeMatrix(mtxId, name='trIVTT', description= 'Avg total in vehicle times')
    
    def _initWalk(self, mtxId):
        self.walkMatrix = _util.initializeMatrix(mtxId, name= 'trWalk', description= 'Avg total walk times')
    
    def _initWait(self, mtxId):
        self.waitMatrix = _util.initializeMatrix(mtxId, name= 'trWait', description= 'Avg total wait times')
    
    def _initBoard(self, mtxId):
        self.boardingMatrix = _util.initializeMatrix(mtxId, name= 'trBord', description= 'Avg total boarding times')
    
    def _initCost(self, mtxId):
        self.costMatrix = _util.initializeMatrix(mtxId, name= 'trCost', description= 'Avg total transit cost (fares)')     
            
    def _assignmentCheck(self):
        if self.scenario.transit_assignment_type != 'EXTENDED_TRANSIT_ASSIGNMENT':
            raise Exception("No extended transit assignment results were found for scenario %s!" %self.scenario.id)    
    
    def _calculateFareFactor(self):
        self._appliedFareFactor = 0
        if self.FarePerception != 0:
            self._appliedFareFactor = 60.0 / self.FarePerception
    
    def _getSelectLineAnalysisSpec(self):
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
                "analyzed_demand": self.ivttMatrix.id, #---Analyzed demand (this may need to be changed)  I've changed this to by a matrix that will exist
                "constraint": None,
                "results": {
                    "strategy_values": self._selectLineMatrix.id, #---Strategy results
                    "selected_demand": None, #---Demand results
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        
        return spec
    
    def _getFeasibilityMatrixSpec(self):
        #          (walk < cutoff) AND (wait < cutoff) AND ((walk + wait + ivtt) < cutoff)   
        expression = "({0} < {3}) && ({1} < {4}) && (({0} + {1} + {2}) < {5})".format(self.walkMatrix.id,
                                                                                    self.waitMatrix.id,
                                                                                    self.ivttMatrix.id,
                                                                                    str(self.WalkTimeCutoff),
                                                                                    str(self.WaitTimeCutoff),
                                                                                    str(self.TotalTimeCutoff))
        
        spec = {
                "expression": expression,
                "result": self.feasibilityMatrix.id,
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
    
    def _getInLineFaresAnalysisSpec(self):
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
                "analyzed_demand": self.ivttMatrix.id, #---Some Analyzed demand matrix is now requires
                "constraint": None,
                "results": {
                    "strategy_values": self.lineFaresMatrix.id, #---RESULT MATRIX
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return spec
    
    def _getBoardingFaresAnalysisSpec(self):
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
                "analyzed_demand": self.ivttMatrix.id, #---Some Analyzed demand matrix is now requires
                "constraint": None,
                "results": {
                    "strategy_values": self.accessFaresMatrix.id, #---RESULT MATRIX
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return spec
    
    def _getFixIVTTSpec(self):
        spec = {
                "expression": "({0} - {1} * {2}).max.0".format(self.ivttMatrix.id,
                                                               self.lineFaresMatrix.id,
                                                               self._appliedFareFactor),
                "result": self.ivttMatrix.id,
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
    
    def _getFixWalkSpec(self):
        spec = {
                "expression": "({0} - {1} * {2}).max.0".format(self.walkMatrix.id,
                                                               self.accessFaresMatrix.id,
                                                               self._appliedFareFactor),
                "result": self.walkMatrix.id,
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
    
    def _getMatrixCleanupSpec(self):
        spec = {
                "expression": "(%s > 0)" %self._selectLineMatrix.id,
                "result": self._selectLineMatrix.id,
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
    
    def _getTimeComponentAnalysisSpec(self): 
        spec = {
                "by_mode_subset": {
                                   "modes": self._modeList,
                                   "actual_total_boarding_times": self.boardingMatrix.id,
                                   "actual_in_vehicle_times": self.ivttMatrix.id,
                                   "actual_aux_transit_times": self.walkMatrix.id 
                                   },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": self.waitMatrix.id
                }
        
        return spec
    
    def _getCostAnalysisSpec(self):
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
                "analyzed_demand": self.ivttMatrix.id, #---Some Analyzed demand matrix is now requires
                "constraint": None,
                "results": {
                    "strategy_values": self.costMatrix.id, #---RESULT MATRIX
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return spec
    
    def _getApplyConstraintSpec(self, baseMtx):
        spec = {
                "expression": "{0} * {1} * {2}".format(baseMtx.id, self._selectLineMatrix.id, self.feasibilityMatrix.id) ,
                "result": baseMtx.id,
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
    
    def _getCostSumSpec(self):
        spec = {
                "expression": "{0} + {1}".format(self.accessFaresMatrix.id, self.lineFaresMatrix.id),
                "result": self.costMatrix.id,
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
    
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg    