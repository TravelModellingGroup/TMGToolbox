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
import multiprocessing
import os

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
    StartIndex = _m.Attribute(str)
    VariableTopology = _m.Attribute(str)
    InnerIterations = _m.Attribute(str)
    OuterIterations = _m.Attribute(str)
    CoarseRGap = _m.Attribute(str)
    FineRGap = _m.Attribute(str)
    CoarseBRGap = _m.Attribute(str)
    FineBRGap = _m.Attribute(str)
    NormalizedGap = _m.Attribute(str)
    PerformanceFlag = _m.Attribute(str)
    RunTitle = _m.Attribute(str)
    OnRoadTTFRanges = _m.Attribute(str)
    Mode = _m.Attribute(str)
    DemandMatrixNumber = _m.Attribute(str)
    TimeMatrixNumber = _m.Attribute(str)
    CostMatrixNumber = _m.Attribute(str)
    TollMatrixNumber = _m.Attribute(str)
    VolumeAttribute = _m.Attribute(str)
    AttributeStartIndex = _m.Attribute(str)
    LinkTollAttributeID = _m.Attribute(str)
    TollWeight = _m.Attribute(str)
    LinkCost = _m.Attribute(str)

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
            title="Multi-Class Road Assignment",
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
        Mode,
        DemandMatrixNumber,
        TimeMatrixNumber,
        CostMatrixNumber,
        TollMatrixNumber,
        VolumeAttribute,
        AttributeStartIndex,
        LinkTollAttributeID,
        TollWeight,
        LinkCost,
    ):
        # ---1 Set up Scenario
        self.Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.Scenario is None:
            raise Exception("Scenario %s was not found!" % ScenarioNumber)
        # self.OnRoadTTFRanges = RangeSetOnRoadTTFs
        print(
            ScenarioNumber,
            IntervalLengths,
            StartTime,
            ExtraTimeInterval,
            NumberOfExtraTimeIntervals,
            BackgroundTraffic,
            LinkComponentAttribute,
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
            Mode,
            DemandMatrixNumber,
            TimeMatrixNumber,
            CostMatrixNumber,
            TollMatrixNumber,
            VolumeAttribute,
            AttributeStartIndex,
            LinkTollAttributeID,
            TollWeight,
            LinkCost,
        )
