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
        self.link = 0
        self.node = 1
        self.transit_line = 2
        self.turn = 3
        self.transit_segment = 4

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

        if domain == self.link:
            self.node_selector = None
            self.transit_line_selector = None
            self.incoming_link_selector = None
            self.outgoing_link_selector = None
            self.link_selector = link_selector
        elif domain == self.node:
            self.link_selector = None
            self.transit_line_selector = None
            self.incoming_link_selector = None
            self.outgoing_link_selector = None
            self.node_selector = node_selector
        elif domain == self.transit_line:
            self.link_selector = None
            self.node_selector = None
            self.incoming_link_selector = None
            self.outgoing_link_selector = None
            self.transit_line_selector = transit_line_selector
        elif domain == self.turn:
            self.link_selector = None
            self.node_selector = None
            self.transit_line_selector = None
            self.incoming_link_selector = incoming_link_selector
            self.outgoing_link_selector = outgoing_link_selector
        elif domain == self.transit_segment:
            self.node_selector = None
            self.incoming_link_selector = None
            self.outgoing_link_selector = None
            self.link_selector = link_selector
            self.transit_line_selector = transit_line_selector

        try:
            self._execute(
                to_scenario, from_scenario, to_attribute, from_attribute, domain
            )
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(
        self, to_scenario, from_scenario, to_attribute, from_attribute, domain
    ):
        attribute_type = self._get_attribute_type(domain)
        to_attribute = self._create_attributes_not_in_to_scenario(
            attribute_type, to_attribute, to_scenario
        )
        selection = self._create_selection_spec()

        copy_attribute_tool(
            from_scenario=from_scenario,
            to_scenario=to_scenario,
            from_attribute_name=from_attribute,
            to_attribute_name=to_attribute.id,
            selection=selection,
        )

    def _create_selection_spec(self):
        selection = {
            "node": str(self.node_selector),
            "link": str(self.link_selector),
            "incoming_link": str(self.incoming_link_selector),
            "outgoing_link": str(self.outgoing_link_selector),
            "transit_line": str(self.transit_line_selector),
        }
        return selection

    def _create_attributes_not_in_to_scenario(self, attrib_type, attribute, scenario):
        def check_att_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        attribute_in_from = scenario.attributes(attrib_type)
        if attribute not in attribute_in_from:
            attribute_in_from = scenario.create_extra_attribute(
                attrib_type, check_att_name(attribute), default_value=0
            )
            print("attribute %s created" % attribute)

        return attribute_in_from

    def _get_attribute_type(self, domain):
        if domain == self.link:
            return "LINK"
        elif domain == self.node:
            return "NODE"
        elif domain == self.transit_line:
            return "TRANSIT_LINE"
        elif domain == self.turn:
            return "TURN"
        elif domain == self.transit_segment:
            return "TRANSIT_SEGMENT"

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.get_progress()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg
