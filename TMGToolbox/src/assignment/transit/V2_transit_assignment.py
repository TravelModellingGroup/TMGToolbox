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
BASIC TRANSIT ASSIGNMENT

    Authors: Peter Kucirek

    Latest revision by: @pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.1.0 [Description]
    
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

class BasicTransitAssignment(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    DemandMatrixNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    
    WaitPerception = _m.Attribute(float) #
    WalkPerception = _m.Attribute(float) #
    InVehiclePerception = _m.Attribute(float) #
    BoardingPerception = _m.Attribute(float) #
    
    UseAdditiveDemand = _m.Attribute(bool) #
    UseEM4Options = _m.Attribute(bool) # Not yet used. Future proofing.
    WaitFactor = _m.Attribute(float) #
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    demandMatrix = _m.Attribute(_m.InstanceType) #
    modes = _m.Attribute(_m.ListType)
    
    #---Internal variables
    _modeList = [] #
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(2)
        self.WaitFactor = 0.5
        self.UseAdditiveDemand = False
        self.UseEM4Options = False
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Basic Transit Assignment v%s" %self.version,
                     description="Executes a basic transit assignment. Boarding penalties are \
                         assumed to be loaded into <b>UT3</b>.",
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
                             allow_none=True)
        
        pb.add_select_mode(tool_attribute_name='modes',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Modes:')
        
        pb.add_checkbox(tool_attribute_name='UseAdditiveDemand',
                        title="Use additive demand?")
        
        pb.add_header("PERCEPTION FACTORS")
        #----------------------------------
        pb.add_text_box(tool_attribute_name='WaitFactor',
                        size=4,
                        title='Wait factor:',
                        note='Default is 0.5')
        
        pb.add_text_box(tool_attribute_name='WaitPerception',
                        size=4,
                        title='Wait time perception:')
        
        pb.add_text_box(tool_attribute_name='WalkPerception',
                        size=4,
                        title='Walk perception:')
        
        pb.add_text_box(tool_attribute_name='InVehiclePerception',
                        size=4,
                        title='In-vehicle perception:')
        
        pb.add_text_box(tool_attribute_name='BoardingPerception',
                        size=4,
                        title='Boarding perception:')
        
        return pb.render()
        
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        #Run is called from Modeller.
        self.isRunningFromXTMF = False
        
        # Fix the checkbox problem
        if self.UseAdditiveDemand == None: #If the checkbox hasn't been clicked, this variable will be set to None by Modeller
            self.UseAdditiveDemand = False
        
        # Convert the list of mode objects to a list of mode characters
        for m in self.modes:
            self._modeList.append(m.id)
        
        # Execute
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, ScenarioNumber, DemandMatrixNumber, ModeString, WaitPerception,
                 WalkPerception, InVehiclePerception, BoardingPerception, UseAdditiveDemand,
                 WaitFactor, UseEM4Options):
        
        #---1 Set up scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        #---2 Set up Demand matrix
        if DemandMatrixNumber == 0:
            self.demandMatrix = None
        else:
            self.demandMatrix = _m.Modeller().emmebank.matrix("mf%s" %DemandMatrixNumber)
            if self.demandMatrix == None:
                raise Exception("Matrix %s does not exist!" %DemandMatrixNumber)
        
        #---3 Set up modes
        for i in range(0, len(ModeString)):
            if not self._modeList.__contains__(ModeString[i]):
                self._modeList.append(ModeString[i])
                
        #---4 Pass in remaining args
        self.WaitPerception = WaitPerception
        self.WalkPerception = WalkPerception
        self.InVehiclePerception = InVehiclePerception
        self.BoardingPerception = BoardingPerception
        self.UseAdditiveDemand = UseAdditiveDemand
        self.WaitFactor = WaitFactor
        self.UseEM4Options = UseEM4Options
        
        self.isRunningFromXTMF = True
        
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            self._tracker.completeTask()
            
            try:
                transitAssignmentTool = _m.Modeller().tool("inro.emme.standard.transit_assignment.extended_transit_assignment")
            except Exception, e:
                transitAssignmentTool = _m.Modeller().tool("inro.emme.transit_assignment.extended_transit_assignment")
            
            with self._demandMatrixMANAGER():
                
                self._tracker.runTool(transitAssignmentTool,
                                      self._getAssignmentSpec(),# Specification
                                      self.scenario,            # Scenario
                                      self.UseAdditiveDemand)   # Use additional volumes
        self._tracker.reset()         


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
            #def initializeMatrix(id=None, default=0, name="", description="", matrix_type='FULL'):
            self.demandMatrix = _util.initializeMatrix(matrix_type='SCALAR', name='trscal', description="Scalar matrix to get transit times")
            
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
                _m.Modeller().emmebank.delete_matrix(self.demandMatrix.id)
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    '''
    ScenarioNumber = _m.Attribute(int)
    DemandMatrixNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    
    WaitPerception = _m.Attribute(float) #
    WalkPerception = _m.Attribute(float) #
    InVehiclePerception = _m.Attribute(float) #
    BoardingPerception = _m.Attribute(float) #
    
    UseAdditiveDemand = _m.Attribute(bool) #
    UseEM4Options = _m.Attribute(bool) # Not yet used. Future proofing.
    WaitFactor = _m.Attribute(float) #
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    demandMatrix = _m.Attribute(_m.InstanceType) #
    modes = _m.Attribute(_m.ListType)
    
    #---Internal variables
    _modeList = [] #
    '''
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "Version": self.version,
                "Demand Matrix" : str(self.demandMatrix),
                "Modes": str(self._modeList),
                "Wait Perception": self.WaitPerception,
                "Walk Perception": self.WalkPerception,
                "In Vehicle Perception": self.InVehiclePerception,
                "Boarding Perception": self.BoardingPerception,
                "Headway Fraction": self.WaitFactor,
                "Use Additive Demand Flag": self.UseAdditiveDemand,
                "Use Emme 4 Options Flag": self.UseEM4Options,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _getAssignmentSpec(self):
        spec = {
                "modes": self._modeList, #---MODES
                "demand": self.demandMatrix.id, #---DEMAND MATRIX
                "waiting_time": {
                                "headway_fraction": self.WaitFactor, #---WAIT FACTOR
                                "effective_headways": "hdw",
                                "spread_factor": 1,
                                "perception_factor": self.WaitPerception #---WAIT PERCEPTION
                                },
                "boarding_time": {
                                    "at_nodes": None,
                                    "on_lines": {
                                                "penalty": "ut3", #---BOARDING ATTRIBUTE
                                                "perception_factor": self.BoardingPerception #---BOARDING PERCEPTION
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
                                    "perception_factor": self.InVehiclePerception #---IVTT PERCEPTION
                                    },
                "in_vehicle_cost": None, #---IN VEHICLE FARES
                "aux_transit_time": {
                                     "perception_factor": self.WalkPerception #---WALK PERCEPTION
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
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    