from __future__ import print_function

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
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

# import six library for python2 to python3 conversion
import six

# initalize python3 types
_util.initalizeModellerTypes(_m)


class CalculateBackgroundTraffic(_m.Tool()):
    version = "1.0.0"
    tool_run_msg = ""
    number_of_tasks = 4
    Scenario = _m.Attribute(_m.InstanceType)
    ScenarioNumber = _m.Attribute(int)
    IntervalLengths = _m.Attribute(str)
    LinkComponentAttribute = _m.Attribute(str)
    StartIndex = _m.Attribute(int)
    OnRoadTTFRanges = _m.Attribute(str)

    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        self.Scenario = _MODELLER.scenario
        self.OnRoadTTFRanges = "3-128"

    def page(self):
        pb = _m.ToolPageBuilder(
            self,
            title="Calculate Background Traffic @tvph[per_time_period] to be used be a space time traffic assignemnt tool STTA.",
            description="Cannot be called from Modeller.",
            runnable=False,
            branding_text="XTMF",
        )
        return pb.render()

    def __call__(self, ScenarioNumber, IntervalLengths, LinkComponentAttribute, StartIndex, OnRoadTTFRanges):
        Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if Scenario is None:
            raise Exception("Scenario %s was not found!" % ScenarioNumber)
        IntervalLengthList = [float(x) for x in IntervalLengths.split(",")]
        onRoadTTFRanges = self.convertToRanges(OnRoadTTFRanges)

        try:
            self._execute(Scenario, IntervalLengthList, LinkComponentAttribute, StartIndex, onRoadTTFRanges)
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(self, Scenario, IntervalLengthList, LinkComponentAttribute, StartIndex, onRoadTTFRanges):
        timeDependentComponentAttributeList = self.createTimeDependentAttributeList(LinkComponentAttribute, IntervalLengthList, StartIndex)
        linkComponentAttributeList = self.createTransitTrafficAttributeList(Scenario, timeDependentComponentAttributeList)
        self.calculateTransitBackgroundTraffic(Scenario, onRoadTTFRanges, linkComponentAttributeList, self._tracker)

    def calculateTransitBackgroundTraffic(self, Scenario, onRoadTTFRanges, linkComponentAttributeList, tracker):
        if int(Scenario.element_totals["transit_lines"]) > 0:
            bGSpecList = []
            with _trace("Calculating transit background traffic"):
                for linkComponentAttribute in linkComponentAttributeList:
                    spec = self.get_transit_bg_spec(onRoadTTFRanges, linkComponentAttribute.id)
                    bGSpecList.append(spec)
                networkCalcTool(bGSpecList, scenario=Scenario)
                tracker.completeTask()

    def get_transit_bg_spec(self, OnRoadTTFRanges, linkComponentAttribute):
        ttf_terms = str.join(
            " + ",
            ["((ttf >=" + str(x[0]) + ") * (ttf <= " + str(x[1]) + "))" for x in OnRoadTTFRanges],
        )
        return {
            "result": linkComponentAttribute,
            "expression": "(60 / hdw) * (vauteq) " + ("* (" + ttf_terms + ")" if ttf_terms else ""),
            "aggregation": "+",
            "selections": {"link": "all", "transit_line": "all"},
            "type": "NETWORK_CALCULATION",
        }

    def createTimeDependentAttributeList(self, attributeName, IntervalLengthList, attributeStartIndex):
        def check_att_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        time_dependent_attribute_list = [check_att_name(attributeName) + str(attributeStartIndex + i) for i, j in enumerate(IntervalLengthList)]
        return time_dependent_attribute_list

    def createTransitTrafficAttributeList(self, Scenario, linkComponentAttributeList):
        transit_traffic_attribute_list = []
        for transit_traffic_att in linkComponentAttributeList:
            attribute_at = Scenario.extra_attribute(transit_traffic_att)
            if attribute_at is not None:
                if attribute_at.type != "LINK":
                    raise Exception("Attribute '%s' is not a link type attribute" % transit_traffic_att)
                Scenario.delete_extra_attribute(attribute_at)
            t_traffic_attribute = Scenario.create_extra_attribute("LINK", transit_traffic_att, default_value=0.0)
            transit_traffic_attribute_list.append(t_traffic_attribute)
        return transit_traffic_attribute_list

    def convertToRanges(self, range_str):
        """
        This function converts a range string to a list of tuples of (start, end) pairs, inclusive, of ranges.

        Returns: list of tuples (start, end) inclusive
        """

        def process_term(term):
            parts = term.split("-")
            if len(parts) == 1:
                value = int(term)
                return (value, value)
            else:
                return (int(parts[0]), int(parts[1]))

        return [process_term(x) for x in range_str.split(",")]

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.get_progress()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg
