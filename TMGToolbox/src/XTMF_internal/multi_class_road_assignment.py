from __future__ import print_function

"""
    Copyright 2015-2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
"""

"""
#---METADATA---------------------
Toll-Based Road Assignment

    Authors: David King, Eric Miller, James Vaughan

    Latest revision by: JamesVaughan
    
    Executes a multi-class road assignment which allows for the generalized penalty of road tolls.
    
    V 1.0.0

    V 1.1.0 Added link volume attributes for increased resolution of analysis.

    V 1.1.1 Updated to allow for multi-threaded matrix calcs in 4.2.1+

    V 1.1.2 Fixed for compatibility with Python3
        
"""


import inro.modeller as _m
import traceback as _traceback
import multiprocessing
from contextlib import contextmanager

_MODELLER = _m.Modeller()  # Instantiate Modeller once.
_util = _MODELLER.module("tmg.common.utilities")
EMME_VERSION = _util.getEmmeVersion(tuple)
# import six library for python2 to python3 conversion
import six

# initialize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################


@contextmanager
def blankManager(obj):
    try:
        yield obj
    finally:
        pass


class MultiClassRoadAssignment(_m.Tool()):

    version = "1.1.1"
    tool_run_msg = ""
    # For progress reporting, enter the integer number of tasks here
    number_of_tasks = 4

    # Tool Input Parameters
    #    Only those parameters necessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get initialized during construction (__init__)

    # ---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    # DemandMatrix = _m.Attribute(_m.InstanceType) #remove?
    LinkTollAttributeId = _m.Attribute(str)

    TimesMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    TollsMatrixId = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    # Must be passed as a string, with modes comma separated (e.g. 'a,b,c') cov => ['a','b','c']
    Mode_List = _m.Attribute(str)
    # Must be passed as a string, with demand matrices comma separated (e.g. 'a,b,c') cov => ['a','b','c']
    xtmf_Demand_String = _m.Attribute(str)
    # The Demand Matrix List
    Demand_List = _m.Attribute(str)
    PeakHourFactor = _m.Attribute(float)
    LinkCost = _m.Attribute(str)
    TollWeight = _m.Attribute(str)
    Iterations = _m.Attribute(int)
    rGap = _m.Attribute(float)
    brGap = _m.Attribute(float)
    normGap = _m.Attribute(float)
    PerformanceFlag = _m.Attribute(bool)
    xtmf_NameString = _m.Attribute(str)
    ResultAttributes = _m.Attribute(str)
    xtmf_AnalysisAttributes = _m.Attribute(str)
    xtmf_AnalysisAttributesMatrixId = _m.Attribute(str)
    xtmf_AnalysisSelectedLinkVolumes = _m.Attribute(str)
    xtmf_AggregationOperator = _m.Attribute(str)
    xtmf_LowerBound = _m.Attribute(str)
    xtmf_UpperBound = _m.Attribute(str)
    xtmf_PathSelection = _m.Attribute(str)
    xtmf_MultiplyPathPropByDemand = _m.Attribute(str)
    xtmf_MultiplyPathPropByValue = _m.Attribute(str)
    xtmf_BackgroundTransit = _m.Attribute(str)
    OnRoadTTFRanges = _m.Attribute(str)
    NumberOfProcessors = _m.Attribute(int)

    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)

        self.Scenario = _MODELLER.scenario

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

        self.NumberOfProcessors = multiprocessing.cpu_count()
        self.OnRoadTTFRanges = "3-128"
        self._RoadAssignmentUtil = _util.RoadAssignmentUtil()

    def page(self):
        pb = _m.ToolPageBuilder(
            self,
            title="Multi-Class Road Assignment",
            description="Cannot be called from Modeller.",
            runnable=False,
            branding_text="XTMF",
        )

        return pb.render()

    def __call__(
        self,
        xtmf_ScenarioNumber,
        Mode_List,
        xtmf_Demand_String,
        TimesMatrixId,
        CostMatrixId,
        TollsMatrixId,
        PeakHourFactor,
        LinkCost,
        TollWeight,
        Iterations,
        rGap,
        brGap,
        normGap,
        PerformanceFlag,
        RunTitle,
        LinkTollAttributeId,
        xtmf_NameString,
        ResultAttributes,
        xtmf_AnalysisAttributes,
        xtmf_AnalysisAttributesMatrixId,
        xtmf_AnalysisSelectedLinkVolumes,
        xtmf_AggregationOperator,
        xtmf_LowerBound,
        xtmf_UpperBound,
        xtmf_PathSelection,
        xtmf_MultiplyPathPropByDemand,
        xtmf_MultiplyPathPropByValue,
        xtmf_BackgroundTransit,
        OnRoadTTFRanges,
    ):
        # ---1 Set up Scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if self.Scenario is None:
            raise Exception("Scenario %s was not found!" % xtmf_ScenarioNumber)
        self.OnRoadTTFRanges = OnRoadTTFRanges
        self.on_road_ttfs = self._RoadAssignmentUtil.convert_to_ranges(self.OnRoadTTFRanges)
        #:List will be passed as follows: xtmf_Demand_String = "mf10,mf11,mf12", Will be parsed into a list
        self.Demand_List = xtmf_Demand_String.split(",")
        # Splitting the Time, Cost and Toll string into Lists, and Modes for denoting results
        self.ResultAttributes = ResultAttributes
        self.TimesMatrixId = TimesMatrixId.split(",")
        self.CostMatrixId = CostMatrixId.split(",")
        self.TollsMatrixId = TollsMatrixId.split(",")
        self.Mode_List_Split = Mode_List.split(",")
        self.ClassNames = [x for x in xtmf_NameString.split(",")]
        self.TollWeight = [float(x) for x in TollWeight.split(",")]
        self.LinkCost = [float(x) for x in LinkCost.split(",")]
        self.LinkTollAttributeId = [x for x in LinkTollAttributeId.split(",")]
        AnalysisAttributes = [x for x in xtmf_AnalysisAttributes.split("|")]
        AnalysisAttributesMatrixId = [x for x in xtmf_AnalysisAttributesMatrixId.split("|")]
        AnalysisSelectedLinkVolumes = [x for x in xtmf_AnalysisSelectedLinkVolumes.split("|")]
        operators = [x for x in xtmf_AggregationOperator.split("|")]
        lowerBounds = [x for x in xtmf_LowerBound.split("|")]
        upperBounds = [x for x in xtmf_UpperBound.split("|")]
        selectors = [x for x in xtmf_PathSelection.split("|")]
        multiplyPathDemand = [x for x in xtmf_MultiplyPathPropByDemand.split("|")]
        mulitplyPathValue = [x for x in xtmf_MultiplyPathPropByValue.split("|")]
        self.ClassAnalysisAttributes = []
        self.ClassAnalysisAttributesMatrix = []
        self.ClassAnalysisSelectedLinkVolumes = []
        self.ClassAnalysisOperators = []
        self.ClassAnalysisLowerBounds = []
        self.ClassAnalysisUpperBounds = []
        self.ClassAnalysisSelectors = []
        self.ClassAnalysisMultiplyPathDemand = []
        self.ClassAnalysisMultiplyPathValue = []
        operatorList = ["+", "-", "*", "/", "%", ".max.", ".min."]
        for i in range(len(self.Demand_List)):
            self.ClassAnalysisAttributes.append([x for x in AnalysisAttributes[i].split(",")])
            self.ClassAnalysisAttributesMatrix.append([x for x in AnalysisAttributesMatrixId[i].split(",")])
            self.ClassAnalysisSelectedLinkVolumes.append([x for x in AnalysisSelectedLinkVolumes[i].split(",")])
            self.ClassAnalysisOperators.append([x for x in operators[i].split(",")])
            self.ClassAnalysisLowerBounds.append([x for x in lowerBounds[i].split(",")])
            self.ClassAnalysisUpperBounds.append([x for x in upperBounds[i].split(",")])
            self.ClassAnalysisSelectors.append([x for x in selectors[i].split(",")])
            self.ClassAnalysisMultiplyPathDemand.append([x for x in multiplyPathDemand[i].split(",")])
            self.ClassAnalysisMultiplyPathValue.append([x for x in mulitplyPathValue[i].split(",")])
            for j in range(len(self.ClassAnalysisAttributes[i])):
                if self.ClassAnalysisAttributes[i][j] == "":
                    # make the blank attributes None for better use in spec
                    self.ClassAnalysisAttributes[i][j] = None
                if self.ClassAnalysisAttributesMatrix[i][j] == "mf0" or self.ClassAnalysisAttributesMatrix[i][j] == "":
                    # make mf0 matrices None for better use in spec
                    self.ClassAnalysisAttributesMatrix[i][j] = None
                if self.ClassAnalysisSelectedLinkVolumes[i][j] == "":
                    # make mf0 matrices None for better use in spec
                    self.ClassAnalysisSelectedLinkVolumes[i][j] = None
                try:
                    self.ClassAnalysisLowerBounds[i][j] = float(self.ClassAnalysisLowerBounds[i][j])
                    self.ClassAnalysisUpperBounds[i][j] = float(self.ClassAnalysisUpperBounds[i][j])
                except:
                    if self.ClassAnalysisLowerBounds[i][j].lower() == "none" or self.ClassAnalysisLowerBounds[i][j].lower() == "":
                        self.ClassAnalysisLowerBounds[i][j] = None
                    else:
                        raise Exception("Lower bound not specified correct for attribute  %s" % self.ClassAnalysisAttributes[i][j])
                    if self.ClassAnalysisUpperBounds[i][j].lower() == "none" or self.ClassAnalysisUpperBounds[i][j].lower() == "":
                        self.ClassAnalysisUpperBounds[i][j] = None
                    else:
                        raise Exception("Upper bound not specified correct for attribute  %s" % self.ClassAnalysisAttributes[i][j])
                if self.ClassAnalysisSelectors[i][j].lower() == "all":
                    self.ClassAnalysisSelectors[i][j] = "ALL"
                elif self.ClassAnalysisSelectors[i][j].lower() == "selected":
                    self.ClassAnalysisSelectors[i][j] = "SELECTED"
                else:
                    self.ClassAnalysisSelectors[i][j] = None
                if self.ClassAnalysisOperators[i][j] not in operatorList:
                    if self.ClassAnalysisOperators[i][j].lower() == "max":
                        self.ClassAnalysisOperators[i][j] = ".max."
                    elif self.ClassAnalysisOperators[i][j].lower() == "min":
                        self.ClassAnalysisOperators[i][j] = ".min."
                    elif self.ClassAnalysisOperators[i][j].lower() == "none" or self.ClassAnalysisOperators[i][j].strip(" ") == "":
                        self.ClassAnalysisOperators[i][j] = None
                    else:
                        raise Exception("The Path operator for the %s attribute is not specified correctly. It needs to be a binary operator" % self.ClassAnalysisAttributes[i][j])
                if str(self.ClassAnalysisMultiplyPathDemand[i][j]).lower() == "true":
                    self.ClassAnalysisMultiplyPathDemand[i][j] = True
                elif str(self.ClassAnalysisMultiplyPathDemand[i][j]).lower() == "false":
                    self.ClassAnalysisMultiplyPathDemand[i][j] = False
                else:
                    self.ClassAnalysisMultiplyPathDemand[i][j] = None

                if str(self.ClassAnalysisMultiplyPathValue[i][j]).lower() == "true":
                    self.ClassAnalysisMultiplyPathValue[i][j] = True
                elif str(self.ClassAnalysisMultiplyPathValue[i][j]).lower() == "false":
                    self.ClassAnalysisMultiplyPathValue[i][j] = False
                else:
                    self.ClassAnalysisMultiplyPathValue[i][j] = None
        self.DemandMatrixList = []
        for i in range(0, len(self.Demand_List)):
            demandMatrix = self.Demand_List[i]
            if _MODELLER.emmebank.matrix(demandMatrix) is None:
                if str(demandMatrix).lower() == "mf0":
                    dm = _util.initializeMatrix(matrix_type="FULL")
                    demandMatrix = dm.id
                    print("Assigning a Zero Demand matrix for class '%s' on scenario %d" % (str(self.ClassNames[i]), int(self.Scenario.number)))
                    self.Demand_List[i] = dm.id
                    self.DemandMatrixList.append(_MODELLER.emmebank.matrix(demandMatrix))
                else:
                    raise Exception("Matrix %s was not found!" % demandMatrix)
            else:
                self.DemandMatrixList.append(_MODELLER.emmebank.matrix(demandMatrix))

        # ---2. Pass in remaining args
        self.PeakHourFactor = PeakHourFactor
        self.Iterations = Iterations
        self.rGap = rGap
        self.brGap = brGap
        self.normGap = normGap
        self.RunTitle = RunTitle[:25]
        self.PerformanceFlag = PerformanceFlag
        if str(xtmf_BackgroundTransit).lower() == "true":
            self.BackgroundTransit = True
        else:
            self.BackgroundTransit = False
        # ---3. Run
        try:
            print("Starting assignment.")
            self._execute()
            print("Assignment complete.")
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    ##########################################################################################################

    def _execute(self):

        with _m.logbook_trace(
            name="%s (%s v%s)" % (self.RunTitle, self.__class__.__name__, self.version),
            attributes=self._RoadAssignmentUtil._getAtts(self.Scenario, self.RunTitle, self.TimesMatrixId, self.PeakHourFactor, self.LinkCost, self.Iterations, self.__MODELLER_NAMESPACE__),
        ):
            self._tracker.reset()
            matrixCalcTool = _MODELLER.tool("inro.emme.matrix_calculation.matrix_calculator")
            networkCalculationTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator")
            trafficAssignmentTool = _MODELLER.tool("inro.emme.traffic_assignment.sola_traffic_assignment")
            self._tracker.startProcess(5)

            with self._RoadAssignmentUtil._initOutputMatrices(self.Demand_List, self.CostMatrixId, self.ClassNames, self.TollsMatrixId, self.TimesMatrixId, self.ClassAnalysisAttributesMatrix, self.ClassAnalysisAttributes) as OutputMatrices:
                self._tracker.completeSubtask()

                with self._RoadAssignmentUtil._costAttributeMANAGER(self.Scenario, self.Demand_List) as costAttribute, self._RoadAssignmentUtil._transitTrafficAttributeMANAGER(
                    self.Scenario,
                    EMME_VERSION,
                    self.BackgroundTransit,
                ) as bgTransitAttribute, self._RoadAssignmentUtil._timeAttributeMANAGER(self.Scenario, self.Demand_List) as timeAttribute:
                    # bgTransitAttribute is None
                    # Adding @ for the process of generating link cost attributes and declaring list variables

                    def get_attribute_name(at):
                        if at.startswith("@"):
                            return at
                        else:
                            return "@" + at

                    classVolumeAttributes = [get_attribute_name(at) for at in self.ResultAttributes.split(",")]

                    for name in classVolumeAttributes:
                        if name == "@None" or name == "@none":
                            name = None
                            continue
                        if self.Scenario.extra_attribute(name) is not None:
                            _m.logbook_write("Deleting Previous Extra Attributes.")
                            self.Scenario.delete_extra_attribute(name)
                        _m.logbook_write("Creating link cost attribute '@(mode)'.")
                        self.Scenario.create_extra_attribute("LINK", name, default_value=0)

                    with (_util.tempMatricesMANAGER(len(self.Demand_List), description="Peak hour matrix")) as peakHourMatrix:
                        # only do if you want background transit
                        if self.BackgroundTransit == True:
                            # only do if there are actually transit lines present in the network
                            if int(self.Scenario.element_totals["transit_lines"]) > 0:
                                # Do Once
                                with _m.logbook_trace("Calculating transit background traffic"):
                                    networkCalculationTool(
                                        self._RoadAssignmentUtil._getTransitBGSpec(self.on_road_ttfs),
                                        scenario=self.Scenario,
                                    )
                                    self._tracker.completeSubtask()

                        appliedTollFactor = self._RoadAssignmentUtil._calculateAppliedTollFactor(self.TollWeight)
                        # Do for each class
                        with _m.logbook_trace("Calculating link costs"):
                            for i in range(len(self.Demand_List)):
                                networkCalculationTool(
                                    self._RoadAssignmentUtil._getLinkCostCalcSpec(
                                        costAttribute[i].id,
                                        self.LinkCost[i],
                                        self.LinkTollAttributeId[i],
                                        appliedTollFactor[i],
                                    ),
                                    scenario=self.Scenario,
                                )
                                self._tracker.completeSubtask()
                        # For each class
                        with _m.logbook_trace("Calculating peak hour matrix"):
                            for i in range(len(self.Demand_List)):
                                if EMME_VERSION >= (4, 2, 1):
                                    matrixCalcTool(self._RoadAssignmentUtil._getPeakHourSpec(peakHourMatrix[i].id, self.Demand_List[i], self.PeakHourFactor), scenario=self.Scenario, num_processors=self.NumberOfProcessors)
                                else:
                                    matrixCalcTool(self._RoadAssignmentUtil._getPeakHourSpec(peakHourMatrix[i].id, self.Demand_List[i].id, self.PeakHourFactor), scenario=self.Scenario)
                            self._tracker.completeSubtask()

                        self._tracker.completeTask()

                        with _m.logbook_trace("Running Road Assignments."):
                            # init assignment flag. if assignment done, then trip flag
                            assignmentComplete = False
                            # init attribute flag. if list has something defined, then trip flag
                            attributeDefined = False
                            allAttributes = []
                            allMatrices = []
                            selectedLinkVolumes = []
                            operators = []
                            lowerBounds = []
                            upperBounds = []
                            pathSelectors = []
                            multiplyPathDemand = []
                            multiplyPathValue = []
                            # check to see if any cost matrices defined
                            for i in range(len(self.Demand_List)):
                                allAttributes.append([])
                                allMatrices.append([])
                                selectedLinkVolumes.append([])
                                operators.append([])
                                lowerBounds.append([])
                                upperBounds.append([])
                                pathSelectors.append([])
                                multiplyPathDemand.append([])
                                multiplyPathValue.append([])
                                if self.CostMatrixId[i] is not None:
                                    _m.logbook_write("Cost matrix defined for class %s" % self.ClassNames[i])
                                    allAttributes[i].append(costAttribute[i].id)
                                    allMatrices[i].append(self.CostMatrixId[i])
                                    selectedLinkVolumes[i].append(None)
                                    operators[i].append("+")
                                    lowerBounds[i].append(None)
                                    upperBounds[i].append(None)
                                    pathSelectors[i].append("ALL")
                                    multiplyPathDemand[i].append(False)
                                    multiplyPathValue[i].append(True)
                                    attributeDefined = True
                                else:
                                    allAttributes[i].append(None)
                                if self.TollsMatrixId[i] is not None:
                                    _m.logbook_write("Toll matrix defined for class %s" % self.ClassNames[i])
                                    allAttributes[i].append(self.LinkTollAttributeId[i])
                                    allMatrices[i].append(self.TollsMatrixId[i])
                                    selectedLinkVolumes[i].append(None)
                                    operators[i].append("+")
                                    lowerBounds[i].append(None)
                                    upperBounds[i].append(None)
                                    pathSelectors[i].append("ALL")
                                    multiplyPathDemand[i].append(False)
                                    multiplyPathValue[i].append(True)
                                    attributeDefined = True
                                else:
                                    allAttributes[i].append(None)
                                for j in range(len(self.ClassAnalysisAttributes[i])):
                                    if self.ClassAnalysisAttributes[i][j] is not None:
                                        _m.logbook_write("Additional matrix for attribute %s defined for class %s" % (self.ClassAnalysisAttributes[i][j], self.ClassNames[i]))
                                        allAttributes[i].append(self.ClassAnalysisAttributes[i][j])
                                        allMatrices[i].append(self.ClassAnalysisAttributesMatrix[i][j])
                                        selectedLinkVolumes[i].append(self.ClassAnalysisSelectedLinkVolumes[i][j])
                                        operators[i].append(self.ClassAnalysisOperators[i][j])
                                        lowerBounds[i].append(self.ClassAnalysisLowerBounds[i][j])
                                        upperBounds[i].append(self.ClassAnalysisUpperBounds[i][j])
                                        pathSelectors[i].append(self.ClassAnalysisSelectors[i][j])
                                        multiplyPathDemand[i].append(self.ClassAnalysisMultiplyPathDemand[i][j])
                                        multiplyPathValue[i].append(self.ClassAnalysisMultiplyPathValue[i][j])
                                        attributeDefined = True
                                    else:
                                        allAttributes[i].append(None)
                            if attributeDefined is True:
                                spec = self._RoadAssignmentUtil._getPrimarySOLASpec(
                                    self.Demand_List,
                                    peakHourMatrix,
                                    appliedTollFactor,
                                    self.Mode_List_Split,
                                    classVolumeAttributes,
                                    costAttribute,
                                    allAttributes,
                                    allMatrices,
                                    operators,
                                    lowerBounds,
                                    upperBounds,
                                    pathSelectors,
                                    multiplyPathDemand,
                                    multiplyPathValue,
                                    multiprocessing,
                                    self.Iterations,
                                    self.rGap,
                                    self.brGap,
                                    self.normGap,
                                    self.PerformanceFlag,
                                    self.TimesMatrixId,
                                    selectedLinkVolumes
                                )
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)
                                assignmentComplete = True
                            for i in range(len(self.Demand_List)):
                                # check to see if any time matrices defined to fix the times matrix for that class
                                if self.TimesMatrixId[i] is not None:
                                    matrixCalcTool(
                                        self._RoadAssignmentUtil._CorrectTimesMatrixSpec(self.TimesMatrixId[i], self.CostMatrixId[i]),
                                        scenario=self.Scenario,
                                        num_processors=self.NumberOfProcessors,
                                    )
                                # check to see if any cost matrices defined to fix the cost matrix for that class
                                if self.CostMatrixId[i] is not None:
                                    matrixCalcTool(
                                        self._RoadAssignmentUtil._CorrectCostMatrixSpec(self.CostMatrixId[i], appliedTollFactor[i]),
                                        scenario=self.Scenario,
                                        num_processors=self.NumberOfProcessors,
                                    )
                            # if no assignment has been done, do an assignment
                            if assignmentComplete is False:
                                attributes = []
                                for i in range(len(self.Demand_List)):
                                    attributes.append(None)
                                spec = self._RoadAssignmentUtil._getPrimarySOLASpec(
                                    self.Demand_List,
                                    peakHourMatrix,
                                    appliedTollFactor,
                                    self.Mode_List_Split,
                                    classVolumeAttributes,
                                    costAttribute,
                                    attributes,
                                    None,
                                    None,
                                    None,
                                    None,
                                    None,
                                    None,
                                    None,
                                    multiprocessing,
                                    self.Iterations,
                                    self.rGap,
                                    self.brGap,
                                    self.normGap,
                                    self.PerformanceFlag,
                                    self.TimesMatrixId,
                                )
                                report = self._tracker.runTool(trafficAssignmentTool, spec, scenario=self.Scenario)

                            stoppingCriterion = report["stopping_criterion"]
                            iterations = report["iterations"]
                            if len(iterations) > 0:
                                finalIteration = iterations[-1]
                            else:
                                finalIteration = {"number": 0}
                                stoppingCriterion = "MAX_ITERATIONS"
                            number = finalIteration["number"]

                            if stoppingCriterion == "MAX_ITERATIONS":
                                val = finalIteration["number"]
                            elif stoppingCriterion == "RELATIVE_GAP":
                                val = finalIteration["gaps"]["relative"]
                            elif stoppingCriterion == "NORMALIZED_GAP":
                                val = finalIteration["gaps"]["normalized"]
                            elif stoppingCriterion == "BEST_RELATIVE_GAP":
                                val = finalIteration["gaps"]["best_relative"]
                            else:
                                val = "undefined"

                            print("Primary assignment complete at %s iterations." % number)
                            print("Stopping criterion was %s with a value of %s." % (stoppingCriterion, val))

    ##########################################################################################################

    # ----CONTEXT MANAGERS---------------------------------------------------------------------------------
    """
    Context managers for temporary database modifications.
    """

    @contextmanager
    def _AoNScenarioMANAGER(self):
        # Code here is executed upon entry

        tempScenarioNumber = _util.getAvailableScenarioNumber()

        if tempScenarioNumber is None:
            raise Exception("No additional scenarios are available!")

        scenario = _MODELLER.emmebank.copy_scenario(self.Scenario.id, tempScenarioNumber, copy_path_files=False, copy_strat_files=False, copy_db_files=False)
        scenario.title = "All-or-nothing assignment"

        _m.logbook_write("Created temporary Scenario %s for all-or-nothing assignment." % tempScenarioNumber)

        try:
            yield scenario
        # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _MODELLER.emmebank.delete_scenario(tempScenarioNumber)
            _m.logbook_write("Deleted temporary Scenario %s" % tempScenarioNumber)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()

    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    @_m.method(return_type=six.text_type)
    def _GetSelectAttributeOptionsHTML(self):
        list = []

        for att in self.Scenario.extra_attributes():
            if not att.type == "LINK":
                continue
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = '<option value="{id}">{text}</option>'.format(id=att.name, text=label)
            list.append(html)
        return "\n".join(list)
