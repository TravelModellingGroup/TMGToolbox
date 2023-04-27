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

import inro.modeller as _m

_MODELLER = _m.Modeller()
_util = _MODELLER.module("tmg.common.utilities")
_geolib = _MODELLER.module("tmg.common.geometry")
_bank = _MODELLER.emmebank
_write = _m.logbook_write
_trace = _m.logbook_trace
Shapely2ESRI = _geolib.Shapely2ESRI
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
    ToScenarioNumber = _m.Attribute(int)
    FromScenarioNumbers = _m.Attribute(str)
    LinkComponentAttribute = _m.Attribute(str)
    AttributeIndexRange = _m.Attribute(str)

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

    def __call__(self, ToScenarioNumber, FromScenarioNumbers, LinkComponentAttribute, AttributeIndexRange):
        ToScenario = _m.Modeller().emmebank.scenario(ToScenarioNumber)
        if ToScenario is None:
            raise Exception("Scenario %s was not found!" % ToScenarioNumber)
        FromScenarioList = []
        for scenarioNumber in [int(x) for x in FromScenarioNumbers.split(",")]:
            scenarioList = _m.Modeller().emmebank.scenario(scenarioNumber)
            if scenarioNumber is None:
                raise Exception("Scenario %s was not found!" % scenarioNumber)
            FromScenarioList.append(scenarioList)
        try:
            self._execute(ToScenario, FromScenarioList, LinkComponentAttribute, AttributeIndexRange)
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(self, ToScenario, FromScenarioList, LinkComponentAttribute, AttributeIndexRange):
        timeDependentComponentAttributeList = self._createTimeDependentAttributeList(LinkComponentAttribute, AttributeIndexRange)
        ToNetwork = ToScenario.get_network()
        attribute_in_from = self._createAttributesNotInToScenario("LINK", ToNetwork, ToScenario, FromScenarioList, timeDependentComponentAttributeList)
        self._copyAttributesBetweenScenarions("LINK", attribute_in_from, ToScenario, FromScenarioList)

    def _createAttributesNotInToScenario(self, attrib_type, ToNetwork, ToScenario, FromScenarioList, timeDependentComponentAttributeList):
        attribute_in_from = []
        for from_scenario in FromScenarioList:
            attributeList = from_scenario.attributes(attrib_type)
            for attribute in attributeList:
                if attribute in timeDependentComponentAttributeList:
                    attribute_in_from.append(attribute)
                    if attribute not in ToScenario.attributes(attrib_type):
                        ToScenario.create_extra_attribute(attrib_type, attribute, default_value=0)
                        print("attribute %s created" % attribute)
        for attrib in attribute_in_from:
            if attrib not in ToNetwork.attributes("LINK"):
                ToNetwork.create_attribute("LINK", attrib, default_value=0)
        return attribute_in_from

    def _copyAttributesBetweenScenarions(self, attrib_type, attribute_in_from, ToScenario, FromScenarioList):
        ToNetwork = ToScenario.get_network()
        for from_scenario in FromScenarioList:
            from_network = from_scenario.get_network()
            attributeList = from_scenario.attributes(attrib_type)
            attrib_in_from_scenario = [attrib for attrib in attributeList if attrib in attribute_in_from]
            for from_link in from_network.links():
                to_link = ToNetwork.link(from_link.i_node.id, from_link.j_node.id)
                if to_link is not None:
                    for attrib in attrib_in_from_scenario:
                        to_link[attrib] = from_link[attrib]
            print("Done copying attributes from scenario %s" % from_scenario)
        ToScenario.publish_network(ToNetwork)

    def _createTimeDependentAttributeList(self, LinkComponentAttribute, AttributeIndexRange):
        def check_att_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        attributeRangeList = self._createRangeList(AttributeIndexRange)
        time_dependent_attribute_list = [check_att_name(LinkComponentAttribute) + str(i) for i in attributeRangeList]
        return time_dependent_attribute_list

    def _createRangeList(self, indexRanges):
        result = []
        for part in indexRanges.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                result.extend(range(start, end + 1))
            else:
                result.append(int(part))
        return result

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.get_progress()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg
