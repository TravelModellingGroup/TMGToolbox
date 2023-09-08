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
copy_attribute_tool = _MODELLER.tool("inro.emme.data.network.copy_attribute")


# import six library for python2 to python3 conversion
import six

# initalize python3 types
_util.initalizeModellerTypes(_m)


class CopyAttribute(_m.Tool()):
    version = "1.0.0"
    tool_run_msg = ""
    number_of_tasks = 4
    to_scenario_number = _m.Attribute(int)
    from_scenario_numbers = _m.Attribute(int)
    to_attribute = _m.Attribute(str)
    from_attribute = _m.Attribute(str)
    domain = _m.Attribute(str)
    node_selector = _m.Attribute(str)
    link_selector = _m.Attribute(str)
    transit_line_selector = _m.Attribute(str)
    incoming_link_selector = _m.Attribute(str)
    outgoing_link_selector = _m.Attribute(str)

    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        self.link = "LINK"
        self.node = "NODE"
        self.transit_line = "TRANSIT_LINE"
        self.turn = "TURN"
        self.transit_segment = "TRANSIT_SEGMENT"

    def page(self):
        pb = _m.ToolPageBuilder(
            self,
            title="Copy Attributes Between Scenarios",
            description="Cannot be called from Modeller.",
            runnable=False,
            branding_text="XTMF",
        )
        return pb.render()

    def __call__(
        self,
        to_scenario_number,
        from_scenario_numbers,
        to_attribute,
        from_attribute,
        domain,
        node_selector,
        link_selector,
        transit_line_selector,
        incoming_link_selector,
        outgoing_link_selector,
    ):
        to_scenario = _bank.scenario(to_scenario_number)
        from_scenario = _bank.scenario(from_scenario_numbers)
        if to_scenario is None:
            raise Exception("Scenario %s was not found!" % to_scenario_number)
        if from_scenario is None:
            raise Exception("Scenario %s was not found!" % from_scenario_numbers)

        try:
            self._execute(
                to_scenario,
                from_scenario,
                to_attribute,
                from_attribute,
                domain,
                node_selector,
                link_selector,
                transit_line_selector,
                incoming_link_selector,
                outgoing_link_selector,
            )
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(
        self,
        to_scenario,
        from_scenario,
        to_attribute,
        from_attribute,
        domain,
        node_selector,
        link_selector,
        transit_line_selector,
        incoming_link_selector,
        outgoing_link_selector,
    ):
        attribute_type = domain
        to_attribute = self._create_attributes_not_in_to_scenario(
            attribute_type, to_attribute, to_scenario
        )
        selection = self._create_selection_spec(
            domain,
            link_selector,
            node_selector,
            transit_line_selector,
            incoming_link_selector,
            outgoing_link_selector,
        )
        copy_attribute_tool(
            from_scenario=from_scenario,
            to_scenario=to_scenario,
            from_attribute_name=from_attribute,
            to_attribute_name=to_attribute,
            selection=selection,
        )

    def _create_selection_spec(
        self,
        domain,
        link_selector,
        node_selector,
        transit_line_selector,
        incoming_link_selector,
        outgoing_link_selector,
    ):
        if domain == self.link:
            return {"link": link_selector}
        elif domain == self.node:
            return {"node": node_selector}
        elif domain == self.transit_line:
            return {"transit_line": transit_line_selector}
        elif domain == self.turn:
            return {
                "incoming_link": incoming_link_selector,
                "outgoing_link": outgoing_link_selector,
            }
        elif domain == self.transit_segment:
            return {"link": link_selector, "transit_line": transit_line_selector}

    def _create_attributes_not_in_to_scenario(self, attrib_type, attribute, scenario):
        def check_att_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        att = attribute
        if attribute not in scenario.attributes(attrib_type):
            att = scenario.create_extra_attribute(
                attrib_type, check_att_name(attribute), default_value=0
            )
            print("attribute %s created" % attribute)

        return att

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.get_progress()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg
