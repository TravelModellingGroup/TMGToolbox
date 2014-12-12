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
GTAModel Legacy Rail transit line-haul assignment script

    Authors: Eric Miller, Michael Hain, Peter Kucirek

    Latest revision by: James Vaughan
    
    
    This script executes a GO-rail station-to-station assignment, and reporting
    in-vehicle travel times and fares (if applicable).
    
    Comments:
        - Do we need to even apply fare-based impedances, since the number of paths
            from each station to each other station are so limited? More specifically,
            it seems proveable that the least-time path is always the least-cost path
            for this type of assignment as there are no lower-cost alternatives
            available.
        - Simillarly, are the other various perception factors really needed? 
        - Modes are hard-coded ATM.
    
'''
#---VERSION HISTORY
'''
    0.1.0 Created from macro_TransAssign2.mac
    
    0.2.0 Updated to use context managers
    
    0.2.1 - 0.2.3: Debug testing to ensure accurate results.
    
    0.2.4 Settled on not using fare-based impedances.
    
    0.2.5 Fixed a bug where the constraint matrix wasn't being applied correctly.

    0.2.6 Added Parallel processing for EMME 4.1+
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from multiprocessing import cpu_count
_util = _m.Modeller().module('tmg.common.utilities')
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')
EMME_VERSION = _util.getEmmeVersion(tuple) 

##########################################################################################################

