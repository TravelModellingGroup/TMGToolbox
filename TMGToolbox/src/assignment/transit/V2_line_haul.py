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
Station to Station Assignment

    Authors: Peter Kucirek

    Latest revision by: James Vaughan
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.1.0 Added Parallel processing for EMME 4.1+
    
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

class Station2StationAssignment(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    DemandMatrixNumber = _m.Attribute(int)
    WaitTimeMatrixNumber = _m.Attribute(int) #
    InVehicleTimeMatrixNumber = _m.Attribute(int) #
    
    StationSelectorExpression = _m.Attribute(str) #
    ModeString = _m.Attribute(str)
    
    WaitFactor = _m.Attribute(float) #
    WaitPerception = _m.Attribute(float) #
    WalkPerception = _m.Attribute(float) #
    
    UseAdditiveDemand = _m.Attribute(bool) #
    UseEM4Options = _m.Attribute(bool) # Not yet used. Future proofing.
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    modes = _m.Attribute(_m.ListType) #
    demandMatrix = _m.Attribute(_m.InstanceType) #
    
    #---Internal variables
    _modeList = []
    
    def __init__(self):
        #ENTER IN THE NUMBER OF TASKS. THIS WILL CRASH OTHERWISE.
        #******************************************************************************
        self._tracker = _util.ProgressTracker(6) # Enter in the correct number of tasks
        #******************************************************************************
        
        # Set up variable defaults
        self.WaitFactor = 0.5
        self.StationSelectorExpression = "7000-8000"
        self.WaitPerception = 2.0
        self.WalkPerception = 2.0
        self.UseAdditiveDemand = False
        self.UseEM4Options = False
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Station to Station Assignment v%s" %self.version,
                     description="Assigns a limited matrix of demand to centroids which represent \
                             GO train stations. Can assign a scalar matrix of 0 or a full matrix of \
                             demand (constrained by the station selector). Unlike most other transit \
                             assignment tools, this tool saves the constrained IVTT and wait times \
                             matrices as outputs.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("ASSIGNMENT SETUP")
        #-----------------------------------------------------------------------------
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name='demandMatrix',
                             title='Demand Matrix:',
                             note="If no matrix is selected, a scalar matrix of value '0' will\
                             be assigned.",
                             allow_none=True)
        
        pb.add_select_mode(tool_attribute_name='modes',
                           title='Assignment Modes',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           note="<font color='red'><b>Modes are available for the primary scenario only.</b></font>\
                           <br>Actual assignment is based on mode ids, so this is only a problem\
                           <br>if modes differ across scenarios.")
        
        pb.add_text_box(tool_attribute_name='StationSelectorExpression',
                        size=150,
                        title="Station centroid selection:",
                        note="Write an expression to select which centroids are stations.<br>\
                            A single range is written as '[start]-[stop]' (e.g., '7000-8000') <br>\
                            with multiple ranges separated by ';'",
                        multi_line=True)
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_checkbox(tool_attribute_name='UseAdditiveDemand')
            with t.table_cell():
                pb.add_html("Assign additional demand?")
            with t.table_cell():
                pb.add_checkbox(tool_attribute_name='UseEM4Options')
            with t.table_cell():
                pb.add_html("Use new Emme 4 options?")
        
        pb.add_header("ROUTE CHOICE PARAMETERS")
        #-----------------------------------------------------------------------------
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='WaitPerception',
                        size=6,
                        title="Wait Time Perception")
                
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='WaitFactor',
                        size=6,
                        title="Headway Fraction")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='WalkPerception',
                                size=6,
                                title="Walk Time Perception")
        
        pb.add_header("ASSIGNMENT OUTPUT")
        #-----------------------------------------------------------------------------
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='WaitTimeMatrixNumber',
                                size=2,
                                title="Wait Times Matrix Number",
                                note="If left blank, an available matrix will be created.")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='InVehicleTimeMatrixNumber',
                                size=2,
                                title="In-Vehicle Times Matrix Number",
                                note="If left blank, an available matrix will be created.")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        #Setup 
        self._modeList = [str(m) for m in self.modes]
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, ScenarioNumber, DemandMatrixNumber, WaitTimeMatrixNumber, InVehicleTimeMatrixNumber, \
                 StationSelectorExpression, ModeString, WaitFactor, WaitPerception, WalkPerception,\
                 UseAdditiveDemand, UseEM4Options):
        
        #---1 Set up scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        #---2 Set up the demand matrix
        if DemandMatrixNumber == 0:
            self.demandMatrix = None
        else:
            self.demandMatrix = _m.Modeller().emmebank.matrix('mf%s' %DemandMatrixNumber)
            if self.demandMatrix == None:
                raise Exception("Could not find matrix 'mf%s' in the databank!" %DemandMatrixNumber)
            
        #---3 Set up modes
        self._modeList = [c for c in ModeString]
        
        #---4 Pass in remaining args
        self.WaitTimeMatrixNumber = WaitTimeMatrixNumber
        self.InVehicleTimeMatrixNumber = InVehicleTimeMatrixNumber
        self.StationSelectorExpression = StationSelectorExpression
        self.WaitFactor = WaitFactor
        self.WalkPerception = WalkPerception
        self.UseAdditiveDemand = UseAdditiveDemand
        self.UseEM4Options = UseEM4Options
        
        self.isRunningFromXTMF = True
        
        #---Execute
        
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    ##########################################################################################################    
    
    
    def _execute(self):
        self._tracker.reset()
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            try:
                transitAssignmentTool = _m.Modeller().tool("inro.emme.standard.transit_assignment.extended_transit_assignment")
                matrixResultsTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
                matrixCalcTool = _m.Modeller().tool("inro.emme.standard.matrix_calculation.matrix_calculator")
            except Exception, e:
                transitAssignmentTool = _m.Modeller().tool("inro.emme.transit_assignment.extended_transit_assignment")
                matrixResultsTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
                matrixCalcTool = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
            
            with self._demandMatrixMANAGER(): # TASK 1
                
                with _m.logbook_trace("Initializing output matrices"):
                    ivttMatrix = _util.initializeMatrix(id=self.InVehicleTimeMatrixNumber,
                                                   matrix_type='FULL',
                                                   description="Station-station IVTT matrix")
                    
                    waitMatrix = _util.initializeMatrix(id=self.WaitTimeMatrixNumber,
                                                   matrix_type='FULL',
                                                   description="Station-station wait time matrix")
                    
                    self._tracker.completeTask() # TASK 2
                
                with _m.logbook_trace("Running transit assignment"):
                    self._tracker.runTool(transitAssignmentTool, self._getAssignmentSpec(),
                                      scenario=self.scenario,
                                      add_volumes=self.UseAdditiveDemand) #TASK 3
                    
                    # some error with progress reporting is occurring here.
                
                with _m.logbook_trace("Extracting output matrices"):
                    self._tracker.runTool(matrixResultsTool,
                                          self._getMatrixResultSpec(ivttMatrix, waitMatrix),
                                          scenario=self.scenario) # TASK 4
                    
                with _m.logbook_trace("Constraining output matrices"):
                    self._tracker.runTool(matrixCalcTool,
                                          self._getConstraintSpec(ivttMatrix, ivttMatrix),
                                          scenario=self.scenario) # TASK 5
                    
                    self._tracker.runTool(matrixCalcTool,
                                          self._getConstraintSpec(waitMatrix, waitMatrix),
                                          scenario=self.scenario) # TASK 6
        
        
                    
    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager  
    def _demandMatrixMANAGER(self):
        #Code here is executed upon entry
        
        with _m.logbook_trace("Initializing temporary demand matrix"):
            id=None
            if self.demandMatrix == None:
                
                self.demandMatrix = _util.initializeMatrix(id,
                                                      matrix_type='SCALAR',
                                                      name='trscal',
                                                      description='Scalar matrix to get transit times')
                
                self._tracker.completeTask()
                
            else:
                cachedMatrix = self.demandMatrix
                self.demandMatrix = _util.initializeMatrix(matrix_type='FULL', description="Constrained full matrix for station-to-station assignment")
                _m.logbook_write("Created temporary constrained full demand matrix '%s'" %id)
                
                try:
                    matrixCalcTool = _m.Modeller().tool("inro.emme.standard.matrix_calculation.matrix_calculator")
                except Exception, e:
                    matrixCalcTool = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
                
                self._tracker.runTool(matrixCalcTool,
                                      self._getConstraintSpec(cachedMatrix, self.demandMatrix), 
                                      scenario=self.scenario) #TASK 1
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            id = self.demandMatrix.id
            _m.Modeller().emmebank.delete_matrix(id)
            _m.logbook_write("Temporary matrix %s deleted." %id)
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _getConstraintSpec(self, baseMatrix, resultMatrix):
        return {
                "expression": baseMatrix.id,
                "result": resultMatrix.id,
                "constraint": {
                                "by_value": None,
                                "by_zone": {
                                            "origins": self.StationSelectorExpression,
                                            "destinations": self.StationSelectorExpression
                                            }
                               },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
    
    def _getAssignmentSpec(self):
        spec = {
                "modes": self._modeList,
                "demand": self.demandMatrix.id,
                "waiting_time": {
                                "headway_fraction": self.WaitFactor,
                                "effective_headways": "hdw",
                                "spread_factor": 1,
                                "perception_factor": self.WaitPerception
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
                                                "penalty": 0,
                                                "perception_factor": 1
                                                },
                                    "on_lines": None
                                    },
                "in_vehicle_time": {
                                    "perception_factor": 1
                                    },
                "in_vehicle_cost": None,
                "aux_transit_time": {
                                    "perception_factor": self.WalkPerception
                                    },
                "aux_transit_cost": None,
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
    
    def _getMatrixResultSpec(self, ivttMatrix, waitMatrix):
        return {
                "by_mode_subset": {
                                    "modes": self._modeList,
                                    "actual_in_vehicle_times": ivttMatrix.id
                                    },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": waitMatrix.id
                }
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        try:
            return self._tracker.getProgress()
        except Exception, e:
            print "Exception occurred during progress reporting."
            print "Tracker progress = %s" %self._tracker._progress
            print  _traceback.format_exc(e)
            raise
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    