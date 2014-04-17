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

    Authors: Peter Kucirek, Eric Miller

    Latest revision by: pkucirek
    
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
    
    2.0.0 Forked  a new version to use a link extra attribute 
    
    2.0.1 Fixed bug which occurs when a new matrix is selected for output.
    
    3.0.0 Branched to a version which calculates transit-induced background
        traffic.
    
    3.0.1 Fixed minor bug: transit vehicle auto equivalencies were not being applied
    
'''

import inro.modeller as _m
import traceback as _traceback
import multiprocessing
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class TollBasedRoadAssignment(_m.Tool()):
    
    version = '3.0.1'
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
    
    LinkTollAttributeId = _m.Attribute(str)
    
    TimesMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    TollsMatrixId = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    
    PeakHourFactor = _m.Attribute(float)
    LinkCost = _m.Attribute(float)
    TollWeight = _m.Attribute(float)
    Iterations = _m.Attribute(int)
    rGap = _m.Attribute(float)
    brGap = _m.Attribute(float)
    normGap = _m.Attribute(float)
    PerformanceFlag = _m.Attribute(bool)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario
        
        mf10 = _MODELLER.emmebank.matrix('mf10')
        if mf10 != None:
            self.DemandMatrix = mf10
        
        self.PeakHourFactor = 0.43
        self.LinkCost = 0
        self.TollWeight = 0
        self.Iterations = 100
        self.rGap = 0
        self.brGap = 0.1
        self.normGap = 0.05
        self.PerformanceFlag = False
        self.RunTitle = ""
        self.LinkTollAttributeId = "@toll"
        

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Toll Based Road Assignment v%s" %self.version,
                     description="Executes a standard Emme traffic assignment using tolls for link \
                         costs converted to a time penalty, using a specified link extra attribute \
                         containing the toll value. The actual times and costs are recovered \
                         by running a second 'all-or-nothing' assignment. \
                         <br><br> This version uses a link extra attribute containing the link\
                         toll amount, as well as calculates custom transit BG traffic from\
                         segments with flagged TTFs. It assumes that segments flagged with \
                         ttf=3 mix with traffic.\
                         <br><br><b>Temporary Storage Requirements:</b> 2 extra \
                         link attributes, 1 full matrix, 1 scenario.",
                     branding_text="TMG")
        
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
        
        keyval = {}
        for att in self.Scenario.extra_attributes():
            if not att.type == 'LINK': continue
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            keyval[att.name] = label
            
        pb.add_select(tool_attribute_name='LinkTollAttributeId',
                        keyvalues=keyval,
                        title="Link Toll Attribute")
        
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
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#LinkTollAttributeId")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#LinkTollAttributeId");
            $("#LinkTollAttributeId").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        if self.DemandMatrix == None: raise NullPointerException("Demand matrix not specified")
        if self.LinkTollAttributeId == None: raise NullPointerException("Link toll attribute not specified")
        if self.PeakHourFactor == None: raise NullPointerException("Peak hour factor not specified")
        if self.LinkCost == None: raise NullPointerException("Link unit cost not specified")
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
                 PeakHourFactor, LinkCost, TollWeight, Iterations, rGap, brGap, normGap, PerformanceFlag,
                 RunTitle, SelectTollLinkExpression):
        
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
        self.TollWeight = TollWeight
        self.Iterations = Iterations
        self.rGap = rGap
        self.brGap = brGap
        self.normGap = normGap
        
        self.isRunningFromXTMF = True
        self.RunTitle = RunTitle[:25]
        self.SelectTollLinkExpression = SelectTollLinkExpression
        
        #---3. Run
        try:
            self._execute()
        except Exception, e:
            raise Exception(_util.formatReverseStack())
    
    ##########################################################################################################    
    
    
    def _execute(self):
        
        with _m.logbook_trace(name="%s (%s v%s)" %(self.RunTitle, self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
            _m.logbook_write(name="Initializing")
            
            self._tracker.reset()
            
            try:
                matrixCalcTool = _m.Modeller().tool("inro.emme.standard.matrix_calculation.matrix_calculator")
                trafficAssignmentTool = _m.Modeller().tool("inro.emme.standard.traffic_assignment.standard_traffic_assignment")
                networkCalculationTool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
            except Exception, e:
                matrixCalcTool = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
                trafficAssignmentTool = _m.Modeller().tool("inro.emme.traffic_assignment.standard_traffic_assignment")
                networkCalculationTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
            
            self._tracker.startProcess(5)
            
            self._initOutputMatrices()
            self._tracker.completeSubtask()
            
            with nested(self._costAttributeMANAGER(),
                        _util.tempMatrixMANAGER(description="Peak hour matrix"),
                        self._transitTrafficAttributeMANAGER()) \
                    as (costAttribute, peakHourMatrix, bgTransitAttribute): #bgTransitAttribute is None
                
                with _m.logbook_trace("Calculating transit background traffic"):
                    networkCalculationTool(self._getTransitBGSpec(), scenario=self.Scenario)
                    self._tracker.completeSubtask()
                    
                with _m.logbook_trace("Calculating link costs"):
                    networkCalculationTool(self._getLinkCostCalcSpec(costAttribute.id), scenario=self.Scenario)
                    self._tracker.completeSubtask()
                    
                with _m.logbook_trace("Calculating peak hour matrix"):
                    matrixCalcTool(self._getPeakHourSpec(peakHourMatrix.id))
                    self._tracker.completeSubtask()
                    
                
                appliedTollFactor = self._calculateAppliedTollFactor()
                self._tracker.completeTask()
                
                with _m.logbook_trace("Running primary road assignment."):
                    spec = self._getPrimaryRoadAssignmentSpec(peakHourMatrix.id, costAttribute.id, 
                                                              appliedTollFactor)
                    self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                
                self._tracker.startProcess(3)
                with self._AoNScenarioMANAGER() as allOrNothingScenario:
                    self._tracker.completeSubtask
                    
                    with _m.logbook_trace("All or nothing assignment to recover costs:"):
                        with _m.logbook_trace("Copying auto times into UL2"):
                            networkCalculationTool(self._getSaveAutoTimesSpec(), scenario=allOrNothingScenario)
                            self._tracker.completeSubtask
                        
                        with _m.logbook_trace("Preparing function 98 for assignment"):
                            self._modifyFunctionForAoNAssignment()
                            networkCalculationTool(self._getChangeLinkVDFto98Spec(), scenario=allOrNothingScenario)
                            self._tracker.completeSubtask
                        
                        self._tracker.completeTask()
                        
                        with _m.logbook_trace("Running all or nothing assignment"):
                            self._tracker.runTool(trafficAssignmentTool,
                                                  self._getAoNAssignmentSpec(peakHourMatrix.id, costAttribute.id),
                                                  scenario=allOrNothingScenario)                                 

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
        
        scenario = _MODELLER.emmebank.copy_scenario(self.Scenario.id, tempScenarioNumber)
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
    def _transitTrafficAttributeMANAGER(self):
        
        attributeCreated = False
        bgTrafficAttribute = self.Scenario.extra_attribute('@tvph')
        
        if bgTrafficAttribute == None:
            bgTrafficAttribute = self.Scenario.create_extra_attribute('LINK','@tvph', 0)
            attributeCreated = True
            _m.logbook_write("Created extra attribute '@tvph'")
        else:
            bgTrafficAttribute.initialize(0)
            _m.logbook_write("Initialized existing extra attribute '@tvph' to 0.")
        
        try:
            extraParameterTool = _MODELLER.tool('inro.emme.traffic_assignment.set_extra_function_parameters')
        except Exception, e:
            extraParameterTool = _MODELLER.tool('inro.emme.standard.traffic_assignment.set_extra_function_parameters')
        
        extraParameterTool(el1 = '@tvph')
        
        try:
            yield
        finally:
            if attributeCreated:
                self.Scenario.delete_extra_attribute("@tvph")
                _m.logbook_write("Deleted extra attribute '@tvph'")
            extraParameterTool(el1 = '0')
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = { "Run Title": self.RunTitle,
                "Scenario" : str(self.Scenario.id),
                "Demand Matrix" : self.DemandMatrix.id,
                "Times Matrix" : str(self.TimesMatrixId),
                "Cost Matrix" : str(self.CostMatrixId),
                "Toll Matrix" : str(self.TollsMatrixId),
                "Toll Attribute": self.LinkTollAttributeId,
                "Peak Hour Factor" : str(self.PeakHourFactor),
                "Link Cost" : str(self.LinkCost),
                "Toll Weight" : str(self.TollWeight),
                "Iterations" : str(self.Iterations),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts       
        
    def _getTransitBGSpec(self):
        return {
                "result": "@tvph",
                "expression": "(60 / hdw) * (vauteq) * (ttf == 3)",
                "aggregation": "+",
                "selections": {
                                "link": "all",
                                "transit_line": "all"
                                },
                "type": "NETWORK_CALCULATION"
                }
    
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
            
    def _getPrimaryRoadAssignmentSpec(self, peakHourMatrixId, costAttributeId, appliedTollFactor):
        
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
                                                  "link_costs": self.LinkTollAttributeId,
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
                                  "link_component": self.LinkTollAttributeId,
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
                                      "best_relative_gap": self.brGap * 0.01,
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
    
    @_m.method(return_type=unicode)
    def _GetSelectAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            if not att.type == 'LINK': continue
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
    
    def mm(self):
        q = {
             "traversal_analysis": null,
             "classes": [
                         {
                          "generalized_cost": 
                            {
                             "link_costs": "@z407",
                             "perception_factor": 2.0
                             },
                          "results": 
                                {"link_volumes": null,
                                 "od_travel_times": 
                                    {
                                     "shortest_paths": "mf1"
                                    },
                                  "turn_volumes": null
                                  },
                          "mode": "c",
                          "analysis": {
                                       "analyzed_demand": "mf1",
                                       "results": {
                                                   "selected_turn_volumes": null,
                                                   "selected_link_volumes": null,
                                                   "od_values": "mf3"
                                                   }
                                       }, "demand": "mf1"}], "background_traffic": null, "path_analysis": {"operator": "+", "selection_threshold": {"upper": 999999, "lower": -999999}, "turn_component": null, "path_to_od_composition": {"multiply_path_proportions_by": {"path_value": true, "analyzed_demand": false}, "considered_paths": "ALL"}, "link_component": "@z407"}, "performance_settings": {"number_of_processors": 8}, "cutoff_analysis": null, "type": "STANDARD_TRAFFIC_ASSIGNMENT", "stopping_criteria": {"normalized_gap": 0.0, "best_relative_gap": 0.0, "relative_gap": 0.0, "max_iterations": 100}}
    