class LegacyRailStation2StationAssignment(_m.Tool()):
    
    version = '0.2.5'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    DemandMatrixNumber = _m.Attribute(int)
    UseAdditiveDemand = _m.Attribute(bool) # 
    
    WaitPerception = _m.Attribute(float) #
    WalkPerception = _m.Attribute(float) #
    
    TotalTimeCutoff = _m.Attribute(float) #
    GOBaseFare = _m.Attribute(float) #
    
    CostMatrixNumber = _m.Attribute(int)
    InVehicleTimeMatrixNumber = _m.Attribute(int)
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    demandMatrix = _m.Attribute(_m.InstanceType) #
    costMatrix = _m.Attribute(_m.InstanceType) #
    ivttMatrix = _m.Attribute(_m.InstanceType) #
    
    #---Internal variables
    _walkLinksChanged = False
    _functionsChanged = False
    _hasConstraintMatrix = False
    _usingScalar = False
    
    def __init__(self):
        #---0. Set up all Emme tools and data structures
            self.databank = _m.Modeller().emmebank
            try:
                self.matrixCalcTool = _m.Modeller().tool("inro.emme.standard.matrix_calculation.matrix_calculator")
                self.transitAssignmentTool = _m.Modeller().tool("inro.emme.standard.transit_assignment.extended_transit_assignment")
                self.matrixAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
                self.strategyAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.strategy_based_analysis')
            except Exception, e:
                self.matrixCalcTool = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
                self.transitAssignmentTool = _m.Modeller().tool("inro.emme.transit_assignment.extended_transit_assignment")
                self.matrixAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
                self.strategyAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Legacy Station-to-station Assignment",
                     description="Executes a station-to-station assignment for commuter rail (GO Transit).\
                         <br><br> Saves matrix results for in-vehicle \
                         times and costs (fares) for feasible trips from station centroids only. Station \
                         centroids are hard-coded to NCS11 definitions.\
                         <br><br>Costs are computed assuming in-line fares are stored in <br>us3</b>.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("ASSIGNMENT OPTIONS")
        #----------------------------------
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name='demandMatrix',
                             title='Demand Matrix:',
                             note="If no matrix is selected, a scalar matrix of value '0' will\
                             be assigned.",
                             filter=["FULL"],
                             allow_none=True)
        
        pb.add_checkbox(tool_attribute_name='UseAdditiveDemand',
                        title="Use additive demand?")
        
        pb.add_header("OUTPUT MATRICES")
        #----------------------------------
        
        pb.wrap_html("Output matrices will be only contain results for GO station \
                            centroids (zones 7000 - 7999).")
        
        pb.add_select_matrix(tool_attribute_name='ivttMatrix',
                             title='IVTT Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_select_matrix(tool_attribute_name='costMatrix',
                             filter=['FULL'],
                             title="Cost Matrix:",
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_header("PERCEPTION FACTORS")
        #----------------------------------
        
        pb.add_text_box(tool_attribute_name='WaitPerception',
                        size=4,
                        title='Wait time perception:')
        
        pb.add_text_box(tool_attribute_name='WalkPerception',
                        size=4,
                        title='Walk perception:')
        
        pb.add_text_box(tool_attribute_name='TotalTimeCutoff',
                        size=6,
                        title="In-vehicle Travel Time Cutoff:",
                        note="Used for feasibility")
        
        pb.add_text_box(tool_attribute_name='GOBaseFare',
                        size=6,
                        title="GO Rail Base Fare:",
                        note="In $.")
    
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
                    
        #---2 Fix the checkbox problem
        if self.UseAdditiveDemand == None: #If the checkbox hasn't been clicked, this variable will be set to None by Modeller
            self.UseAdditiveDemand = False
        
        #---3 Initialize output matrices, if needed
        #def initializeMatrix(id=None, default=0, name="", description="", matrix_type='FULL'):
        self.ivttMatrix = _util.initializeMatrix(self.ivttMatrix, matrix_type='FULL', name= 'goIVTT', \
                                                description= 'Avg total in vehicle times for GO')
        self.costMatrix = _util.initializeMatrix(self.costMatrix, matrix_type='FULL', name='gocost',
                                            description= 'Avg total costs for GO')
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, ScenarioNumber, DemandMatrixNumber, UseAdditiveDemand, GOBaseFare, WalkPerception,
                 WaitPerception, TotalTimeCutoff, CostMatrixNumber,InVehicleTimeMatrixNumber):
        
        #---1 Set up scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        #---2 Set up Demand matrix
        if self.DemandMatrixNumber == 0:
            self.demandMatrix = None
        else:
            self.demandMatrix = self.databank.matrix("mf%s" %self.DemandMatrixNumber)
            if self.demandMatrix == None:
                raise Exception("Could not load or create demand matrix! Either matrix %s does not exist\
                                or a temporary matrix could not be created." %self.DemandMatrixNumber)
        
        #---3 Initialize output matrices
        self.ivttMatrix = _util.initializeMatrix(id= InVehicleTimeMatrixNumber, matrix_type='FULL', name= 'goIVTT',
                                            description= 'Avg total in vehicle times for GO')
        self.costMatrix = _util.initializeMatrix(id= CostMatrixNumber, matrix_type='FULL', name='gocost',
                                            description= 'Avg total costs for GO')
        
        #---4 Pass call variables into Tool
        self.UseAdditiveDemand = UseAdditiveDemand
        self.WaitPerception = WaitPerception
        self.TotalTimeCutoff = TotalTimeCutoff
        self.GOBaseFare = GOBaseFare
        
        self.isRunningFromXTMF = True
        
        #---5 Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="Legacy Line Haul Assignment v%s" %self.version,
                                     attributes=self._getAtts()):
            
            with nested(self._demandMatrixMANAGER(), self._constraintMatrixMANAGER()):                   
                with _m.logbook_trace(name="Running extended transit assignment"):
                    self.transitAssignmentTool(self._setUpAssignment(), # Specification
                                           self.scenario,           # Scenario
                                           self.UseAdditiveDemand)  # Use additional volumes
                
                with _m.logbook_trace(name="Extracting assignment results"):
                    self.matrixAnalysisTool(self._getIVTTMatrixSpec(), self.scenario)
                    self.strategyAnalysisTool(self._getCostAnalysisSpec(), self.scenario)
                    
                with _m.logbook_trace("Adding bade fare to cost matrix:"):
                    self.matrixCalcTool(self._getBaseFareSpec(), self.scenario)   
                
                with _m.logbook_trace(name="Preparing constraint matrix"):              
                     self._calculateConstraintMatrix()
                     
                with _m.logbook_trace(name="Applying constraint matrix"):
                    self._applyConstraintMatrix(self.costMatrix)
                    self._applyConstraintMatrix(self.ivttMatrix)
                
            # Cleanup is handled automatically.

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager  
    def _demandMatrixMANAGER(self):
        #Code here is executed upon entry
        
        usingScalar = False
        if self.demandMatrix == None:
            _m.logbook_write("Initializing temporary scalar demand matrix.")
            self.demandMatrix = _util.initializeMatrix(matrix_type='SCALAR', name='trscal', description= 'Scalar matrix to get transit times')
            
            if self.demandMatrix == None:
                raise Exception("Could not create temporary scalar demand matrix!")
            
            usingScalar = True
        
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            if usingScalar == True:
                _m.logbook_write("Deleting temporary scalar demand matrix.")
                self.databank.delete_matrix(self.demandMatrix.id)
      
    @contextmanager
    def _constraintMatrixMANAGER(self):
        #Code here is executed upon entry
        
        _m.logbook_write("Initializing temporary constraint matrix.")
        self.constraintMatrix = _util.initializeMatrix(matrix_type='FULL')
        
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _m.logbook_write("Deleting temporary constraint matrix %s." %self.constraintMatrix.id)
            self.databank.delete_matrix(self.constraintMatrix.id)
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "IVTT Matrix Result" : self.ivttMatrix.id,
                "Cost Matrix Result" : self.costMatrix.id,
                "Feasibility Cutoff" : self.TotalTimeCutoff,
                "Wait Perception":self.WaitPerception,
                "Walk Perception": self.WalkPerception,
                "Is using additive demand?": self.UseAdditiveDemand,
                "Is running from XTMF?" : str(self.isRunningFromXTMF),
                "self": self.__MODELLER_NAMESPACE__}
        
        if self.demandMatrix == None:
            atts['Demand Matrix'] = "SCALAR"
        else:
            atts['Demand Matrix'] = "FULL: %s" %self.demandMatrix.id
            
        return atts
    
    def _setUpAssignment(self):
                
        spec = {
                "modes": ['r','t','v'], #---MODES
                "demand": self.demandMatrix.id, #---DEMAND MATRIX
                "waiting_time": {
                                "headway_fraction": 0.5, #---WAIT FACTOR
                                "effective_headways": "hdw",
                                "spread_factor": 1,
                                "perception_factor": self.WaitPerception #---WAIT PERCEPTION
                                },
                "boarding_time": {
                                    "at_nodes": None,
                                  "on_lines": {
                                                "penalty": "ut3",
                                                "perception_factor": 1
                                                }
                                  },
                "boarding_cost": {
                                "at_nodes": {
                                             "penalty": 0, # For some reason, I can't just leave this blank.
                                             "perception_factor": 0 
                                             },
                                "on_lines": None
                                  },
                "in_vehicle_time": {
                                    "perception_factor": 1 #---IVTT PERCEPTION
                                    },
                "in_vehicle_cost": None, #---IN VEHICLE FARES
                "aux_transit_time": {
                                     "perception_factor": self.WalkPerception #---WALK PERCEPTION
                                    },
                "aux_transit_cost": None, #---WALK FARES
                "flow_distribution_at_origins": {
                                                "by_time_to_destination": "BEST_CONNECTOR",
                                                "by_fixed_proportions": None
                                                },
                "flow_distribution_between_lines": {
                                                    "consider_travel_time": False
                                                    },
                "connector_to_connector_path_prohibition": None,
                "save_strategies": True,
                "od_results": None,
                "type": "EXTENDED_TRANSIT_ASSIGNMENT"
                }
        if EMME_VERSION[0] + 0.1 * EMME_VERSION[1] >= 4.1:
            spec["performance_settings"] = {
                    "number_of_processors": cpu_count()
                    }
        return spec
    
    def _getIVTTMatrixSpec(self):
        
        spec = {
                "by_mode_subset": {
                                   "modes": ["r"],
                                   "actual_in_vehicle_times": self.ivttMatrix.id
                                   },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS"
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
                "analyzed_demand": None, #---No analyzed demand is required
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
    
    def _getBaseFareSpec(self):
        spec = {
                "expression": "{mfc} + {bfare}*(({mfc} > 0) + (p == q))".format(mfc=self.costMatrix.id, bfare=self.GOBaseFare),
                "result": self.costMatrix.id,
                "constraint": {
                    "by_value": None,
                    "by_zone": {
                        "origins": "7000-7999",
                        "destinations": "7000-7999"
                    }
                },
                "aggregation": {
                    "origins": None,
                    "destinations": None
                },
                "type": "MATRIX_CALCULATION"
            }
        
        return spec
    
    def _calculateConstraintMatrix(self):        
        spec = {
                "expression": "(int(p / 1000) == 7) * (int(q / 1000) == 7) * ({0} < 150)".format(self.ivttMatrix.id),
                "result": self.constraintMatrix.id,
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
        
        self.matrixCalcTool(spec, self.scenario)
    
    def _applyConstraintMatrix(self, subjectMatrix):
        spec = {
                "expression": "0",
                "result": subjectMatrix.id,
                "constraint": {
                               "by_value": {
                                            "interval_min": 0,
                                            "interval_max": 0,
                                            "condition": "INCLUDE",
                                            "od_values": self.constraintMatrix.id
                                            },
                               "by_zone": None
                               },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
        self.matrixCalcTool(spec, self.scenario)   
            
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    