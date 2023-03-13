"""
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
"""

# ---METADATA---------------------
"""
Add Transfer Adjustments

    Authors: James Vaughan

    Latest revision by: @jamesvaughan
    
    
    [Description]
    This tool is designed to take in a list of adjustments to apply to station zones where transfer
    links can be assigned travel times.  Those travel times are then implemented by
    extending the length of the transfer links so that the aux transit mode will take thgat given
    travel time to cross it.
        
"""
# ---VERSION HISTORY
"""
    0.1.0 Created.
    
"""

from logging import exception
import inro.modeller as _m
import traceback as _traceback
import math
_MODELLER = _m.Modeller()  # Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module("tmg.common.TMG_tool_page_builder")
# import six library for python2 to python3 conversion
import six
import json

# initialize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################


class AddTransferAdjustments(_m.Tool()):

    version = "0.1.0"
    tool_run_msg = ""

    parameters = _m.Attribute(str)

    def __init__(self):

        # ---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario  # Default is primary scenario

    def page(self):
        pb = _m.ToolPageBuilder(
            self,
            title="Add Transfer Adjustments",
            description="Cannot be called from Modeller.",
            runnable=False,
            branding_text="XTMF",
        )

        return pb.render()

    ##########################################################################################################

    def __call__(self, parameters):
        self.tool_run_msg = ""
        try:
            parameters = json.loads(parameters)
            self._Execute(parameters)
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc()
            )
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Done.")

    ##########################################################################################################

    def _Execute(self, parameters):
        # The parameters is a json object with three properties
        # 1) "stations" = an array of station node numbers
        # 2) "scenario" = a the scenario number to operate on
        # 3) "transfer_modes" = a list of modes that are considered transfers, a * means all modes
        with _m.logbook_trace(
            name="{classname} v{version}".format(
                classname=(self.__class__.__name__), version=self.version
            ),
            attributes=self._GetAtts(),
        ):
            # Load in the scenario
            scenario = self._load_scenario(parameters["scenario"])
            network = scenario.get_network()
            # Load the transfer modes
            transfer_modes = self._load_transfer_modes(
                parameters["transfer_modes"], network
            )
            # Adjust the scenario
            for station_adjustment in parameters["stations"]:
                station_number = station_adjustment["station_number"]
                transfer_time = station_adjustment["transfer_time"]
                self._apply_adjustment(
                    network, station_number, transfer_time, transfer_modes
                )

            # Write the modified network back out to the scenario
            scenario.publish_network(network)
        return

    def _load_scenario(self, scenario_number):
        return _MODELLER.emmebank.scenario(scenario_number)

    def _load_transfer_modes(self, transfer_modes, network):
        ret = []
        for mode in transfer_modes:
            # If we should get all modes
            if mode == "*":
                for x in network.modes():
                    if x.type == "AUX_TRANSIT":
                        ret.append(x)
            else:
                m = network.mode(mode)
                if m is None:
                    raise exception(
                        "The mode " + mode + " does not exist in the network!"
                    )
                elif m.type != "AUX_TRANSIT":
                    raise exception("The mode " + mode + " is not an AUX_TRANSIT mode!")
                ret.append(m)
        return ret

    def _apply_adjustment(self, network, station_number, transfer_time, transfer_modes):
        
        def get_transfer_mode(link, transfer_modes):
            modes = link.modes
            for m in transfer_modes:
                if m in modes:
                    return m
            return None
        
        def apply(links, transfer_modes, transfer_time):
            for link in links:
                mode = get_transfer_mode(link, transfer_modes)
                if mode is not None:
                    link.length = transfer_time * mode.speed
            return

        station_node = network.node(station_number)
        if station_node is None:
            raise "Unknown station node " + str(station_node)

        # We need to convert the transfer time into a fraction of an hour
        # so when it is multiplied by the speed in km/h we get our result in kms
        transfer_time /= 60.0
        # Apply for both incoming and outgoing links
        apply(station_node.incoming_links(), transfer_modes, transfer_time)
        apply(station_node.outgoing_links(), transfer_modes, transfer_time)
        return

    #########################################################################################################

    # ----SUB FUNCTIONS---------------------------------------------------------------------------------

    def _GetAtts(self):
        atts = {
            "Scenario": str(self.Scenario.id),
            "Version": self.version,
            "self": self.__MODELLER_NAMESPACE__,
        }
        return atts

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return 0.0

    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
