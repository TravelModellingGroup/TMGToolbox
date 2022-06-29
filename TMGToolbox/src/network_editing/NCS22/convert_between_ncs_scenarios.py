# ---LICENSE----------------------
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

import inro.modeller as _m
import csv
import traceback as _traceback
from contextlib import contextmanager
_MODELLER = _m.Modeller()
_bank = _MODELLER.emmebank
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

class ConvertBetweenNCSScenarios(_m.Tool()):
    version = "0.0.1"
    number_of_tasks = 1
    tool_run_msg = ""

    #Emme modeller gui input parameters
    OldNcsScenario = _m.Attribute(_m.InstanceType)
    NewNcsScenario = _m.Attribute(_m.InstanceType)
    StationCentroidFile = _m.Attribute(str)
    ZoneCentroidFile = _m.Attribute(str)
    ModeCodeDefinitionsFile = _m.Attribute(str)
    LinkAttributesFile  = _m.Attribute(str)
    TransitVehicleDefinitionsFile = _m.Attribute(str)
    LaneCapacitiesFile = _m.Attribute(str)
    TransitLineCodeFile = _m.Attribute(str)
    SkipMissingTransitLines = _m.Attribute(bool)
    
    def __init__(self):
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(
            self, 
            title="Convert Network v%s" %self.version,
            description="Converts a network from NCS16 to the NCS22 standard.",
            branding_text="- TMG Toolbox 2")
            
        if self.tool_run_msg != "":  # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        # add the inputs to the page
        pb.add_select_scenario(
            tool_attribute_name="OldNcsScenario",
            title="Old NCS Scenario",
            allow_none=False
        )
        pb.add_select_scenario(
            tool_attribute_name="NewNcsScenario",
            title="New NCS Scenario",
            allow_none=False
        )
        pb.add_select_file(
            tool_attribute_name="StationCentroidFile",
            window_type="file",
            title="Station Centroid File CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="ZoneCentroidFile",
            window_type="file",
            title="Zone Centroid CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="ModeCodeDefinitionsFile",
            window_type="file",
            title="Mode Code Definitions CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="LinkAttributesFile",
            window_type="file",
            title="Link Attributes CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="TransitVehicleDefinitionsFile",
            window_type="file",
            title="Transit Vehicle Definitions CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="LaneCapacitiesFile",
            window_type="file",
            title="Lane Capacities CSV File Location",
        )
        pb.add_select_file(
            tool_attribute_name="TransitLineCodeFile",
            window_type="file",
            title="Transit LineCode CSV File Location",
        )
        pb.add_checkbox(
            tool_attribute_name="SkipMissingTransitLines",
            label="Boolean to skip missing transit lines default is True",
        )
        return pb.render()

    @_m.method(return_type=str)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    def run(self):
        """
        method to run the tool using the Emme modeller GUI
        """
        self.tool_run_msg = ""
        self.TRACKER.reset()

        # build the data as a python dictionary
        scenario = _MODELLER.emmebank.scenario(self.OldNcsScenario)
        parameters = {
                "old_ncs_scenario": _MODELLER.emmebank.scenario(self.OldNcsScenario),
                "new_ncs_scenario": _MODELLER.emmebank.scenario(self.NewNcsScenario),
                "station_centroid_file": self.StationCentroidFile,
                "zone_centroid_file": self.ZoneCentroidFile,
                "mode_code_definitions": self.ModeCodeDefinitionsFile,
                "link_attributes": self.LinkAttributesFile,
                "transit_vehicle_definitions": self.TransitVehicleDefinitionsFile,
                "lane_capacities": self.LaneCapacitiesFile,
                "transit_line_codes": self.TransitLineCodeFile,
                "skip_missing_transit_lines": self.SkipMissingTransitLines
            }

        try:
            self._execute(scenario, parameters)
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc())
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Tool is completed.")
        
    def __call__(self, parameters):
        scenario = _util.load_scenario(parameters["old_ncs_scenario"])
        try:
            self._execute(scenario, parameters)
        except Exception as e:
            raise Exception(_util.format_reverse_stack())

        self.tool_run_msg = _m.PageBuilder.format_info("Tool is completed.")

    def run_xtmf(self, parameters):
        old_ncs_scenario = _util.load_scenario(parameters["old_ncs_scenario"])
        try:
            self._execute(old_ncs_scenario, parameters)
        except Exception as e:
            raise Exception(_util.format_reverse_stack())

    def _execute(self, old_ncs_scenario, parameters):
        centroid_dict = self.create_mapped_centroid_dict(parameters)
        network = old_ncs_scenario.get_network()
        # Conversion Steps
        print("Updating zone and station centroids")
        self.update_zone_centroid_numbers(network, centroid_dict)
        print("Updating mode code definition...")
        self.update_mode_code_definitions(parameters, network)
        self.update_extra_attributes(old_ncs_scenario, "LINK", parameters["link_attributes"])
        print("Updating transit vehicle definition...")
        self.update_transit_vehicle_definitions(parameters, network)
        self.update_lane_capacity(parameters, network)
        print("Updating transit line codes")
        self.update_transit_line_codes(parameters, network)
        # Copy scenario and write a new updated network
        print("Started copying %s into %s" % (parameters["old_ncs_scenario"], parameters["new_ncs_scenario"]))
        self.copy_ncs_scenario(parameters, network, title="GTAModel - NCS22")
        print(
            "Done! Scenario %s has an updated network with the most recent network coding standard." % old_ncs_scenario
        )

    def update_zone_centroid_numbers(self, network, centroid_dict):
        nodes_list = []
        for item in network.nodes():
            nodes_list.append(int(item))
        max_node_number = max(nodes_list) + 1
        for old_centroid in centroid_dict:
            centroid_to_update = network.node(old_centroid)
            if centroid_to_update is not None:
                centroid_to_update.number = old_centroid + max_node_number
        for old_centroid_node in centroid_dict:
            centroid_to_update = network.node(old_centroid_node + max_node_number)
            if centroid_to_update is not None:
                centroid_to_update.number = centroid_dict[old_centroid_node]

    def copy_ncs_scenario(self, parameters, network, title="New_NCS_Scenario"):
        new_ncs_scenario = _bank.scenario(parameters["new_ncs_scenario"])
        if new_ncs_scenario != None:
            _bank.delete_scenario(new_ncs_scenario)
        new_ncs_scenario = _bank.copy_scenario(parameters["old_ncs_scenario"], parameters["new_ncs_scenario"])
        new_ncs_scenario.publish_network(network, resolve_attributes=True)
        new_ncs_scenario.title = str(title)
        return new_ncs_scenario

    def update_centroid_lists_with_zone_centroids(self, parameters, old_centroid_list, new_centroid_list):
        with self.open_csv_reader(parameters["zone_centroid_file"]) as zone_centroid_file:
            for centroid_range in zone_centroid_file:
                old_centroid_starts = int(centroid_range[1].strip())
                old_centroid_ends = int(centroid_range[2].strip())
                new_centroid_starts = int(centroid_range[3].strip())
                new_centroid_ends = int(centroid_range[4].strip())
                old_centroid_range = range(old_centroid_starts, old_centroid_ends + 1)
                new_centroid_range = range(new_centroid_starts, new_centroid_ends + 1)
                for centroid in old_centroid_range:
                    old_centroid_list.append(centroid)
                for centroid in new_centroid_range:
                    new_centroid_list.append(centroid)

    def update_centroid_lists_with_station_centroids(self, parameters, old_centroid_list, new_centroid_list):
        with self.open_csv_reader(parameters["station_centroid_file"]) as station_centroid_file:
            for centroid in station_centroid_file:
                old_station_centroid = int(centroid[2].strip())
                new_station_centroid = int(centroid[3].strip())
                if old_station_centroid <= 0 or new_station_centroid <= 0:
                    continue
                old_centroid_list.append(old_station_centroid)
                new_centroid_list.append(new_station_centroid)

    def create_mapped_centroid_dict(self, parameters):
        centroid_dict = {}
        old_centroid_list = []
        new_centroid_list = []
        self.update_centroid_lists_with_zone_centroids(parameters, old_centroid_list, new_centroid_list)
        self.update_centroid_lists_with_station_centroids(parameters, old_centroid_list, new_centroid_list)
        for old_centroid in old_centroid_list:
            old_centroids = old_centroid_list.index(old_centroid)
            centroid_dict[old_centroid] = new_centroid_list[old_centroids]
        return centroid_dict

    def update_mode_code_definitions(self, parameters, network):
        with self.open_csv_reader(parameters["mode_code_definitions"]) as mode_code_file:
            for mode_list in mode_code_file:
                old_mode_id = str(mode_list[2])
                if old_mode_id == "":
                    continue
                for mode in network.modes():
                    if str(mode.id) == old_mode_id:
                        description = str(mode_list[0])
                        mode_type = str(mode_list[1].strip())
                        new_mode_id = str(mode_list[3].strip())
                        mode.id = new_mode_id
                        if mode.type != mode_type:
                            raise Exception('There is an issue with mode type "%s"' % mode_list)
                        # Emme allows description of the mode, up to 10 characters.
                        mode.description = description[:10]

    def update_extra_attributes(self, scenario, attribute_type, attributes_file_name, default_value=0):
        attribute_type = self.check_attribute_type(attribute_type)
        with self.open_csv_reader(attributes_file_name) as attributes_file:
            for attrib_list in attributes_file:
                new_attribute_id = str(attrib_list[0].strip())
                new_description = str(attrib_list[1])
                if not new_attribute_id.startswith("@"):
                    new_attribute_id = "@" + new_attribute_id
                checked_extra_attribute = scenario.extra_attribute(new_attribute_id)
                if checked_extra_attribute == None:
                    new_attribute = scenario.create_extra_attribute(attribute_type, new_attribute_id, default_value)
                    # maximum length of description is 40 characters
                    new_attribute.description = new_description[:40]
                elif checked_extra_attribute != None and checked_extra_attribute.type != attribute_type:
                    raise Exception("Attribute %s already exist or has some issues!" % new_attribute_id)
                else:
                    continue

    def check_attribute_type(self, attribute_type):
        ATTRIBUTE_TYPES = ["NODE", "LINK", "TURN", "TRANSIT_LINE", "TRANSIT_SEGMENT"]
        attribute_type = str(attribute_type).upper()
        # check if the type provided is correct
        if attribute_type not in ATTRIBUTE_TYPES:
            raise TypeError("Attribute type '%s' provided is not recognized." % attribute_type)
        return attribute_type

    # code for transit vehicle changes
    def filter_mode(self, value, network):
        """
        extract the id of the vehicles from the transit vehicles list
        this is used to filter the transit vehicle to change the data
        """
        for i in network.transit_vehicles():
            if value == i.description:
                return i.id
        return None

    def copy_data(self, id, code, seated_capacity, total_capacity, auto_equivalent, network):
        """
        function to change the value and convert the ncs16 standard to ncs22.
        """
        # first extract the transit vehicle object using the id
        vehicle_object = network.transit_vehicle(int(id))
        # change the values of the vehicle object
        vehicle_object.description = code
        vehicle_object.seated_capacity = int(seated_capacity)
        vehicle_object.total_capacity = int(total_capacity)
        vehicle_object.auto_equivalent = float(auto_equivalent)

    def update_transit_vehicle_definitions(self, parameters, network):
        """
        function to read the csv file
        it also runs the copy_data() method to change the traffic vehicle data
        """
        with self.open_csv_reader(parameters["transit_vehicle_definitions"]) as transit_op_file:
            for item in transit_op_file:
                # get the vehicle id using the ncs16 standard code
                id = self.filter_mode(item[1].strip(), network)
                # run the copy_data function to change the data
                self.copy_data(
                    id=id,
                    code=item[6].strip(),
                    seated_capacity=item[8].strip(),
                    total_capacity=item[9].strip(),
                    auto_equivalent=item[10].strip(),
                    network=network,
                )

    def update_lane_capacity(self, parameters, network):
        with self.open_csv_reader(parameters["lane_capacities"]) as lane_capacity_file:
            for line in lane_capacity_file:
                vdf = int(line[0].strip())
                new_lane_capacity = int(line[1].strip())
                for link in network.links():
                    volume_delay_func = int(link.volume_delay_func)
                    if vdf == volume_delay_func:
                        link.data3 = new_lane_capacity

    def update_transit_line_codes(self, parameters, network):
        """
        Function to update the transit line codes
        """
        with self.open_csv_reader(parameters["transit_line_codes"]) as transit_line_file:
            for item in transit_line_file:
                # get the nc16 transit line object id
                transit_line_object = network.transit_line(item[0])
                # check if the transit line object is None, if it is None give the user an error
                if transit_line_object is not None:
                    # change the transit line object id to ncs22
                    transit_line_object.id = item[1]
                elif not parameters["skip_missing_transit_lines"]:
                    raise Exception("The transit line object {} doesn't exist".format(item[0]))

    @contextmanager
    def open_csv_reader(self, file_path):
        csv_file = open(file_path, mode="r")
        file = csv.reader(csv_file)
        next(file)
        try:
            yield file
        finally:
            csv_file.close()

