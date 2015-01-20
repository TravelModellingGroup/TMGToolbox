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
Toll-Based Road Assignment

    Authors: Peter Kucirek, Eric Miller, James Vaughan

    Latest revision by: James Vaughan
    
    Executes a road assignment which allows for the generalized penalty of road tolls.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created from auto assignment macro
    
    0.2.3 Fixed a bug in which exceptions were being eaten by one of my context managers.
    
    0.2.4 Added in progress tracker to report progress to XTMF and Modeller. Also, added
            feature to enable/disable "high-performance mode" which affects the number of
            cores used for processing. High performance = all cores. Otherwise, number of 
            cores = max - 2
            
    1.1.0 Upgraded to stable version for release. New features:
        - Tool defaults
        - Better naming convention
        - Unified output matrix handling
        - Optional arguments added.
        
    1.1.1 Bug fixes. Should actually run now.
    
    1.1.2 Fixed bug which occurs when a new matrix is selected for output.
    
    1.2.0 Upgraded to use SOLA traffic assignment (Emme 4.1 and newer). Other new features:
        - Print status to console (also to XTMF) whilst running. Includes the stopping criterion
        - All-or-nothing scenario manager doesn't copy over the transit strategy files.
        
    1.2.1 Removed a scaling factor being incorrectly applied to the Best Relative Gap

    1.2.1 Added the ability to use a peak period matrix instead of just a scaling factor
