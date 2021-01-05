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
Toll-Based Road Assignment

    Authors: Peter Kucirek, Eric Miller

    Latest revision by: lunaxi
    
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
    
    3.0.2 Re-coded XTMF-side of tool.
    
    3.1.0 Added feature to recognize '0' matrix as a scalar of 0 (XTMF side only)
    
    3.2.0 Upgraded to use SOLA traffic assignment (Emme 4.1 and newer). Other new features:
        - Print status to console (also to XTMF) whilst running. Includes the stopping criterion
        - All-or-nothing scenario manager doesn't copy over the transit strategy files.
        
    3.2.1 Removed a scaling factor being incorrectly applied to the Best Relative Gap

    3.3.0 Major change. Features:
        - No more all-or-nothing assignment.
        - Primary assignment now exports full cost (link costs + tolls)
        - Secondary assignment is only run if a toll matrix is chosen
        - Secondary assignment is identical to the primary, but outputs toll matrix
        - Secondary assignment no longer run in temporary scenario
        - Changed transit background calculation to include ttf>=3

    3.3.1 Added new assignment to calculate true travel time, not shortest path generalized cost.

    3.3.2 Updated to allow for multi-threaded matrix calcs in 4.2.1+

    3.3.3 Assignment now includes on-link operating costs in generalized costs (instead of only tolls)
        
    3.4.0 Add path analysis option 

