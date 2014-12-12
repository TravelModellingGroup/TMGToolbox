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
LEGACY GTA Model fare-based transit assignment script

    Authors: Eric Miller, Michael Hain, Peter Kucirek, James Vaughan

    Latest revision by: James Vaughan
    
    
    This legacy version sets up @tfare on centroid connectors, assuming an 'old' version
    of a V3 hyper network. The newer version is set up differently and thus is incompatible
    with the legacy version. This was done strictly for the Durham Model.
    
    
'''
#---VERSION HISTORY
'''
    0.1.0 Created from macro_TransAssign2.mac
    
    0.1.1 Some major bug fixes:
        - Demand matrix was fixed to 'mf9'. Changed to use the specified matrix.
        - _calculateFareFactor() wasn't being called at all
        - Changed the type of WalkSpeed from int to float
    
    0.2.0 Modified the way this tool works with temporary database modifications.
        It now uses context managers so that it crashes gracefully. 
        
    0.2.1 Upgrades and bug fixes:
        - Fixed context managers (weren't working before)
        - Fixed UL1 calculation
        - Used Network Calculator Tool instead of a foreach loop for faster processing. 
    
    0.2.2 Testing for assignment results. Extracting travel times will produce accurate results.
    0.2.3 Added Parallel processing for EMME 4.1+
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

class LegacyFBTA(_m.Tool()):
    
    version = '0.2.2'
    tool_run_msg = ""
    
    # Variables marked with a '#' are used in the main block, and are assigned by both run and call
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int) 
    DemandMatrixNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    
    WalkSpeed = _m.Attribute(float) #
    WaitPerception = _m.Attribute(float) #
    WalkPerception = _m.Attribute(float) #
    InVehiclePerception = _m.Attribute(float) #
    BoardingPerception = _m.Attribute(float) #
    
    FarePerception = _m.Attribute(float) #
    '''To disable fare-based impedances, set this parameter to 0.0'''
    
    UseAdditiveDemand = _m.Attribute(bool) #
    WaitFactor = _m.Attribute(float) #
    
    #---Special instance types, used only from Modeller
    scenario = _m.Attribute(_m.InstanceType) #
    demandMatrix = _m.Attribute(_m.InstanceType) #
    modes = _m.Attribute(_m.ListType)
    
    #---Private vars
    _appliedFareFactor = 0 #
    _modeList = [] #
    
    def __init__(self):
        # Set up all Emme tools and data structures
            self.databank = _m.Modeller().emmebank
            try:
                self.transitAssignmentTool = _m.Modeller().tool("inro.emme.standard.transit_assignment.extended_transit_assignment")
            except Exception, e:
                self.transitAssignmentTool = _m.Modeller().tool("inro.emme.transit_assignment.extended_transit_assignment")
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Legacy Fare-Based Transit Assignment",
                     description="Executes a fare-based transit assignment (FBTA) as described \
                                 in the GTAModel Version 3 documentation: Using special functions \
                                 on centroid connectors and transit time functions. This requires \
                                 a compatible network, which can currently only be created by \
                                 <em>macro_EditNetwork.mac.</em><br><br>\
                                 This Tool can also be used to execute a more standard transit \
                                 assignment procedure by using a fare perception of <b>'0'</b>.\
                                 <br><br>This Tool executes an Extended Transit Assignment, which allows\
                                 for subsequent analyses; such as those that can be found in \
                                 <em>TMG2.Assignment.TransitAnalysis</em>.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("ASSIGNMENT SETUP")
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
        
        pb.add_text_box(tool_attribute_name='WalkSpeed',
                        size=6,
                        title='Walk speed:',
                        note='In km/hr')
        
        pb.add_text_box(tool_attribute_name='WalkPerception',
                        size=4,
                        title='Walk perception:')
        
        pb.add_text_box(tool_attribute_name='InVehiclePerception',
                        size=4,
                        title='In-vehicle perception:')
        
        pb.add_text_box(tool_attribute_name='BoardingPerception',
                        size=4,
                        title='Boarding perception:')
        
        pb.add_text_box(tool_attribute_name='FarePerception',
                        size=6,
                        title='Fare perception:',
                        note="Enter '0' to disable fare-based impedances.")
    
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
        
    def __call__(self, ScenarioNumber, DemandMatrixNumber, ModeString, WalkSpeed, WaitPerception, \
                 WalkPerception, InVehiclePerception, BoardingPerception, FarePerception, \
                 UseAdditiveDemand, WaitFactor):
        
        #---1 Set up scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        #---2 Set up Demand matrix
        if DemandMatrixNumber == 0:
            self.demandMatrix = None
        else:
            self.demandMatrix = self.databank.matrix("mf%s" %DemandMatrixNumber)
            if self.demandMatrix == None:
                raise Exception("Matrix %s does not exist!" %DemandMatrixNumber)
        
        #---3 Set up modes
        for i in range(0, len(ModeString)):
            if not self._modeList.__contains__(ModeString[i]):
                self._modeList.append(ModeString[i])
        
        #---4 Pass in remaining args
        self.WalkSpeed = WalkSpeed
        self.WaitPerception = WaitPerception
        self.WalkPerception = WalkPerception
        self.InVehiclePerception = InVehiclePerception
        self.BoardingPerception = BoardingPerception
        self.FarePerception = FarePerception
        self.UseAdditiveDemand = UseAdditiveDemand
        self.WaitFactor = WaitFactor
    
        self.isRunningFromXTMF = True
        
        #---5 Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    ##########################################################################################################
    
    def _execute(self):
        with _m.logbook_trace(name="Legacy Fare Based Transit Assignment v%s" %self.version,
                                     attributes=self._getAtts()):
                        
            self._calculateFareFactor()
            
            with nested(self._demandMatrixMANAGER(), self._walkLinksMANAGER(), self._transitFunctionsMANAGER()):
                self._calculateUL1()
                _m.logbook_write(name="Running extended transit assignment")
                self.transitAssignmentTool(self._setUpAssignment(), # Specification
                                       self.scenario,           # Scenario
                                       self.UseAdditiveDemand)  # Use additional volumes
                        
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
                self.databank.delete_matrix(self.demandMatrix.id)
    
    @contextmanager
    def _walkLinksMANAGER(self):
        #Code here is executed upon entry
        
        with _m.logbook_trace("Changing speed of modes tuv."):
            net = self.scenario.get_network()
            tMode = net.mode('t')
            uMode = net.mode('u')
            vMode = net.mode('v')
            
            tSpeed = tMode.speed
            uSpeed = uMode.speed
            vSpeed = vMode.speed
            
            tMode.speed = 'ul1*1.0'
            _m.logbook_write("Changed speed of mode 't' to 'ul1*1.0'.")
            uMode.speed = 'ul1*1.0'
            _m.logbook_write("Changed speed of mode 'u' to 'ul1*1.0'.")
            vMode.speed = 'ul1*1.0'
            _m.logbook_write("Changed speed of mode 'u' to 'ul1*1.0'.")
            
            self.scenario.publish_network(net)
            _m.logbook_write("Changes saved to databank.")
        
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            with _m.logbook_trace("Resetting modes tuv."):
                net = self.scenario.get_network()
                tMode = net.mode('t')
                uMode = net.mode('u')
                vMode = net.mode('v')
                
                tMode.speed = str(tSpeed)
                _m.logbook_write("Reset speed of mode 't' to '%s'." %tSpeed)
                uMode.speed = str(uSpeed)
                _m.logbook_write("Reset speed of mode 'u' to '%s'." %uSpeed)
                vMode.speed = str(vSpeed)
                _m.logbook_write("Reset speed of mode 'v' to '%s'." %vSpeed)
                
                self.scenario.publish_network(net)
                _m.logbook_write("Changes saved to databank.")
    
    @contextmanager
    def _transitFunctionsMANAGER(self):
        #Code here is executed upon entry
        
        functionChanger = None #Use the standard tools; it is faster and more verbose.
        try:
            functionChanger = _m.Modeller().tool("inro.emme.data.function.change_function")
        except Exception, e:
            functionChanger = _m.Modeller().tool("inro.emme.standard.data.function.change_function")
        
        expressionArchive = {}
        with _m.logbook_trace("Modifying transit time functions."):
            for f in self.databank.functions():
                if f.type == "TRANSIT_TIME":
                    expressionArchive[f.id] = f.expression
                    functionChanger(f, f.expression + " + (us3 * %s)" %(self._appliedFareFactor))
                    #f.expression += " + (us3 * %s)" %(self._appliedFareFactor)
        
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            with _m.logbook_trace("Resetting transit time functions."):
                for item in expressionArchive.iteritems():
                    f = self.databank.function(item[0])
                    functionChanger(f, item[1])
                    #f.expression = item[1]
        
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------    
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "ModeString" : str(self._modeList),
                "Walk Speed" : str(self.WalkSpeed),
                "Wait Perception":self.WaitPerception,
                "Walk Perception": self.WalkPerception,
                "IVTT Perception": self.InVehiclePerception,
                "Boarding Perception" : self.BoardingPerception,
                "Fare Perception" : self.FarePerception,
                "Is using additive demand?": self.UseAdditiveDemand,
                "Wait Factor": self.WaitFactor,
                "Is running from XTMF?" : str(self.isRunningFromXTMF),
                "self": self.__MODELLER_NAMESPACE__}
        
        if self.demandMatrix == None:
            atts['Demand Matrix'] = "SCALAR"
        else:
            atts['Demand Matrix'] = "FULL: %s" %self.demandMatrix.id
            
        return atts
    
    def _reportProgress(self, current, total):
        if self.isRunningFromXTMF:
            self.XTMFBridge.ReportProgress(float(float(current) / float(total)))
    
    def _calculateFareFactor(self):
        self._appliedFareFactor = 0
        if self.FarePerception != 0:
            self._appliedFareFactor = 60.0 / self.FarePerception
    
    def _calculateUL1(self):
        _m.logbook_write("Calculating UL1 for tuv links.")
        
        networkCalculator = None #Use the standard tools; it is faster and more verbose.
        try:
            networkCalculator = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
        except Exception, e:
            networkCalculator = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
        
        # link.data1 = 60 / link.length + self._appliedFareFactor * link.__getattribute__('@tfare') / self.WalkPerception
        spec = {
                "result": "ul1",
                "expression": 
                    "(60 * length / {0}) + ({1} * @tfare / {2})".format(self.WalkSpeed, self._appliedFareFactor, self.WalkPerception),
                "aggregation": None,
                "selections": {
                    "link": "modes=tuv"
                },
                "type": "NETWORK_CALCULATION"
                }
        
        networkCalculator(spec, scenario=self.scenario)
        
    def _setUpAssignment(self):
        
        # Ensure that modes t, u, and v are enabled
        if not self._modeList.__contains__('t'):
            self._modeList.append('t')
        if not self._modeList.__contains__('u'):
            self._modeList.append('u')
        if not self._modeList.__contains__('v'):
            self._modeList.append('v')
        
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
            
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg