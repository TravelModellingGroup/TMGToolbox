"""
    Copyright 2022 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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

import multiprocessing
import inro.modeller as _m
import multiprocessing

_MODELLER = _m.Modeller()
_util = _MODELLER.module("tmg.common.utilities")
_geolib = _MODELLER.module("tmg.common.geometry")
Shapely2ESRI = _geolib.Shapely2ESRI
networkCalcTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator")
matrixCalcTool = _MODELLER.tool("inro.emme.matrix_calculation.matrix_calculator")
subareaAnalysisTool = _MODELLER.tool("inro.emme.subarea.subarea")
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

# import six library for python2 to python3 conversion
import six

# initalize python3 types
_util.initalizeModellerTypes(_m)


class ExportSubareaTool(_m.Tool()):
    version = "2.0.0"
    tool_run_msg = ""
    number_of_tasks = 4
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    LinkTollAttributeId = _m.Attribute(str)
    TimesMatrixId = _m.Attribute(str)
    CostMatrixId = _m.Attribute(str)
    TollsMatrixId = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    Mode_List = _m.Attribute(str)
    xtmf_Demand_String = _m.Attribute(str)
    Demand_List = _m.Attribute(str)
    PeakHourFactor = _m.Attribute(float)
    LinkCost = _m.Attribute(str)
    TollWeight = _m.Attribute(str)
    Iterations = _m.Attribute(int)
    rGap = _m.Attribute(float)
    brGap = _m.Attribute(float)
    normGap = _m.Attribute(float)
    PerformanceFlag = _m.Attribute(bool)
    SOLAFlag = _m.Attribute(bool)
    xtmf_NameString = _m.Attribute(str)
    ResultAttributes = _m.Attribute(str)
    xtmf_BackgroundTransit = _m.Attribute(str)
    OnRoadTTFRanges = _m.Attribute(str)
    NumberOfProcessors = _m.Attribute(int)
    xtmf_shapeFileLocation = _m.Attribute(str)
    xtmf_iSubareaLinkSelection = _m.Attribute(str)
    xtmf_jSubareaLinkSelection = _m.Attribute(str)
    xtmf_subareaGateAttribute = _m.Attribute(str)
    xtmf_subareaNodeAttribute = _m.Attribute(str)
    xtmf_createNodeFlagFromShapeFile = _m.Attribute(bool)
    xtmf_createGateAttrib = _m.Attribute(bool)
    xtmf_extractTransit = _m.Attribute(bool)
    xtmf_outputFolder = _m.Attribute(str)

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
        xtmf_BackgroundTransit,
        OnRoadTTFRanges,
        xtmf_shapeFileLocation,
        xtmf_iSubareaLinkSelection,
        xtmf_jSubareaLinkSelection,
        xtmf_subareaGateAttribute,
        xtmf_subareaNodeAttribute,
        xtmf_createNodeFlagFromShapeFile,
        xtmf_createGateAttrib,
        xtmf_extractTransit,
        xtmf_outputFolder,
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
        self.ClassAnalysisAttributes = []
        self.ClassAnalysisAttributesMatrix = []
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
        self.ShapeFileLocation = xtmf_shapeFileLocation
        self.ISubareaLinkSelection = xtmf_iSubareaLinkSelection
        self.JSubareaLinkSelection = xtmf_jSubareaLinkSelection
        self.SubareaGateAttribute = xtmf_subareaGateAttribute
        self.SubareaNodeAttribute = xtmf_subareaNodeAttribute
        self.CreateNodeFlagFromShapeFile = xtmf_createNodeFlagFromShapeFile
        self.CreateGateAttrib = xtmf_createGateAttrib
        self.ExtractTransit = xtmf_extractTransit
        self.OutputFolder = xtmf_outputFolder
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
                                SOLA_spec = self._RoadAssignmentUtil._getPrimarySOLASpec(
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

                                if self.CreateGateAttrib:
                                    self._CreateSubareaExtraAttribute(self.SubareaGateAttribute, "LINK")
                                    self._TagSubareaCentroids()

                                if self.CreateNodeFlagFromShapeFile:
                                    self._CreateSubareaExtraAttribute(self.SubareaNodeAttribute, "NODE")
                                    network = self.Scenario.get_network()
                                    subareaNodes = self._LoadShapeFIle(network)
                                    for node in subareaNodes:
                                        node[self.SubareaNodeAttribute] = 1
                                    self.Scenario.publish_network(network)

                                self._tracker.runTool(
                                    subareaAnalysisTool,
                                    subarea_nodes=self.SubareaNodeAttribute,
                                    subarea_folder=self.OutputFolder,
                                    traffic_assignment_spec=SOLA_spec,
                                    extract_transit=self.ExtractTransit,
                                    overwrite=True,
                                    gate_labels=self.SubareaGateAttribute,
                                    scenario=self.Scenario,
                                )

    def _CreateSubareaExtraAttribute(self, attribID, attribType):
        if self.Scenario.extra_attribute(attribID) is None:
            self.Scenario.create_extra_attribute(
                attribType,
                attribID,
            )

    def _TagSubareaCentroids(self):
        iSpec = {
            "type": "NETWORK_CALCULATION",
            "result": self.SubareaGateAttribute,
            "expression": "i",
            "selections": {"link": self.ISubareaLinkSelection},
        }
        jSpec = {
            "type": "NETWORK_CALCULATION",
            "result": self.SubareaGateAttribute,
            "expression": "-j",
            "selections": {"link": self.JSubareaLinkSelection},
        }
        networkCalcTool([iSpec, jSpec], self.Scenario)

    def _LoadShapeFIle(self, network):
        with Shapely2ESRI(self.ShapeFileLocation, mode="read") as reader:
            if int(reader._size) != 1:
                raise Exception("Shapefile has invalid number of features. There should only be one 1 polygon in the shapefile")
            SubareaNodes = []
            for node in network.nodes():
                for border in reader.readThrough():
                    if node not in SubareaNodes:
                        point = _geolib.nodeToShape(node)
                        if border.contains(point) == True:
                            SubareaNodes.append(node)
        return SubareaNodes