'''

import inro.modeller as _m
import traceback as _traceback
import multiprocessing
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

@contextmanager
def blankManager(obj):
    try:
        yield obj
    finally:
        pass

class TollBasedRoadAssignment(_m.Tool()):
    
    version = '3.4.0'
    tool_run_msg = ""
    number_of_tasks = 5 # For progress reporting, enter the integer number of tasks here
    
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
    SOLAFlag = _m.Attribute(bool)

    LinkComponent = _m.Attribute(str)
    TurnComponent = _m.Attribute(str)
    OperatorForPathAnaysis = _m.Attribute(str)
    LowerBound = _m.Attribute(float)
    UpperBound = _m.Attribute(float)
    PathToODAggregation = _m.Attribute(str)
    AnalyzedDemandMatrix = _m.Attribute(str)
    ODValueResults = _m.Attribute(str)
    LinkVolResults = _m.Attribute(str)
    TurnVolResults = _m.Attribute(str)
    PathAnalysisFlag = _m.Attribute(bool)

    NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario
        
        mf10 = _MODELLER.emmebank.matrix('mf10')
        if mf10 is not None:
            self.DemandMatrix = mf10
        
        self.PeakHourFactor = 0.385
        self.LinkCost = 0.153
        self.TollWeight = 50
        self.Iterations = 80
        self.rGap = 0.1
        self.brGap = 0
        self.normGap = 0.05
        self.PerformanceFlag = False
        self.RunTitle = ""
        self.LinkTollAttributeId = "@toll"
        self.LinkComponent = "@sellk"
        self.TurnComponent = None
        self.OperatorForPathAnaysis = "+"
        self.LowerBound = None
        self.UpperBound = None
        self.PathToODAggregation = "ANALYZED"
        self.AnalyzedDemandMatrix = None
        self.LinkVolResults = -1
        self.TurnVolResults = -1

        if EMME_VERSION >= (4,1):
            self.SOLAFlag = True
        else:
            self.SOLAFlag = False

        self.PathAnalysisFlag = False

        self.NumberOfProcessors = multiprocessing.cpu_count()

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
                         link attributes, 1 extra function parameter (el1), 1 full matrix, 1 scenario.",
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
        
        keyval = {}
        print self.Scenario.id
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
                        title='Tolls matrix',
                        allow_none=True)
                
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
        
        pb.add_header("CONVERGENCE CRITERIA")
        
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
        
        if EMME_VERSION >= (4,1):
            pb.add_checkbox(tool_attribute_name= 'SOLAFlag',
                            label= "Use SOLA traffic assignment?")
        
        # Path Analysis (Optional)

        pb.add_header("Path Analysis (Optional)")
        
        pb.add_checkbox(tool_attribute_name= 'PathAnalysisFlag',
                        label= "Perform Path Analysis for this class?")

        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkComponent',
                        keyvalues=keyval,
                        title="Link Component")

            keyval_turn = {}
            for att in self.Scenario.extra_attributes():
                if not att.type == 'TURN': continue
                label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
                keyval_turn[att.name] = label
            
            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='TurnComponent',
                              keyvalues=keyval_turn,
                              title="Turn Component")

            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='OperatorForPathAnaysis',
                              keyvalues={'+':'+','-':'-','*':'*','/':'/','.max.':'max','.min.':'min'},
                              title="Operator")

            t.new_row()
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='LowerBound',
                                size=12,
                                title="Selection Threshold: Lower Bound")
            t.new_row()
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='UpperBound',
                                size=12,
                                title="Selection Threshold: Upper Bound")
            
            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='PathToODAggregation',
                              keyvalues={'PATH':'Path','SELECTED':'Selected path','WEIGHTED':'Weighted selected path','ANALYZED':'Analyzed demand on selected paths'},
                              title="Path to OD aggregation",
                              note="<b>Path:</b> consider all paths, multiplied by path value. This gives the proportion-weighted average value of the path values, for all the paths used in the master assignment. \
                              <br><br><b>Selected path:</b> consider only selected paths, multiplied by path value. This gives the sum, for selected paths only, of the path value multiplied by the path proportion. \
                              <br><br><b>Weighted selected path:</b> consider only selected paths, multiplied by analyzed demand and path value. This gives the sum, for selected paths, of the proportion-weighted path value multiplied by the analyzed demand assigned to the path. \
                              <br><br><b>Analyzed demand on selected paths:</b> consider only selected paths, multiplied by analyzed demand.")

            t.new_row()
            with t.table_cell():
                pb.add_select_matrix(tool_attribute_name="AnalyzedDemandMatrix",
                                     title="Analzyed Demand",
                                     filter="FULL", note="By default this is the same as the demand used in the assignment (Select 'None').",
                                     allow_none=True)

            t.new_row()
            with t.table_cell():
                pb.add_select_new_matrix(tool_attribute_name="ODValueResults", 
                        overwrite_existing=True,
                        matrix_type='FULL',
                        note='Create or override',
                        title='OD value results')

            linkKV = [(-1, 'No attribute')]
            turnKV = [(-1, 'No attribute')]
            for exatt in self.Scenario.extra_attributes():
                if exatt.type == 'LINK':
                    link_text = "%s - %s" %(exatt.id, exatt.description)
                    linkKV.append((exatt.id, link_text))
                elif exatt.type == 'TURN':
                    turn_text = "%s - %s" %(exatt.id, exatt.description)
                    turnKV.append((exatt.id, turn_text))
            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkVolResults',
                        keyvalues=linkKV,
                        title="Selected link volumes")
            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='TurnVolResults',
                        keyvalues=turnKV,
                        title="Selected turn volumes")

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

            $("#LinkVolResults")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#LinkVolResults");
            $("#LinkVolResults").trigger('change');

            $("#TurnVolResults")
                .empty()
                .append(tool._GetSelectTurnAttributeOptionsHTML())
            inro.modeller.page.preload("#TurnVolResults");
            $("#TurnVolResults").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        
        if self.DemandMatrix is None: raise NullPointerException("Demand matrix not specified")
        if self.LinkTollAttributeId is None: raise NullPointerException("Link toll attribute not specified")
        if self.PeakHourFactor is None: raise NullPointerException("Peak hour factor not specified")
        if self.LinkCost is None: raise NullPointerException("Link unit cost not specified")
        if self.TollWeight is None: raise NullPointerException("Toll perception not specified")
        if self.Iterations is None: raise NullPointerException("Max iterations not specified")
        if self.rGap is None: raise NullPointerException("Relative gap not specified")
        if self.brGap is None: raise NullPointerException("Best relative gap not specified")
        if self.normGap is None: raise NullPointerException("Normalized gap not specified")
        
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixNumber, TimesMatrixId, CostMatrixId, TollsMatrixId,
                 PeakHourFactor, LinkCost, TollWeight, Iterations, rGap, brGap, normGap, PerformanceFlag,
                 RunTitle, LinkTollAttributeId, SOLAFlag, PathAnalysisFlag, LinkComponent, TurnComponent, OperatorForPathAnaysis, 
                 LowerBound, UpperBound, PathToODAggregation, AnalyzedDemandMatrix, ODValueResults, LinkVolResults, TurnVolResults):
        
        #---1 Set up Scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        if xtmf_DemandMatrixNumber == 0:
            manager = _util.tempMatrixMANAGER(matrix_type= 'SCALAR')
        else:
            demandMatrix = _MODELLER.emmebank.matrix("mf%s" %xtmf_DemandMatrixNumber)
            if demandMatrix is None:
                raise Exception("Matrix %s was not found!" %xtmf_DemandMatrixNumber)
            manager = blankManager(demandMatrix)
        
        #---2. Pass in remaining args
        self.TimesMatrixId = TimesMatrixId
        self.CostMatrixId = CostMatrixId
        if TollsMatrixId == 'mf0':
            self.TollsMatrixId = None
        else:
            self.TollsMatrixId = TollsMatrixId
        self.PeakHourFactor = PeakHourFactor
        self.LinkCost = LinkCost
        self.TollWeight = TollWeight
        self.Iterations = Iterations
        self.rGap = rGap
        self.brGap = brGap
        self.normGap = normGap

        self.RunTitle = RunTitle[:25]
        self.LinkTollAttributeId = LinkTollAttributeId
        
        if EMME_VERSION >= (4,1):
            self.SOLAFlag = SOLAFlag
        else:
            self.SOLAFlag = False
        
        if self.PathAnalysisFlag == True:
            self.LinkComponent = LinkComponent
            self.TurnComponent = TurnComponent
            self.OperatorForPathAnaysis = OperatorForPathAnaysis
            self.LowerBound = LowerBound
            self.UpperBound = UpperBound
            self.PathToODAggregation = PathToODAggregation
            self.AnalyzedDemandMatrix = AnalyzedDemandMatrix 
            self.ODValueResults = ODValueResults
            self.LinkVolResults = LinkVolResults
            self.TurnVolResults = TurnVolResults

        #---3. Run
        try:
            with manager as self.DemandMatrix:
                print "Starting auto assignment."
                self._execute()
                print "Road assignment complete."  
        except Exception as e:
            raise Exception(_util.formatReverseStack())
    
    ##########################################################################################################    
    
    
    def _execute(self):
        
        with _m.logbook_trace(name="%s (%s v%s)" %(self.RunTitle, self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
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
            
            self._tracker.startProcess(5)
            
            self._initOutputMatrices()
            self._tracker.completeSubtask()
            
            with nested(self._costAttributeMANAGER(),
                        _util.tempMatrixMANAGER(description="Peak hour matrix"),
                        self._transitTrafficAttributeMANAGER(),
                        self._timeAttributeMANAGER()) \
                    as (costAttribute, peakHourMatrix, bgTransitAttribute, timeAttribute): #bgTransitAttribute is None
                
                with _m.logbook_trace("Calculating transit background traffic"):
                    networkCalculationTool(self._getTransitBGSpec(), scenario=self.Scenario)
                    self._tracker.completeSubtask()
                    
                with _m.logbook_trace("Calculating link costs"):
                    networkCalculationTool(self._getLinkCostCalcSpec(costAttribute.id), scenario=self.Scenario)
                    self._tracker.completeSubtask()
                    
                with _m.logbook_trace("Calculating peak hour matrix"):
                    if EMME_VERSION >= (4,2,1):
                        matrixCalcTool(self._getPeakHourSpec(peakHourMatrix.id), num_processors=self.NumberOfProcessors, scenario=self.Scenario)
                    else:
                        matrixCalcTool(self._getPeakHourSpec(peakHourMatrix.id),scenario=self.Scenario)
                    self._tracker.completeSubtask()
                    
                
                appliedTollFactor = self._calculateAppliedTollFactor()
                self._tracker.completeTask()
                
                with _m.logbook_trace("Running primary road assignment."):
                    
                    if self.SOLAFlag:
                        spec = self._getPrimarySOLASpec(peakHourMatrix.id, costAttribute.id, appliedTollFactor)
                    else:
                        spec = self._getPrimaryRoadAssignmentSpec(peakHourMatrix.id, costAttribute.id, appliedTollFactor)
                        
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
                    
                    print "Primary assignment complete at %s iterations." %number
                    print "Stopping criterion was %s with a value of %s." %(stoppingCriterion, val)

                self._tracker.startProcess(1)
                with _m.logbook_trace("Secondary assignment to recover true travel times:"):
                        
                    with _m.logbook_trace("Copying auto times into @ltime"):
                            networkCalculationTool(self._getSaveAutoTimesSpec(timeAttribute.id), scenario=self.Scenario)
                            self._tracker.completeSubtask
                        
                    with _m.logbook_trace("Running secondary assignment"):
                        if self.SOLAFlag:
                            spec = self._getSecondarySOLASpec(peakHourMatrix.id, timeAttribute.id, appliedTollFactor, costAttribute.id)
                        else:
                            spec = self._getSecondaryRoadAssignmentSpec(peakHourMatrix.id, timeAttribute.id, appliedTollFactor, costAttribute.id)
                                
                        self._tracker.runTool(trafficAssignmentTool,
                                                spec, scenario=self.Scenario)                  
                    
                self._tracker.startProcess(1)
                if not (self.TollsMatrixId == "null" or self.TollsMatrixId is None):
                    self._tracker.completeSubtask
                    
                    with _m.logbook_trace("Tertiary assignment to recover toll costs separately:"):
                        
                        #with _m.logbook_trace("Copying auto times into UL2"):
                        #    networkCalculationTool(self._getSaveAutoTimesSpec(appliedTollFactor), scenario=allOrNothingScenario)
                        #    self._tracker.completeSubtask
                        
                        #with _m.logbook_trace("Preparing function 98 for assignment"):
                        #    self._modifyFunctionForAoNAssignment()
                        #    networkCalculationTool(self._getChangeLinkVDFto98Spec(), scenario=allOrNothingScenario)
                        #    self._tracker.completeSubtask
                        
                        self._tracker.completeTask()
                        
                        with _m.logbook_trace("Running tertiary assignment"):
                            if self.SOLAFlag:
                                spec = self._getTertiarySOLASpec(peakHourMatrix.id, appliedTollFactor, costAttribute.id)
                            else:
                                spec = self._getTertiaryAssignmentSpec(peakHourMatrix.id, appliedTollFactor, costAttribute.id)
                                
                            self._tracker.runTool(trafficAssignmentTool,
                                                  spec, scenario=self.Scenario)   

                self._tracker.startProcess(1)
                if self.PathAnalysisFlag == True :
                    with _m.logbook_trace("Running traffic assignment for path analysis"):
                            if self.SOLAFlag:
                                spec = self._getSOLASpecForPathAnalysis(peakHourMatrix.id, costAttribute.id, appliedTollFactor, self.LinkComponent,self.TurnComponent,self.OperatorForPathAnaysis,self.LowerBound,self.UpperBound,self.PathToODAggregation,self.AnalyzedDemandMatrix,self.ODValueResults,self.LinkVolResults,self.TurnVolResults)
                            else:
                                spec = self._getAssignmentSpecForPathAnalysis(peakHourMatrix.id, costAttribute.id, appliedTollFactor, self.LinkComponent,self.TurnComponent,self.OperatorForPathAnaysis,self.LowerBound,self.UpperBound,self.PathToODAggregation,self.AnalyzedDemandMatrix,self.ODValueResults,self.LinkVolResults,self.TurnVolResults)
                                
                            self._tracker.runTool(trafficAssignmentTool,
                                                  spec, scenario=self.Scenario) 

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _AoNScenarioMANAGER(self):
        #Code here is executed upon entry
        
        tempScenarioNumber = _util.getAvailableScenarioNumber()
        
        if tempScenarioNumber is None:
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
        if costAttribute is None:
            #@lkcst hasn't been defined
            _m.logbook_write("Creating temporary link cost attribute '@lkcst'.")
            costAttribute = self.Scenario.create_extra_attribute('LINK', '@lkcst', default_value=0)
            attributeCreated = True
            
        elif self.Scenario.extra_attribute('@lkcst').type != 'LINK':
            #for some reason '@lkcst' exists, but is not a link attribute
            _m.logbook_write("Creating temporary link cost attribute '@lcst2'.")
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
    def _timeAttributeMANAGER(self):
        #Code here is executed upon entry
        
        attributeCreated = False
        
        timeAttribute = self.Scenario.extra_attribute('@ltime')
        if timeAttribute is None:
            #@ltime hasn't been defined
            _m.logbook_write("Creating temporary link cost attribute '@ltime'.")
            timeAttribute = self.Scenario.create_extra_attribute('LINK', '@ltime', default_value=0)
            attributeCreated = True
            
        elif self.Scenario.extra_attribute('@ltime').type != 'LINK':
            #for some reason '@ltime' exists, but is not a link attribute
            _m.logbook_write("Creating temporary link cost attribute '@ltim2'.")
            timeAttribute = self.Scenario.create_extra_attribute('LINK', '@ltim2', default_value=0)
            attributeCreated = True
        
        if not attributeCreated:
            timeAttribute.initialize()
            _m.logbook_write("Initialized link cost attribute to 0.")
        
        try:
            yield timeAttribute
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            if attributeCreated: 
                _m.logbook_write("Deleting temporary link cost attribute.")
                self.Scenario.delete_extra_attribute(timeAttribute.id)
                 # Delete the extra cost attribute only if it didn't exist before.    
    @contextmanager
    def _transitTrafficAttributeMANAGER(self):
        
        attributeCreated = False
        bgTrafficAttribute = self.Scenario.extra_attribute('@tvph')
        
        if bgTrafficAttribute is None:
            bgTrafficAttribute = self.Scenario.create_extra_attribute('LINK','@tvph', 0)
            attributeCreated = True
            _m.logbook_write("Created extra attribute '@tvph'")
        else:
            bgTrafficAttribute.initialize(0)
            _m.logbook_write("Initialized existing extra attribute '@tvph' to 0.")
        
        if EMME_VERSION >= 4:
            extraParameterTool = _MODELLER.tool('inro.emme.traffic_assignment.set_extra_function_parameters')
        else:
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
                "expression": "(60 / hdw) * (vauteq) * (ttf >= 3)",
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
            if not (self.TollsMatrixId == "null" or self.TollsMatrixId is None):
                _util.initializeMatrix(self.TollsMatrixId, name='atoll', description='AUTO TOLL: %s' %self.RunTitle)
    
    def _getLinkCostCalcSpec(self, costAttributeId):
        return {
                "result": costAttributeId,
                "expression": "length * %f + %s" %(self.LinkCost, self.LinkTollAttributeId),
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
    
    def _getPrimarySOLASpec(self, peakHourMatrixId, costAttributeId, appliedTollFactor):
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
                            "link_costs": costAttributeId,
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
                    "max_iterations": self.Iterations,
                    "relative_gap": self.rGap,
                    "best_relative_gap": self.brGap,
                    "normalized_gap": self.normGap
                }
            }
        
          
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
                                                  "link_costs": costAttributeId,
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
                                                      "od_values": self.CostMatrixId,
                                                      "selected_link_volumes": None,
                                                      "selected_turn_volumes": None
                                                      }
                                          },
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
                                      "max_iterations": self.Iterations,
                                      "best_relative_gap": self.brGap,
                                      "relative_gap": self.rGap,
                                      "normalized_gap": self.normGap
                                      }
                }
    
    def _getSecondarySOLASpec(self, peakHourMatrixId, timeAttribute, appliedTollFactor, costAttributeId):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
        
        modeId = _util.getScenarioModes(self.Scenario, ['AUTO'])[0][0]
        #Returns a list of tuples. Emme guarantees that there is always
        #one auto mode.

        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 2, 1)

        return {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes": [
                    {
                        "mode": modeId,
                        "demand": peakHourMatrixId,
                        "generalized_cost": {
                            "link_costs": costAttributeId,
                            "perception_factor": appliedTollFactor
                        },
                        "results": {
                            "link_volumes": None,
                            "turn_volumes": None,
                            "od_travel_times": {
                                "shortest_paths": None
                            }
                        },
                        "path_analysis": {
                            "link_component": timeAttribute,
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
                                "od_values": self.TimesMatrixId,
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
        
          
    def _getSecondaryRoadAssignmentSpec(self, peakHourMatrixId, timeAttribute, appliedTollFactor, costAttributeId):
        
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
                                                  "link_costs": costAttributeId,
                                                  "perception_factor": appliedTollFactor
                                                  },
                             "results": {
                                         "link_volumes": None,
                                         "turn_volumes": None,
                                         "od_travel_times": {
                                                             "shortest_paths": None
                                                             }
                                         },
                             "analysis": {
                                          "analyzed_demand": peakHourMatrixId,
                                          "results": {
                                                      "od_values": self.TimesMatrixId,
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
                                  "link_component": timeAttribute,
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
    

    def _getSaveAutoTimesSpec(self, timeAttribute):
        return {
                "result": timeAttribute,
                "expression": "timau",
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    #def _modifyFunctionForAoNAssignment(self):
    #    allOrNothingFunc = _MODELLER.emmebank.function('fd98')
    #    if allOrNothingFunc is None:
    #        allOrNothingFunc = _MODELLER.emmebank.create_function('fd98', 'ul2')
    #    else:
    #        allOrNothingFunc.expression = 'ul2'
        
    #def _getChangeLinkVDFto98Spec(self):
    #    return {
    #            "result": "vdf",
    #            "expression": "98",
    #            "aggregation": None,
    #            "selections": {
    #                           "link": "all"
    #                           },
    #            "type": "NETWORK_CALCULATION"
    #            }
    
    def _getTertiarySOLASpec(self, peakHourMatrixId, appliedTollFactor, costAttributeId):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
            
        modeId = _util.getScenarioModes(self.Scenario, ['AUTO'])[0][0]
        #Returns a list of tuples. Emme guarantees that there is always
        #one auto mode.

        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 2, 1)

        return {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes": [
                    {
                        "mode": modeId,
                        "demand": peakHourMatrixId,
                        "generalized_cost": {
                            "link_costs": costAttributeId,
                            "perception_factor": appliedTollFactor
                            },
                        "results": {
                            "link_volumes": None,
                            "turn_volumes": None,
                            "od_travel_times": {
                                "shortest_paths": None
                            }
                        },
                        "path_analysis": {
                            "link_component": self.LinkTollAttributeId,
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
                    "best_relative_gap": self.brGap,
                    "relative_gap": self.rGap,
                    "normalized_gap": self.normGap
                }
            }
    
      
    def _getTertiaryAssignmentSpec(self, peakHourMatrixId, appliedTollFactor, costAttributeId):
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
                                                    "link_costs": costAttributeId,
                                                    "perception_factor": appliedTollFactor
                                                    },
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
                                                "best_relative_gap": self.brGap,
                                                "relative_gap": self.rGap,
                                                "normalized_gap": self.normGap
                                               }
                         }
    
    def _getSOLASpecForPathAnalysis(self, peakHourMatrixId, costAttributeId, appliedTollFactor,LinkComponent,TurnComponent,OperatorForPathAnaysis,LowerBound,UpperBound,PathToODAggregation,AnalyzedDemandMatrix,ODValueResults,LinkVolResults,TurnVolResults):
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 1, 1)
        
        modeId = _util.getScenarioModes(self.Scenario, ['AUTO'])[0][0]
        #Returns a list of tuples. Emme guarantees that there is always
        #one auto mode.

        if self.PathToODAggregation == 'PATH':
            considered_path = "ALL"
            analyzed_demand_flag = False
            path_value_flag = True
        elif self.PathToODAggregation == 'SELECTED':
            considered_path = "SELECTED"
            analyzed_demand_flag = False
            path_value_flag = True
        elif self.PathToODAggregation == 'WEIGHTED':
            considered_path = "SELECTED"
            analyzed_demand_flag = True
            path_value_flag = True
        else:
            considered_path = "SELECTED"
            analyzed_demand_flag = True
            path_value_flag = False
        
        if self.AnalyzedDemandMatrix == None:
            AnalyzedDemandMatrixID = peakHourMatrixId
        else:
            AnalyzedDemandMatrixID = AnalyzedDemandMatrix

        return {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes": [
                    {
                        "mode": modeId,
                        "demand": peakHourMatrixId,
                        "generalized_cost": {
                            "link_costs": costAttributeId,
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
                                 "link_component": LinkComponent,
                                 "turn_component": TurnComponent,
                                 "operator": OperatorForPathAnaysis,
                                 "selection_threshold": {
                                     "lower": LowerBound,
                                     "upper": UpperBound
                                     },
                                 "path_to_od_composition": {
                                     "considered_paths": considered_path,
                                     "multiply_path_proportions_by": {
                                         "analyzed_demand": analyzed_demand_flag,
                                         "path_value": path_value_flag
                                         }
                                     },
                                 "analyzed_demand": AnalyzedDemandMatrixID,
                                 "results": {
                                     "od_values": ODValueResults,
                                     "selected_link_volumes": LinkVolResults,
                                     "selected_turn_volumes": TurnVolResults
                                     }
                                 },
                        "cutoff_analysis": None,
                        "traversal_analysis": None
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

    def _getAssignmentSpecForPathAnalysis(self, peakHourMatrixId, costAttributeId, appliedTollFactor, LinkComponent,TurnComponent,OperatorForPathAnaysis,LowerBound,UpperBound,PathToODAggregation,AnalyzedDemandMatrix,ODValueResults,LinkVolResults,TurnVolResults):
        
        if self.PerformanceFlag:
            numberOfPocessors = multiprocessing.cpu_count()
        else:
            numberOfPocessors = max(multiprocessing.cpu_count() - 2, 1)

        if self.PathToODAggregation == 'PATH':
            considered_path = "ALL"
            analyzed_demand_flag = False
            path_value_flag = True
        elif self.PathToODAggregation == 'SELECTED':
            considered_path = "SELECTED"
            analyzed_demand_flag = False
            path_value_flag = True
        elif self.PathToODAggregation == 'WEIGHTED':
            considered_path = "SELECTED"
            analyzed_demand_flag = True
            path_value_flag = True
        else:
            considered_path = "SELECTED"
            analyzed_demand_flag = True
            path_value_flag = False
        
        if self.AnalyzedDemandMatrix == None:
            AnalyzedDemandMatrixID = peakHourMatrixId
        else:
            AnalyzedDemandMatrixID = AnalyzedDemandMatrix
            
        return {
                "type": "STANDARD_TRAFFIC_ASSIGNMENT",
                "classes": [{
                             "mode": "c",
                             "demand": peakHourMatrixId,
                             "generalized_cost": {
                                                  "link_costs": costAttributeId,
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
                                 "analyzed_demand": AnalyzedDemandMatrixID,
                                 "results": {
                                     "od_values": ODValueResults,
                                     "selected_link_volumes": LinkVolResults,
                                     "selected_turn_volumes": TurnVolResults
                                     }
                                 }
                             }],
                "performance_settings": {
                                         "number_of_processors": numberOfPocessors
                                         },
                "background_traffic": None,
                "path_analysis": {
                                  "link_component": LinkComponent,
                                  "turn_component": TurnComponent,
                                  "operator": OperatorForPathAnaysis,
                                  "selection_threshold": {
                                                          "lower": LowerBound,
                                                          "upper": UpperBound
                                                          },
                                  "path_to_od_composition": {
                                                             "considered_paths": considered_path,
                                                             "multiply_path_proportions_by": {
                                                                                              "analyzed_demand": analyzed_demand_flag,
                                                                                              "path_value": path_value_flag
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
    
    @_m.method(return_type=unicode)
    def _GetSelectTurnAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            if not att.type == 'TURN': continue
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)