'''

import inro.modeller as _m
import traceback as _traceback
import multiprocessing
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(float)

##########################################################################################################

class TollBasedRoadAssignment(_m.Tool()):
    
    version = '1.2.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    #---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    xtmf_DemandMatrixNumber = _m.Attribute(int)
    DemandMatrix = _m.Attribute(_m.InstanceType)
    SelectTollLinkExpression = _m.Attribute(str)    
    
    TimesMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    TollsMatrixId = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    
    PeakHourFactor = _m.Attribute(str)
    LinkCost = _m.Attribute(float)
    TollCost = _m.Attribute(float)
    TollWeight = _m.Attribute(float)
    Iterations = _m.Attribute(int)
    rGap = _m.Attribute(float)
    brGap = _m.Attribute(float)
    normGap = _m.Attribute(float)
    
    PerformanceFlag = _m.Attribute(bool)
    SOLAFlag = _m.Attribute(bool)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario
        
        mf10 = _MODELLER.emmebank.matrix('mf10')
        if mf10 != None:
            self.DemandMatrix = mf10
        
        self.SelectTollLinkExpression = "vdf=14"
        self.PeakHourFactor = "0.43"
        self.LinkCost = 0
        self.TollCost = 0
        self.TollWeight = 0
        self.Iterations = 100
        self.rGap = 0
        self.brGap = 0.1
        self.normGap = 0.05
        self.PerformanceFlag = False
        self.RunTitle = ""
        
        if EMME_VERSION >= 4.1:
            self.SOLAFlag = True
        else:
            self.SOLAFlag = False

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Toll Based Road Assignment v%s" %self.version,
                     description="Executes a standard Emme traffic assignment using tolls for link \
                         costs converted to a time penalty. The actual times and costs are recovered \
                         by running a second 'all-or-nothing' assignment. This version applies a \
                         uniform toll cost to links meeting a selector expression.\
                         <br><br><b>Temporary Storage Requirements:</b> 2 extra \
                         link attributes, 1 full matrix, 1 scenario.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("SCENARIO")
        
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select a Scenario",
                               allow_none=False)
        
        matrixCount = sum([1 for m in _MODELLER.emmebank.matrices() if m.type=='FULL'])
        demandMatrixNote = ""
        if matrixCount == 0:
            demandMatrixNote = "<font color=red><b>No full matrices in emmebank!</b></font>"
            pb.runnable= False
        
        pb.add_select_matrix(tool_attribute_name="DemandMatrix",
                             title="Select a demand matrix",
                             filter="FULL", note=demandMatrixNote,
                             allow_none=False)
        
        pb.add_text_box(tool_attribute_name='SelectTollLinkExpression',
                        size=100, multi_line=True,
                        title="Toll Link Selector")
        
        pb.add_header("OUTPUT MATRICES")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name='TimesMatrixId',
                        overwrite_existing=True,
                        matrix_type='FULL',
                        note='Create or override',
                        title='Travel times matrix')
            
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name="CostMatrixId", 
                        overwrite_existing=True,
                        matrix_type='FULL',
                        note='Create or override',
                        title='Travel costs matrix')
        
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name="TollsMatrixId", 
                        overwrite_existing=True,
                        matrix_type='FULL',
                        note='Create or override',
                        title='Tolls matrix')
                
        pb.add_text_box(tool_attribute_name='RunTitle',
                        size=25, title="Run Title",
                        note="25-char run descriptor")
        
        pb.add_header("PARAMETERS")
        
        with pb.add_table(visible_border=False) as t:
            
            with t.table_cell():
                pb.add_html("<b>Peak Hour Factor</b>")
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="PeakHourFactor", 
                        size=10)
            
            with t.table_cell():
                pb.add_html("Converts peak period demand to a single assignment hour.")
            
            t.new_row()
            
            with t.table_cell():
                pb.add_html("<b>Link Unit Cost</b>")
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="LinkCost", 
                        size=10)
            
            with t.table_cell():
                pb.add_html("Link base cost, in $/km")
            
            t.new_row()
            
            with t.table_cell():
                pb.add_html("<b>Toll Unit Cost</b>")
        
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="TollCost", 
                        size=10)
            
            with t.table_cell():
                pb.add_html("Toll base cost, in $/km. Applied to selected links.")
            
            t.new_row()
            
            with t.table_cell():
                pb.add_html("<b>Toll Perception</b>")
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="TollWeight", 
                        size=10)
            
            with t.table_cell():
                pb.add_html("The generalized perception of toll, in $/hr")
        
        pb.add_header("CONVERGANCE CRITERIA")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="Iterations", 
                        size=5,
                        title='Iterations')
        
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="rGap", 
                        size=12,
                        title='Relative gap')
        
            #t.new_row()
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="brGap", 
                        size=12,
                        title='Best relative gap')
        
            with t.table_cell():
                pb.add_text_box(tool_attribute_name="normGap", 
                        size=12,
                        title='Normalized gap')
        
        pb.add_header("Tool Options")
        
        pb.add_checkbox(tool_attribute_name="PerformanceFlag",
                        label="Enable high performance mode?",
                        note="This mode will use more cores for assignment,<br>\
                            at the cost of slowing down other processes.")
        
        if EMME_VERSION >= 4.1:
            pb.add_checkbox(tool_attribute_name= 'SOLAFlag',
                            label= "Use SOLA traffic assignment?")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        if self.DemandMatrix == None: raise NullPointerException("Demand matrix not specified")
        if self.PeakHourFactor == None: raise NullPointerException("Peak hour factor not specified")
        if self.LinkCost == None: raise NullPointerException("Link unit cost not specified")
        if self.TollCost == None: raise NullPointerException("Toll unit cost not specified")
        if self.TollWeight == None: raise NullPointerException("Toll perception not specified")
        if self.Iterations == None: raise NullPointerException("Max iterations not specified")
        if self.rGap == None: raise NullPointerException("Relative gap not specified")
        if self.brGap == None: raise NullPointerException("Best relative gap not specified")
        if self.normGap == None: raise NullPointerException("Normalized gap not specified")
        
        
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixNumber, TimesMatrixId, CostMatrixId, TollsMatrixId,
                 PeakHourFactor, LinkCost, TollCost, TollWeight, Iterations, rGap, brGap, normGap, PerformanceFlag,
                 RunTitle, SelectTollLinkExpression, SOLAFlag):
        
        #---1 Set up Scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.DemandMatrix =_m.Modeller().emmebank.matrix("mf%s" %xtmf_DemandMatrixNumber)
        if (self.DemandMatrix == None):
            raise Exception("Matrix %s was not found!" %xtmf_DemandMatrixNumber)
        
        #---2. Pass in remaining args
        self.TimesMatrixId = TimesMatrixId
        self.CostMatrixId = CostMatrixId
        self.TollsMatrixId = TollsMatrixId
        self.PeakHourFactor = PeakHourFactor
        self.LinkCost = LinkCost
        self.TollCost = TollCost
        self.TollWeight = TollWeight
        self.Iterations = Iterations
        self.rGap = rGap
        self.brGap = brGap
        self.normGap = normGap
        
        self.isRunningFromXTMF = True
        self.RunTitle = RunTitle[:25]
        self.SelectTollLinkExpression = SelectTollLinkExpression
        
        if EMME_VERSION >= 4.1:
            self.SOLAFlag = SOLAFlag
        else:
            self.SOLAFlag = False
        
        #---3. Run
        try:
            self._execute()
        except Exception, e:
            raise Exception(_util.formatReverseStack())
    
    ##########################################################################################################    
    
    
    def _execute(self):
        
        with _m.logbook_trace(name="%s (%s v%s)" %(self.RunTitle, self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
            print "Starting Road Assignment"
            self._tracker.reset()
            
            if EMME_VERSION < 4:
                matrixCalcTool = _MODELLER.tool("inro.emme.standard.matrix_calculation.matrix_calculator")
                trafficAssignmentTool = _MODELLER.tool("inro.emme.standard.traffic_assignment.standard_traffic_assignment")
                networkCalculationTool = _MODELLER.tool("inro.emme.standard.network_calculation.network_calculator")
            else:
                matrixCalcTool = _MODELLER.tool("inro.emme.matrix_calculation.matrix_calculator")
                networkCalculationTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator")
                if self.SOLAFlag:
                    trafficAssignmentTool = _MODELLER.tool('inro.emme.traffic_assignment.sola_traffic_assignment')
                else:
                    trafficAssignmentTool = _MODELLER.tool("inro.emme.traffic_assignment.standard_traffic_assignment")
            
            self._tracker.startProcess(4)
            
            self._initOutputMatrices()
            self._tracker.completeSubtask()
            
            with nested(self._costAttributeMANAGER(), self._tollAttributeMANAGER())\
                    as (costAttribute, tollAttribute): 
                with _util.tempMatrixMANAGER(description="Peak hour matrix") as peakHourMatrix:
                    
                    with _m.logbook_trace("Calculating link costs"):
                        networkCalculationTool(self._getLinkCostCalcSpec(costAttribute.id), scenario=self.Scenario)
                        self._tracker.completeSubtask()
                    
                    if self.SelectTollLinkExpression and not self.SelectTollLinkExpression.isspace():
                        #Only calculate tolls if the selector expression isn't empty or whitespace
                        with _m.logbook_trace("Calculating link tolls"):
                            try:
                                networkCalculationTool(self._getLinkTollCalcSpec(tollAttribute.id), scenario=self.Scenario)
                                self._tracker.completeSubtask()
                            except Exception, e:
                                raise Exception("Error applying toll link selector expression: %s" %e)
                    
                    with _m.logbook_trace("Calculating peak hour matrix"):
                        matrixCalcTool(self._getPeakHourSpec(peakHourMatrix.id))
                        self._tracker.completeSubtask()
                        
                    
                    appliedTollFactor = self._calculateAppliedTollFactor()
                    self._tracker.completeTask()
                    
                    with _m.logbook_trace("Running primary road assignment."):
                        print "Running primary road assignment"
                        
                        if self.SOLAFlag:
                            spec = self._getPrimarySOLASpec(peakHourMatrix.id, tollAttribute.id, appliedTollFactor)
                        else:
                            spec = self._getPrimaryRoadAssignmentSpec(peakHourMatrix.id, tollAttribute.id, 
                                                                  appliedTollFactor)
                        
                        report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                        
                        stoppingCriterion = report['stopping_criterion']
                        iterations = report['iterations']
                        if len(iterations) > 0: finalIteration = iterations[-1]
                        else:
                            finalIteration = {'number': 0}
                            stoppingCriterion = 'MAX_ITERATIONS'
                        number = finalIteration['number']
                        
                        if stoppingCriterion == 'MAX_ITERATIONS':
                            val = finalIteration['number']
                        elif stoppingCriterion == 'RELATIVE_GAP':
                            val = finalIteration['gaps']['relative']
                        elif stoppingCriterion == 'NORMALIZED_GAP':
                            val = finalIteration['gaps']['normalized']
                        elif stoppingCriterion == 'BEST_RELATIVE_GAP':
                            val = finalIteration['gaps']['best_relative']
                        else:
                            val = 'undefined'
                        
                        print "Primary assignment complete at %s iterations" %number
                        print "Stopping criterion was %s with a value of %s." %(stoppingCriterion, val)
                    
                    self._tracker.startProcess(3)
                    with self._AoNScenarioMANAGER() as allOrNothingScenario:
                        self._tracker.completeSubtask
                        
                        with _m.logbook_trace("All or nothing assignment to recover costs:"):
                            print "Running all-or-nothing assignment to recover costs."
                            
                            with _m.logbook_trace("Copying auto times into UL2"):
                                networkCalculationTool(self._getSaveAutoTimesSpec(), scenario=allOrNothingScenario)
                                self._tracker.completeSubtask
                            
                            with _m.logbook_trace("Preparing function 98 for assignment"):
                                self._modifyFunctionForAoNAssignment()
                                networkCalculationTool(self._getChangeLinkVDFto98Spec(), scenario=allOrNothingScenario)
                                self._tracker.completeSubtask
                            
                            self._tracker.completeTask()
                            
                            with _m.logbook_trace("Running all or nothing assignment"):
                                if self.SOLAFlag:
                                    spec = self._getAllOrNothingSOLASpec(peakHourMatrix.id, costAttribute.id)
                                else:
                                    spec = self._getAoNAssignmentSpec(peakHourMatrix.id, costAttribute.id)
                                
                                self._tracker.runTool(trafficAssignmentTool,
                                                      spec, scenario= allOrNothingScenario)
        print "Road Assignment complete."

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _AoNScenarioMANAGER(self):
        #Code here is executed upon entry
        
        tempScenarioNumber = _util.getAvailableScenarioNumber()
        
        if tempScenarioNumber == None:
            raise Exception("No additional scenarios are available!")
        
        scenario = _MODELLER.emmebank.copy_scenario(self.Scenario.id, tempScenarioNumber, 
                                                    copy_path_files= False, 
                                                    copy_strat_files= False, 
                                                    copy_db_files= False)
        scenario.title = "All-or-nothing assignment"
        
        _m.logbook_write("Created temporary Scenario %s for all-or-nothing assignment." %tempScenarioNumber)
        
        try:
            yield scenario
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _MODELLER.emmebank.delete_scenario(tempScenarioNumber)
            _m.logbook_write("Deleted temporary Scenario %s" %tempScenarioNumber)
    
    @contextmanager
    def _costAttributeMANAGER(self):
        #Code here is executed upon entry
        
        attributeCreated = False
        
        costAttribute = self.Scenario.extra_attribute('@lkcst')
        if costAttribute == None:
            #@lkcst hasn't been defined
            _m.logbook_write("Creating temporary link cost attribute '@lkcst'.")
            costAttribute = self.Scenario.create_extra_attribute('LINK', '@lkcst', default_value=0)
            attributeCreated = True
            
        elif self.Scenario.extra_attribute('@lkcst').type != 'LINK':
            #for some reason '@lkcst' exists, but is not a link attribute
            _m.logbook_write("Creating temporary link cost attribute '@lcost'.")
            costAttribute = self.Scenario.create_extra_attribute('LINK', '@lcst2', default_value=0)
            attributeCreated = True
        
        if not attributeCreated:
            costAttribute.initialize()
            _m.logbook_write("Initialized link cost attribute to 0.")
        
        try:
            yield costAttribute
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            if attributeCreated: 
                _m.logbook_write("Deleting temporary link cost attribute.")
                self.Scenario.delete_extra_attribute(costAttribute.id)
                 # Delete the extra cost attribute only if it didn't exist before.
        
    @contextmanager
    def _tollAttributeMANAGER(self):
        #Code here is executed upon entry
        
        attributeCreated = False
        
        tollAttribute = self.Scenario.extra_attribute('@toll')
        if tollAttribute == None:
            #@lkcst hasn't been defined
            _m.logbook_write("Creating temporary link cost attribute '@toll'.")
            tollAttribute = self.Scenario.create_extra_attribute('LINK', '@toll', default_value=0)
            attributeCreated = True
            
        elif self.Scenario.extra_attribute('@toll').type != 'LINK':
            #for some reason '@lkcst' is not a link attribute
            _m.logbook_write("Creating temporary link cost attribute '@toll2'.")
            tollAttribute = self.Scenario.create_extra_attribute('LINK', '@toll2', default_value=0)
            attributeCreated = True
        
        if not attributeCreated:
            tollAttribute.initialize()
            _m.logbook_write("Initialized toll attribute to 0.")
        
        try:
            yield tollAttribute
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            if attributeCreated: 
                _m.logbook_write("Deleting temporary toll attribute.")
                self.Scenario.delete_extra_attribute(tollAttribute.id)
                 # Delete the extra cost attribute only if it didn't exist before.
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = { "Run Title": self.RunTitle,
                "Scenario" : str(self.Scenario.id),
                "Demand Matrix" : self.DemandMatrix.id,
                "Times Matrix" : str(self.TimesMatrixId),
                "Cost Matrix" : str(self.CostMatrixId),
                "Toll Matrix" : str(self.TollsMatrixId),
                "Toll Selector": self.SelectTollLinkExpression,
                "Peak Hour Factor" : str(self.PeakHourFactor),
                "Link Cost" : str(self.LinkCost),
                "Toll Cost" : str(self.TollCost),
                "Toll Weight" : str(self.TollWeight),
                "Iterations" : str(self.Iterations),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts       
          
    def _initOutputMatrices(self):
        with _m.logbook_trace("Initializing output matrices:"):
            _util.initializeMatrix(self.CostMatrixId, name='acost', description='AUTO COST: %s' %self.RunTitle)
            _util.initializeMatrix(self.TimesMatrixId, name='aivtt', description='AUTO TIME: %s' %self.RunTitle)
            _util.initializeMatrix(self.TollsMatrixId, name='atoll', description='AUTO TOLL: %s' %self.RunTitle)
    
    def _getLinkCostCalcSpec(self, costAttributeId):
        return {
                "result": costAttributeId,
                "expression": "length * %f" %self.LinkCost,
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
        
    def _getLinkTollCalcSpec(self, tollAttributeId):
        return {
                "result": tollAttributeId,
                "expression": "length * %f" %self.TollCost,
                "aggregation": None,
                "selections": {
                               "link": self.SelectTollLinkExpression
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _getPeakHourSpec(self, peakHourMatrixId):
        return {
                "expression": self.DemandMatrix.id + "*" + str(self.PeakHourFactor), 
                "result": peakHourMatrixId,
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
        
    def _calculateAppliedTollFactor(self):
        appliedTollFactor = 0
        if self.TollWeight != 0:
            appliedTollFactor = 60.0 / self.TollWeight #Toll weight is in $/hr, needs to be converted to min/$
        return appliedTollFactor
    
    def _getPrimarySOLASpec(self, peakHourMatrixId, tollAttributeId, appliedTollFactor):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
        
        modeId = _util.getScenarioModes(self.Scenario, ['AUTO'])[0][0]
        #Returns a list of tuples. Emme guarantees that there is always
        #one auto mode.
        
        return {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes": [
                    {
                        "mode": modeId,
                        "demand": peakHourMatrixId,
                        "generalized_cost": {
                            "link_costs": tollAttributeId,
                            "perception_factor": appliedTollFactor
                        },
                        "results": {
                            "link_volumes": None,
                            "turn_volumes": None,
                            "od_travel_times": {
                                "shortest_paths": self.TimesMatrixId
                            }
                        },
                        "path_analysis": {
                            "link_component": tollAttributeId,
                            "turn_component": None,
                            "operator": "+",
                            "selection_threshold": {
                                "lower": None,
                                "upper": None
                            },
                            "path_to_od_composition": {
                                "considered_paths": "ALL",
                                "multiply_path_proportions_by": {
                                    "analyzed_demand": False,
                                    "path_value": True
                                }
                            }
                        },
                        "cutoff_analysis": None,
                        "traversal_analysis": None,
                        "analysis": {
                            "analyzed_demand": None,
                            "results": {
                                "od_values": self.TollsMatrixId,
                                "selected_link_volumes": None,
                                "selected_turn_volumes": None
                            }
                        }
                    }
                ],
                "path_analysis": None,
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "performance_settings": {
                    "number_of_processors": numberOfPocessors
                },
                "background_traffic": None,
                "stopping_criteria": {
                    "max_iterations": self.Iterations,
                    "relative_gap": self.rGap,
                    "best_relative_gap": self.brGap,
                    "normalized_gap": self.normGap
                }
            }
      
    
    def _getPrimaryRoadAssignmentSpec(self, peakHourMatrixId, tollAttributeId, appliedTollFactor):
        
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 2, 1)
            
        return {
                "type": "STANDARD_TRAFFIC_ASSIGNMENT",
                "classes": [
                            {
                             "mode": "c",
                             "demand": peakHourMatrixId,
                             "generalized_cost": {
                                                  "link_costs": tollAttributeId,
                                                  "perception_factor": appliedTollFactor
                                                  },
                             "results": {
                                         "link_volumes": None,
                                         "turn_volumes": None,
                                         "od_travel_times": {
                                                             "shortest_paths": self.TimesMatrixId
                                                             }
                                         },
                             "analysis": {
                                          "analyzed_demand": peakHourMatrixId,
                                          "results": {
                                                      "od_values": self.TollsMatrixId,
                                                      "selected_link_volumes": None,
                                                      "selected_turn_volumes": None
                                                      }
                                          }
                             }
                            ],
                "performance_settings": {
                                         "number_of_processors": numberOfPocessors
                                         },
                "background_traffic": None,
                "path_analysis": {
                                  "link_component": tollAttributeId,
                                  "turn_component": None,
                                  "operator": "+",
                                  "selection_threshold": {
                                                          "lower": -999999,
                                                          "upper": 999999
                                                          },
                                  "path_to_od_composition": {
                                                             "considered_paths": "ALL",
                                                             "multiply_path_proportions_by": {
                                                                                              "analyzed_demand": False,
                                                                                              "path_value": True
                                                                                              }
                                                             }
                                  },
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "stopping_criteria": {
                                      "max_iterations": self.Iterations,
                                      "best_relative_gap": self.brGap,
                                      "relative_gap": self.rGap,
                                      "normalized_gap": self.normGap
                                      }
                }
    
    def _getSaveAutoTimesSpec(self):
        return {
                "result": "ul2",
                "expression": "timau",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _modifyFunctionForAoNAssignment(self):
        allOrNothingFunc = _MODELLER.emmebank.function('fd98')
        if allOrNothingFunc == None:
            allOrNothingFunc = _MODELLER.emmebank.create_function('fd98', 'ul2')
        else:
            allOrNothingFunc.expression = 'ul2'
        
    def _getChangeLinkVDFto98Spec(self):
        return {
                "result": "vdf",
                "expression": "98",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _getAllOrNothingSOLASpec(self, peakHourMatrixId, costAttributeId):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
            
        modeId = _util.getScenarioModes(self.Scenario, ['AUTO'])[0][0]
        #Returns a list of tuples. Emme guarantees that there is always
        #one auto mode.
        
        return {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes": [
                    {
                        "mode": modeId,
                        "demand": peakHourMatrixId,
                        "generalized_cost": None,
                        "results": {
                            "link_volumes": None,
                            "turn_volumes": None,
                            "od_travel_times": {
                                "shortest_paths": None
                            }
                        },
                        "path_analysis": {
                            "link_component": costAttributeId,
                            "turn_component": None,
                            "operator": "+",
                            "selection_threshold": {
                                "lower": None,
                                "upper": None
                            },
                            "path_to_od_composition": {
                                "considered_paths": "ALL",
                                "multiply_path_proportions_by": {
                                    "analyzed_demand": False,
                                    "path_value": True
                                }
                            }
                        },
                        "cutoff_analysis": None,
                        "traversal_analysis": None,
                        "analysis": {
                            "analyzed_demand": None,
                            "results": {
                                "od_values": self.CostMatrixId,
                                "selected_link_volumes": None,
                                "selected_turn_volumes": None
                            }
                        }
                    }
                ],
                "path_analysis": None,
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "performance_settings": {
                    "number_of_processors": numberOfPocessors
                },
                "background_traffic": None,
                "stopping_criteria": {
                    "max_iterations": 0,
                    "relative_gap": 0,
                    "best_relative_gap": 0,
                    "normalized_gap": 0
                }
            }
    
    
    def _getAoNAssignmentSpec(self, peakHourMatrixId, costAttributeId):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 2, 1)
        
        return {
                         "type": "STANDARD_TRAFFIC_ASSIGNMENT",
                         "classes": [
                                     {
                                      "mode": "c",
                                      "demand": peakHourMatrixId,
                                      "generalized_cost": None,
                                      "results": {
                                                  "link_volumes": None,
                                                  "turn_volumes": None,
                                                  "od_travel_times": {
                                                                      "shortest_paths": None
                                                                      }
                                                  },
                                      "analysis": {
                                                   "analyzed_demand": None,
                                                   "results": {
                                                               "od_values": self.CostMatrixId,
                                                               "selected_link_volumes": None,
                                                               "selected_turn_volumes": None
                                                               }
                                                   }
                                      }
                                     ],
                         "performance_settings": {
                                                  "number_of_processors": numberOfPocessors
                                                  },
                         "background_traffic": None,
                         "path_analysis": {
                                           "link_component": costAttributeId,
                                           "turn_component": None,
                                           "operator": "+",
                                           "selection_threshold": {
                                                                   "lower": -999999,
                                                                   "upper": 999999
                                                                   },
                                           "path_to_od_composition": {
                                                                      "considered_paths": "ALL",
                                                                      "multiply_path_proportions_by": {
                                                                                                       "analyzed_demand": False,
                                                                                                       "path_value": True
                                                                                                       }
                                                                      }
                                           },
                         "cutoff_analysis": None,
                         "traversal_analysis": None,
                         "stopping_criteria": {
                                               "max_iterations": 0,
                                               "best_relative_gap": 0,
                                               "relative_gap": 0,
                                               "normalized_gap": 0.01
                                               }
                         }
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    