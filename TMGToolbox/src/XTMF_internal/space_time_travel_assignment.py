"""
    Copyright 2023 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
import os
import json
from json import loads as _parsedict
from contextlib import contextmanager

_MODELLER = _m.Modeller()
_util = _MODELLER.module("tmg.common.utilities")
_geolib = _MODELLER.module("tmg.common.geometry")
_bank = _MODELLER.emmebank
_write = _m.logbook_write
_trace = _m.logbook_trace
Shapely2ESRI = _geolib.Shapely2ESRI
networkCalcTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator")
matrixCalcTool = _MODELLER.tool("inro.emme.matrix_calculation.matrix_calculator")
trafficAssignmentTool = _MODELLER.tool("inro.emme.traffic_assignment.space_time_traffic_assignment")
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

# import six library for python2 to python3 conversion
import six

# initalize python3 types
_util.initalizeModellerTypes(_m)


class SpaceTimeTrafficAssignmentTool(_m.Tool()):
    version = "1.0.0"
    tool_run_msg = ""
    number_of_tasks = 4
    Scenario = _m.Attribute(_m.InstanceType)
    ScenarioNumber = _m.Attribute(int)
    IntervalLengths = _m.Attribute(str)
    StartTime = _m.Attribute(str)
    ExtraTimeInterval = _m.Attribute(float)
    NumberOfExtraTimeIntervals = _m.Attribute(int)
    BackgroundTraffic = _m.Attribute(bool)
    LinkComponentAttribute = _m.Attribute(str)
    CreateLinkComponentAttribute = _m.Attribute(bool)
    StartIndex = _m.Attribute(int)
    VariableTopology = _m.Attribute(str)
    InnerIterations = _m.Attribute(int)
    OuterIterations = _m.Attribute(int)
    CoarseRGap = _m.Attribute(float)
    FineRGap = _m.Attribute(float)
    CoarseBRGap = _m.Attribute(float)
    FineBRGap = _m.Attribute(float)
    NormalizedGap = _m.Attribute(float)
    PerformanceFlag = _m.Attribute(bool)
    RunTitle = _m.Attribute(str)
    OnRoadTTFRanges = _m.Attribute(str)
    Mode = _m.Attribute(str)
    DemandMatrixNumber = _m.Attribute(str)
    TimeMatrixNumber = _m.Attribute(str)
    CostMatrixNumber = _m.Attribute(str)
    TollMatrixNumber = _m.Attribute(str)
    VolumeAttribute = _m.Attribute(str)
    AttributeStartIndex = _m.Attribute(int)
    LinkTollAttributeID = _m.Attribute(str)
    TollWeight = _m.Attribute(float)
    LinkCost = _m.Attribute(float)
    TrafficClasses = _m.Attribute(str)

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
        self.LinkTollAttributeID = "@toll"
        self.NumberOfProcessors = multiprocessing.cpu_count()
        self.OnRoadTTFRanges = "3-128"

    def page(self):
        pb = _m.ToolPageBuilder(
            self,
            title="Multi-Class Road Assignment with STTA",
            description="Cannot be called from Modeller.",
            runnable=False,
            branding_text="XTMF",
        )
        return pb.render()

    def __call__(
        self,
        ScenarioNumber,
        IntervalLengths,
        StartTime,
        ExtraTimeInterval,
        NumberOfExtraTimeIntervals,
        BackgroundTraffic,
        LinkComponentAttribute,
        CreateLinkComponentAttribute,
        StartIndex,
        VariableTopology,
        InnerIterations,
        OuterIterations,
        CoarseRGap,
        FineRGap,
        CoarseBRGap,
        FineBRGap,
        NormalizedGap,
        PerformanceFlag,
        RunTitle,
        OnRoadTTFRanges,
        TrafficClasses,
    ):
        print("starting...")
        # ---1 Set up Scenario
        Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if Scenario is None:
            raise Exception("Scenario %s was not found!" % ScenarioNumber)
        OnRoadTTFRanges = OnRoadTTFRanges
        InnerIterations = InnerIterations
        OuterIterations = OuterIterations
        CoarseRGap = CoarseRGap
        FineRGap = FineRGap
        CoarseBRGap = CoarseBRGap
        FineBRGap = FineBRGap
        NormalizedGap = NormalizedGap
        RunTitle = RunTitle[:25]
        PerformanceFlag = PerformanceFlag
        IntervalLengthList = [float(x) for x in IntervalLengths.split(",")]
        StartTime = StartTime
        ExtraTimeInterval = ExtraTimeInterval
        NumberOfExtraTimeIntervals = NumberOfExtraTimeIntervals
        StartIndex = StartIndex
        VariableTopology = VariableTopology
        Parameters = json.loads(TrafficClasses)
        for tc in Parameters["TrafficClasses"]:
            tc["TollWeightList"] = [float(x) for x in tc["TollWeightList"].split(",")]

        try:
            print("Starting assignment.")
            self._execute(
                Scenario,
                IntervalLengthList,
                StartTime,
                ExtraTimeInterval,
                NumberOfExtraTimeIntervals,
                BackgroundTraffic,
                LinkComponentAttribute,
                CreateLinkComponentAttribute,
                StartIndex,
                VariableTopology,
                InnerIterations,
                OuterIterations,
                CoarseRGap,
                FineRGap,
                CoarseBRGap,
                FineBRGap,
                NormalizedGap,
                PerformanceFlag,
                RunTitle,
                OnRoadTTFRanges,
                Parameters,
            )
            print("Assignment complete.")
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(
        self,
        Scenario,
        IntervalLengthList,
        StartTime,
        ExtraTimeInterval,
        NumberOfExtraTimeIntervals,
        BackgroundTraffic,
        LinkComponentAttribute,
        CreateLinkComponentAttribute,
        StartIndex,
        VariableTopology,
        InnerIterations,
        OuterIterations,
        CoarseRGap,
        FineRGap,
        CoarseBRGap,
        FineBRGap,
        NormalizedGap,
        PerformanceFlag,
        RunTitle,
        OnRoadTTFRanges,
        Parameters,
    ):
        for tc in Parameters["TrafficClasses"]:
            if len(tc["TollWeightList"]) != len(IntervalLengthList):
                raise Exception("Length of Toll weight list %s is not equal to the length of interval length list %s", (len(tc["TollWeightList"]), len(IntervalLengthList)))
        """
        matrix_indices_used_list keeps track of all the matrices already created/used
        """
        matrix_indices_used_list = []
        #   create all time dependent matrix dictionary
        allMatrixDictsList = []
        for tc in Parameters["TrafficClasses"]:
            all_matrix_dict = self._create_time_dependent_matrix_dict(
                matrix_indices_used_list,
                IntervalLengthList,
                tc["DemandMatrixNumber"],
                "demand_matrix",
                [("cost_matrix", tc["CostMatrixNumber"]), ("time_matrix", tc["TimeMatrixNumber"]), ("toll_matrix", tc["TollMatrixNumber"])],
            )
            allMatrixDictsList.append(all_matrix_dict)
        #   load all time dependent output matrices
        self._load_input_matrices(allMatrixDictsList, "demand_matrix")
        self._load_output_matrices(allMatrixDictsList, ["cost_matrix", "time_matrix", "toll_matrix"])

        with _m.logbook_trace(
            name="%s (%s v%s)" % (self.RunTitle, self.__class__.__name__, self.version),
            attributes=self._load_atts(
                Scenario,
                RunTitle,
                OuterIterations,
                InnerIterations,
                Parameters["TrafficClasses"],
                self.__MODELLER_NAMESPACE__,
            ),
        ):
            self._tracker.reset()
            with self.temporaryMatricesManager() as temporaryMatrixList:
                # initialize input matrices
                self._init_input_matrices(allMatrixDictsList, temporaryMatrixList, inputMatrixName="demand_matrix")
                # initialize output matrices
                self._init_output_matrices(allMatrixDictsList, temporaryMatrixList, outputMatrixName="cost_matrix", description="")
                self._init_output_matrices(allMatrixDictsList, temporaryMatrixList, outputMatrixName="time_matrix", description="")
                self._init_output_matrices(allMatrixDictsList, temporaryMatrixList, outputMatrixName="toll_matrix", description="")
                with self.temporaryAttributeManager(Scenario) as tempAttributeList:
                    timeDependentVolumeAttributeLists = []
                    timeDependentTimeAttributeLists = []
                    timeDependentCostAttributeLists = []
                    timeDependentLinkTollAttributeLists = []
                    for tc in Parameters["TrafficClasses"]:
                        timeDependentVolumeAttributeLists.append(self._create_time_dependent_attribute_list(tc["VolumeAttribute"], IntervalLengthList, tc["AttributeStartIndex"]))
                        timeDependentTimeAttributeLists.append(self._create_time_dependent_attribute_list("ltime", IntervalLengthList, tc["AttributeStartIndex"]))
                        timeDependentCostAttributeLists.append(self._create_time_dependent_attribute_list("lkcst", IntervalLengthList, tc["AttributeStartIndex"]))
                        timeDependentLinkTollAttributeLists.append(self._create_time_dependent_attribute_list(tc["LinkTollAttributeID"], IntervalLengthList, tc["AttributeStartIndex"]))

                    volumeAttributeLists = self._create_volume_attribute(Scenario, timeDependentVolumeAttributeLists)
                    timeDependentComponentAttributeList = self._create_time_dependent_attribute_list(LinkComponentAttribute, IntervalLengthList, StartIndex)
                    timeAttributeLists = self._createTimeDependentAttributeLists(Scenario, timeDependentTimeAttributeLists, tempAttributeList, "LINK", "traffic")
                    costAttributeLists = self._createTimeDependentAttributeLists(Scenario, timeDependentCostAttributeLists, tempAttributeList, "LINK", "traffic")
                    tollAttributeLists = self._createTimeDependentAttributeLists(Scenario, timeDependentLinkTollAttributeLists, tempAttributeList, "LINK", "traffic", is_temp_attribute=False)
                    if CreateLinkComponentAttribute:
                        linkComponentAttributeList = self._create_transit_traffic_attribute_list(Scenario, timeDependentComponentAttributeList, tempAttributeList)
                    self._tracker.completeSubtask()
                    # Calculate applied toll factor
                    appliedTollFactorLists = self._calculate_applied_toll_factor(Parameters)
                    self._calculateLinkCost(Scenario, Parameters, appliedTollFactorLists, costAttributeLists, tollAttributeLists)
                    self._tracker.completeSubtask()
                    # Assign traffic to road network per time period
                    with _trace("Running Road Assignments."):
                        completed_path_analysis = False
                        if completed_path_analysis is False:
                            modeList = self._loadModeList(Parameters)
                            stta_spec = self._get_primary_STTA_spec(
                                allMatrixDictsList,
                                modeList,
                                volumeAttributeLists,
                                costAttributeLists,
                                IntervalLengthList,
                                StartTime,
                                ExtraTimeInterval,
                                NumberOfExtraTimeIntervals,
                                InnerIterations,
                                OuterIterations,
                                CoarseRGap,
                                FineRGap,
                                CoarseBRGap,
                                FineBRGap,
                                NormalizedGap,
                                Parameters,
                                PerformanceFlag,
                                linkComponentAttributeList,
                            )
                            report = self._tracker.runTool(trafficAssignmentTool, stta_spec, scenario=Scenario)
                        checked = self._load_stopping_criteria(report)
                        number = checked[0]
                        stopping_criterion = checked[1]
                        value = checked[2]
                        print("Primary assignment complete at %s iterations." % number)
                        print("Stopping criterion was %s with a value of %s." % (stopping_criterion, value))

    def _load_atts(self, Scenario, run_title, max_outer_iterations, max_inner_iterations, traffic_classes, modeller_namespace):
        time_matrix_ids = ["mf" + str(mtx["TimeMatrixNumber"]) for mtx in traffic_classes]
        LinkCosts = [str(lc["LinkCost"]) for lc in traffic_classes]
        atts = {
            "Run Title": run_title,
            "Scenario": str(Scenario.id),
            "Times Matrix": str(", ".join(time_matrix_ids)),
            "Link Cost": str(", ".join(LinkCosts)),
            "Max Outer Iterations": str(max_outer_iterations),
            "Max Inner Iterations": str(max_inner_iterations),
            "self": modeller_namespace,
        }
        return atts

    def _create_time_dependent_attribute_list(self, attribute_name, interval_length_list, AttributeStartIndex):
        def check_att_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        time_dependent_attribute_list = [check_att_name(attribute_name) + str(AttributeStartIndex + i) for i, j in enumerate(interval_length_list)]
        return time_dependent_attribute_list

    def _create_time_dependent_matrix_dict(
        self,
        matrix_indices_used_list,
        interval_length_list,
        input_matrix_number,
        inputMatrixName,
        output_matrix_name_list,
    ):
        """
        creates all time dependent input and output matrix in a dictionary.
        Matrix index depends on the input matrix. For example, if time dependent
        input matrix ends starts from mf1 to mf4 all other matrices begin from mf5 and so on.
        """
        all_matrix_dict = {}
        # add all matrix names to be created to dict
        all_matrix_dict[inputMatrixName] = ""
        for i in range(0, len(output_matrix_name_list)):
            all_matrix_dict[output_matrix_name_list[i][0]] = ""
        #   add input matrix list
        input_matrix_list = []
        for i, j in enumerate(interval_length_list):
            if input_matrix_number == 0:
                input_matrix_list.append("mf0")
            else:
                input_matrix_list.append("mf" + str(input_matrix_number + i))
                matrix_indices_used_list.append(input_matrix_number + i)
        all_matrix_dict[inputMatrixName] = input_matrix_list
        for output_matrix in output_matrix_name_list:
            matrix_name = output_matrix[0]
            matrix_number = output_matrix[1]
            output_matrix_list = []
            for j in range(0, len(interval_length_list)):
                if matrix_number == 0:
                    output_matrix_list.append("mf0")
                else:
                    output_matrix_list.append("mf" + str(output_matrix[1] + j))
                    matrix_indices_used_list.append(matrix_number + j)
            all_matrix_dict[matrix_name] = output_matrix_list
        return all_matrix_dict

    def _load_input_matrices(self, allMatrixDictsList, inputMatrixName):
        """
        Load input matrices creates and returns a list of (input) matrices based on matrix_name supplied.
        E.g of matrix_name: "demand_matrix", matrix_id: "mf2"
        """

        def exception(mtx_id, mtx_name):
            raise Exception('Matrix %s with matrix name "%s" was not found!' % (mtx_id, mtx_name))

        for matrix_list in allMatrixDictsList:
            for i, mtx in enumerate(matrix_list[inputMatrixName]):
                if mtx == "mf0" or self._get_or_create(mtx).id == mtx:
                    matrix_list[inputMatrixName][i] = _bank.matrix(mtx)
                else:
                    exception(mtx, inputMatrixName)

    def _load_output_matrices(self, allMatrixDictsList, matrix_name_list):
        for matrix_list in allMatrixDictsList:
            for matrix_name in matrix_name_list:
                for i, matrix_id in enumerate(matrix_list[matrix_name]):
                    if matrix_id == "mf0":
                        matrix_list[matrix_name][i] = None
                    else:
                        matrix_list[matrix_name][i] = self._get_or_create(matrix_id)

    def _get_or_create(self, matrix_id):
        mtx = _bank.matrix(matrix_id)
        if mtx is None:
            mtx = _bank.create_matrix(matrix_id, default_value=0)
        return mtx

    def _init_input_matrices(self, allMatrixDictsList, temporaryMatrixList, inputMatrixName=""):
        """
        - Checks the list of all load matrices in load_input_matrix_list,
            for None, create a temporary matrix and initialize
        - Returns a list of all input matrices provided
        """
        for matrix_list in allMatrixDictsList:
            for i, mtx in enumerate(matrix_list[inputMatrixName]):
                if mtx == None:
                    mtx = _util.initializeMatrix(matrix_type="FULL")
                    temporaryMatrixList.append(mtx)
                    matrix_list[inputMatrixName][i] = mtx

    def _init_output_matrices(self, allMatrixDictsList, temporaryMatrixList, outputMatrixName="", description=""):
        """
        - Checks the dictionary of all load matrices in load_output_matrix_dict,
            for None, create a temporary matrix and initialize
        - Returns a list of all input matrices provided
        """
        desc = "AUTO %s FOR CLASS" % (outputMatrixName.upper())
        for matrix_list in allMatrixDictsList:
            for i, mtx in enumerate(matrix_list[outputMatrixName]):
                if mtx == None:
                    matrix = _util.initializeMatrix(name=outputMatrixName, description=description if description != "" else desc)
                    temporaryMatrixList.append(matrix)
                    matrix_list[outputMatrixName][i] = matrix

    def _create_volume_attribute(self, Scenario, volumeAttributeLists):
        for volume_attribute_list in volumeAttributeLists:
            for volume_attribute in volume_attribute_list:
                volume_attribute_at = Scenario.extra_attribute(volume_attribute)
                if volume_attribute_at is not None:
                    if volume_attribute_at.type != "LINK":
                        raise Exception("Volume Attribute '%s' is not a link type attribute" % volume_attribute)
                    Scenario.delete_extra_attribute(volume_attribute_at)
                Scenario.create_extra_attribute("LINK", volume_attribute, default_value=0)
        return volumeAttributeLists

    def _create_transit_traffic_attribute_list(self, Scenario, linkComponentAttributeList, tempAttributeList):
        # extra_parameter_tool(el1="0")
        transit_traffic_attribute_list = []
        for transit_traffic_att in linkComponentAttributeList:
            t_traffic_attribute = self._create_temp_attribute(Scenario, transit_traffic_att, "LINK", default_value=0.0, assignment_type="traffic")
            tempAttributeList.append(t_traffic_attribute)
            transit_traffic_attribute_list.append(t_traffic_attribute)
        return transit_traffic_attribute_list

    def _create_temp_attribute(self, Scenario, attribute_id, attribute_type, description=None, default_value=0.0, assignment_type=None):
        """
        Creates a temporary extra attribute in a given Scenario
        """
        ATTRIBUTE_TYPES = ["NODE", "LINK", "TURN", "TRANSIT_LINE", "TRANSIT_SEGMENT"]
        attribute_type = str(attribute_type).upper()
        # check if the type provided is correct
        if attribute_type not in ATTRIBUTE_TYPES:
            raise TypeError("Attribute type '%s' provided is not recognized." % attribute_type)
        if len(attribute_id) > 18:
            raise ValueError("Attribute id '%s' can only be 19 characters long with no spaces plus no '@'." % attribute_id)
        prefix = str(attribute_id)
        attrib_id = ""
        if assignment_type == "transit":
            temp_extra_attribute = self._process_transit_attribute(Scenario, prefix, attribute_type, default_value)
        elif assignment_type == "traffic":
            temp_extra_attribute = self._process_traffic_attribute(Scenario, prefix, attribute_type, default_value)
        else:
            raise Exception("Attribute type is 'None' or 'invalid'." "Type can only be either 'transit' or 'traffic'.")
        attrib_id = temp_extra_attribute[1]
        msg = "Created temporary extra attribute %s in Scenario %s" % (
            attrib_id,
            Scenario.id,
        )
        if description:
            temp_extra_attribute[0].description = description
            msg += ": %s" % description
        _m.logbook_write(msg)
        return temp_extra_attribute[0]

    def _process_transit_attribute(self, Scenario, transit_attrib_id, attribute_type, default_value):
        if not transit_attrib_id.startswith("@"):
            transit_attrib_id = "@" + transit_attrib_id
        checked_extra_attribute = Scenario.extra_attribute(transit_attrib_id)
        if checked_extra_attribute is None:
            temp_transit_attrib = Scenario.create_extra_attribute(attribute_type, transit_attrib_id, default_value)
        elif checked_extra_attribute != None and checked_extra_attribute.type != attribute_type:
            raise Exception("Attribute %s already exist or has some issues!" % transit_attrib_id)
        else:
            temp_transit_attrib = Scenario.extra_attribute(transit_attrib_id)
            temp_transit_attrib.initialize(default_value)
        return temp_transit_attrib, transit_attrib_id

    def _process_traffic_attribute(self, Scenario, traffic_attrib_id, attribute_type, default_value):
        if not traffic_attrib_id.startswith("@"):
            traffic_attrib_id = "@%s" % (traffic_attrib_id)
        if Scenario.extra_attribute(traffic_attrib_id) is None:
            temp_traffic_attrib = Scenario.create_extra_attribute(attribute_type, traffic_attrib_id, default_value)
            _m.logbook_write(
                "Created extra attribute '%s'",
            )
        else:
            temp_traffic_attrib = Scenario.extra_attribute(traffic_attrib_id)
            temp_traffic_attrib.initialize(0)
        return temp_traffic_attrib, traffic_attrib_id

    def _calculate_applied_toll_factor(self, Parameters):
        applied_toll_factor_list = []
        for tc in Parameters["TrafficClasses"]:
            if len(tc["TollWeightList"]) != 0:
                try:
                    toll_weight_list = [60 / weight for weight in tc["TollWeightList"]]
                    applied_toll_factor_list.append(toll_weight_list)
                except ZeroDivisionError:
                    toll_weight_list = [0 * weight for weight in tc["TollWeightList"]]
                    applied_toll_factor_list.append(toll_weight_list)
        return applied_toll_factor_list

    def _createTimeDependentAttributeLists(self, Scenario, timeDependentTimeAttributeLists, tempAttributeList, attribute_type, assignment_type, is_temp_attribute=True):
        timeAttributeLists = []
        for time_dependent_attribute_list in timeDependentTimeAttributeLists:
            time_attribute_list = []
            for time_attribute in time_dependent_attribute_list:
                attribute = self._create_temp_attribute(Scenario, time_attribute, attribute_type, default_value=0.0, assignment_type=assignment_type)
                time_attribute_list.append(attribute)
                if is_temp_attribute is True:
                    tempAttributeList.append(attribute)
            timeAttributeLists.append(time_attribute_list)
        return timeAttributeLists

    def _calculateLinkCost(self, Scenario, Parameters, appliedTollFactorLists, costAttributeLists, tollAttributeLists):
        with _trace("Calculating link costs"):
            for i, cost_attribute_list in enumerate(costAttributeLists):
                for j in range(0, len(cost_attribute_list)):
                    networkCalcTool(
                        self._getLinkCostCalcSpec(
                            costAttributeLists[i][j].id,
                            Parameters["TrafficClasses"][i]["LinkCost"],
                            tollAttributeLists[i][j].id,
                            appliedTollFactorLists[i][j],
                        ),
                        scenario=Scenario,
                    )

    def _getLinkCostCalcSpec(self, cost_attribute_id, LinkCost, link_toll_attribute, perception):
        return {
            "result": cost_attribute_id,
            "expression": "(length * %f + %s)*%f" % (LinkCost, link_toll_attribute, perception),
            "aggregation": None,
            "selections": {"link": "all"},
            "type": "NETWORK_CALCULATION",
        }

    def _loadModeList(self, Parameters):
        modeList = [mode["Mode"] for mode in Parameters["TrafficClasses"]]
        return modeList

    def _get_primary_STTA_spec(
        self,
        allMatrixDictsList,
        modeList,
        volumeAttributeLists,
        costAttributeLists,
        IntervalLengthList,
        StartTime,
        ExtraTimeInterval,
        NumberOfExtraTimeIntervals,
        InnerIterations,
        OuterIterations,
        CoarseRGap,
        FineRGap,
        CoarseBRGap,
        FineBRGap,
        NormalizedGap,
        Parameters,
        PerformanceFlag,
        linkComponentAttributeList,
    ):
        if PerformanceFlag == True:
            number_of_processors = multiprocessing.cpu_count()
        else:
            number_of_processors = max(multiprocessing.cpu_count() - 1, 1)
        # Generic Spec for STTA
        STTA_spec = {
            "type": "SPACE_TIME_TRAFFIC_ASSIGNMENT",
            "assignment_period": {
                "start_time": StartTime,
                "interval_lengths": IntervalLengthList,
                "extra_time_interval": ExtraTimeInterval,
                "number_of_extra_time_intervals": NumberOfExtraTimeIntervals,
            },
            "background_traffic": {
                "link_component": linkComponentAttributeList[0].id,
                "turn_component": None,
            },
            "variable_topology": None,
            "classes": [],
            "path_analysis": None,
            "cutoff_analysis": None,
            "traversal_analysis": None,
            "results": {
                "link_volumes": volumeAttributeLists[0][0],
                "link_costs": None,
                "turn_volumes": None,
                "turn_costs": None,
            },
            "performance_settings": {"number_of_processors": number_of_processors},
            "stopping_criteria": {
                "max_outer_iterations": OuterIterations,
                "max_inner_iterations": InnerIterations,
                "relative_gap": {"coarse": CoarseRGap, "fine": FineRGap},
                "best_relative_gap": {"coarse": CoarseBRGap, "fine": FineBRGap},
                "normalized_gap": NormalizedGap,
            },
        }
        STTA_class_generator = []
        for i, matrix_dict in enumerate(allMatrixDictsList):
            stta_class = {
                "mode": modeList[i],
                "demand": matrix_dict["demand_matrix"][0].id,
                "generalized_cost": {
                    "link_costs": costAttributeLists[i][0].id,
                    "od_fixed_cost": None,
                },
                "results": {
                    "link_volumes": volumeAttributeLists[i][0],
                    "turn_volumes": None,
                    "od_travel_times": matrix_dict["time_matrix"][0].id,
                    "od_travel_times": None,
                    "vehicle_count": None,
                },
                "analysis": None,
            }
            STTA_class_generator.append(stta_class)
        STTA_spec["classes"] = STTA_class_generator
        return STTA_spec

    def _load_stopping_criteria(self, report):
        stopping_criterion = report["stopping_criterion"]
        iterations = report["outer_iterations"]
        if len(iterations) > 0:
            final_iteration = iterations[-1]
        else:
            final_iteration = {"number": 0}
            stopping_criterion == "MAX_ITERATIONS"
        number = final_iteration["number"]
        if stopping_criterion == "MAX_ITERATIONS":
            value = final_iteration["number"]
        elif stopping_criterion == "RELATIVE_GAP":
            value = final_iteration["gaps"]["relative"]
        elif stopping_criterion == "NORMALIZED_GAP":
            value = final_iteration["gaps"]["normalized"]
        elif stopping_criterion == "BEST_RELATIVE_GAP":
            value = final_iteration["gaps"]["best_relative"]
        else:
            value = "undefined"
        return number, stopping_criterion, value

    @contextmanager
    def temporaryMatricesManager(self):
        """
        Matrix objects created & added to this matrix list are deleted when this manager exits.
        """
        temporaryMatrixList = []
        try:
            yield temporaryMatrixList
        finally:
            for matrix in temporaryMatrixList:
                if matrix is not None:
                    _m.logbook_write("Deleting temporary matrix '%s': " % matrix.id)
                    _MODELLER.emmebank.delete_matrix(matrix.id)

    @contextmanager
    def temporaryAttributeManager(self, Scenario):
        tempAttributeList = []
        try:
            yield tempAttributeList
        finally:
            for temp_attribute in tempAttributeList:
                if temp_attribute is not None:
                    Scenario.delete_extra_attribute(temp_attribute.id)
                    _m.logbook_write("Deleted temporary '%s' link attribute" % temp_attribute.id)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.get_progress()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg


links407 = [
    "22398-32945",
    "22399-23189",
    "22400-22398",
    "22512-22400",
    "22514-22512",
    "23189-22513",
    "31984-32924",
    "31996-22399",
    "32483-32891",
    "32484-32888",
    "32518-32885",
    "32520-32894",
    "32775-33213",
    "32778-32779",
    "32779-32784",
    "32780-32887",
    "32781-32780",
    "32784-32889",
    "32785-32483",
    "32786-32890",
    "32787-32786",
    "32788-32892",
    "32789-32788",
    "32793-32893",
    "32795-32793",
    "32796-32797",
    "32797-32923",
    "32884-32886",
    "32885-32484",
    "32887-32775",
    "32888-32778",
    "32889-32785",
    "32890-32781",
    "32891-32520",
    "32892-32787",
    "32893-32789",
    "32894-32796",
    "32923-32931",
    "32924-32795",
    "32930-31984",
    "32931-32937",
    "32937-32938",
    "32938-32944",
    "32939-32940",
    "32940-32930",
    "32944-31996",
    "32945-32939",
    "33213-32884",
]


ramps = [
    "22491-22512",
    "22494-22516",
    "22495-22514",
    "22496-22513",
    "31433-22398",
    "31439-32945",
    "31440-31996",
    "31442-22399",
    "31966-31984",
    "32022-32778",
    "32023-32890",
    "32024-32520",
    "32025-32796",
    "32521-32793",
    "32592-32889",
    "32731-32779",
    "32749-32780",
    "32763-32887",
    "32782-32785",
    "32783-32786",
    "32790-32892",
    "32791-32788",
    "32792-32891",
    "32798-32797",
    "32799-32893",
    "32926-32931",
    "32929-32924",
    "32935-32938",
    "32936-32940",
]
