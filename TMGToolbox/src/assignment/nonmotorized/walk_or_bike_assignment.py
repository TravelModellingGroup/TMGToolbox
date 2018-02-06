from multiprocessing import cpu_count
from contextlib import contextmanager
import traceback as _traceback

import inro.modeller as m
mm = m.Modeller()
utils = mm.module('tmg.common.utilities')


class WalkOrBikeAssignment(m.Tool()):
    tool_run_msg = ""

    AssignmentModes = m.Attribute(m.ListType)
    DemandMatrixID = m.Attribute(str)
    TimeSkimMatrixID = m.Attribute(str)
    Scenario = m.Attribute(m.InstanceType)
    NCpus = m.Attribute(int)
    ClassName = m.Attribute(str)
    VolumeAttribute = m.Attribute(str)

    xtmf_ScenarioId = m.Attribute(int)
    xtmf_AssignmentModes = m.Attribute(str)
    xtmf_DemandMatrixNumber = m.Attribute(int)

    number_of_tasks = 3  # For progress reporting, enter the integer number of tasks here

    def __init__(self):
        self.TRACKER = utils.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker
        self.Scenario = mm.scenario
        self.AssignmentModes = [mode.id for mode in mm.scenario.modes() if mode.type == 'AUX_TRANSIT']
        self.NCpus = cpu_count()
        self.ClassName = "walk_only_assignment"

    def page(self):
        pb = m.ToolPageBuilder(self, title="Walk or Bike Assignment",
                               description="Runs an Extended Transit Assignment on aux. transit modes only. Optionally"
                                           " skims the time into a matrix. Optionally saves the assigned demand to a "
                                           "link extra attribute.",
                               branding_text="- TMG Toolbox")

        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario("Scenario", title="Scenario", note="Scenario in which to run the assignment")

        pb.add_select_matrix("DemandMatrixID", allow_none=True, id=True,
                             title="Demand matrix", note="Can be blank, in which case a demand of 0 is used")

        pb.add_select("AssignmentModes", keyvalues=self.populate_mode_list(), title="Assignment modes")

        with pb.section("Outputs"):
            pb.add_select_matrix("TimeSkimMatrixID", allow_none=True, id=True,
                                 title="Time skim matrix", note="If left blank, no skim matrix will be generated")

            pb.add_text_box("VolumeAttribute", size=20,
                            title="Volume attribute", note="Link extra attribute in which to save assigned volumes. "
                                                           "If blank, volumes are <b>not saved in volax</b>.")

        pb.add_text_box("ClassName", title="Class name", size=50)

        cpu_range = reversed(range(1, cpu_count() + 1))
        pb.add_select("NCpus", title="Number of threads", keyvalues=[(n, str(n)) for n in cpu_range])

        pb.add_html("""
        <script type="text/javascript">
            $(document).ready( function ()
            {        
                var tool = new inro.modeller.util.Proxy(%s) ;
                $("#Scenario").bind('change', function()
                {
                    $(this).commit();
                    $("#AssignmentModes")
                        .empty()
                        .append(tool.populate_mode_list(true))
                        .trigger('change');
                });
            });
        </script>""" % pb.tool_proxy_tag)

        return pb.render()

    @m.method(argument_types=[bool], return_type=unicode)
    def populate_mode_list(self, as_html=False):
        allowed_modes = []
        for mode in self.Scenario.modes():
            if mode.type != 'AUX_TRANSIT': continue

            text = "%s - %s - %s" % (mode.id, mode.description, mode.speed)
            item = (mode.id, text)
            if as_html:
                item = "<option value='%s'>%s</option>" % item
            allowed_modes.append(item)

        if not as_html: return allowed_modes
        return "\n".join(allowed_modes)

    def run(self):
        self.tool_run_msg = ""
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise

        self.tool_run_msg = m.PageBuilder.format_info("Script execution complete.")

    def __call__(self, xtmf_AssignmentModes, xtmf_DemandMatrixNumber, TimeSkimMatrixID, xtmf_ScenarioId, NCpus,
                 ClassName, VolumeAttribute):
        self.AssignmentModes = list(xtmf_AssignmentModes)
        self.DemandMatrixID = xtmf_DemandMatrixNumber if xtmf_DemandMatrixNumber > 0 else None
        self.TimeSkimMatrixID = TimeSkimMatrixID if TimeSkimMatrixID > 0 else None
        self.Scenario = mm.emmebank.scenario(xtmf_ScenarioId)
        self.NCpus = NCpus if NCpus > 0 else cpu_count()
        self.ClassName = ClassName
        self.VolumeAttribute = VolumeAttribute

        self._execute()

    @m.logbook_trace(name="Walk or bike assignment")
    def _execute(self):
        self.TRACKER.reset()
        assert self.Scenario is not None
        assert len(self.AssignmentModes) > 0, "No assignment modes were provided"
        assert all(self.Scenario.mode(mode).type == "AUX_TRANSIT" for mode in self.AssignmentModes), \
            "All assigned modes must be auxiliary transit"

        with self._demand_manager() as demand_mid:
            self._do_assignment(demand_mid)
            self.TRACKER.completeTask()

            if self.TimeSkimMatrixID is not None:
                utils.initializeMatrix(self.TimeSkimMatrixID)
                self._extract_time_skim()
            self.TRACKER.completeTask()

            if self.VolumeAttribute:  # Deliberately allow None and '' to be false-y

                # Init the extra attribute
                attr = self.Scenario.extra_attribute(self.VolumeAttribute)
                if attr is None:
                    attr = self.Scenario.create_extra_attribute('LINK', self.VolumeAttribute)
                else:
                    attr.initialize()
                attr.description = "Volumes from '%s' assignment" % self.ClassName

                self._save_volumes(demand_mid)
            self.TRACKER.completeTask()

    @contextmanager
    def _demand_manager(self):
        if self.DemandMatrixID is not None:
            try: yield self.DemandMatrixID
            finally: pass
        else:
            with utils.tempMatrixMANAGER(matrix_type='SCALAR', description='Temp walk or bike demand') as item:
                yield item.id

    def _do_assignment(self, demand_mid):
        spec = {
            "modes": sorted(self.AssignmentModes),
            "demand": demand_mid,
            "waiting_time": {
                "headway_fraction": 0.5,
                "effective_headways": "hdw",
                "spread_factor": 1,
                "perception_factor": 1
            },
            "boarding_time": {
                "global": {
                    "penalty": 0,
                    "perception_factor": 1
                },
                "at_nodes": None,
                "on_lines": None,
                "on_segments": None
            },
            "boarding_cost": {
                "global": {
                    "penalty": 0,
                    "perception_factor": 1
                },
                "at_nodes": None,
                "on_lines": None,
                "on_segments": None
            },
            "in_vehicle_time": {
                "perception_factor": 1
            },
            "in_vehicle_cost": None,
            "aux_transit_time": {
                "perception_factor": 1
            },
            "aux_transit_cost": None,
            "flow_distribution_at_origins": {
                "choices_at_origins": "OPTIMAL_STRATEGY",
                "fixed_proportions_on_connectors": None
            },
            "flow_distribution_at_regular_nodes_with_aux_transit_choices": {
                "choices_at_regular_nodes": "OPTIMAL_STRATEGY"
            },
            "flow_distribution_between_lines": {
                "consider_total_impedance": False
            },
            "connector_to_connector_path_prohibition": None,
            "od_results": {
                "total_impedance": None
            },
            "journey_levels": [],
            "performance_settings": {
                "number_of_processors": self.NCpus
            },
            "type": "EXTENDED_TRANSIT_ASSIGNMENT"
        }

        ts = self.Scenario.transit_strategies
        if ts.strat_file(self.ClassName) is not None:
            ts.delete_strat_file(self.ClassName)

        print "Running walk-all-way assignment"
        mm.tool('inro.emme.transit_assignment.extended_transit_assignment'
                )(spec, scenario=self.Scenario, add_volumes=False, save_strategies=True, class_name=self.ClassName)

    def _extract_time_skim(self):
        spec = {
            "by_mode_subset": {
                "modes": sorted(self.AssignmentModes),
                "actual_aux_transit_times": self.TimeSkimMatrixID
            },
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS"
        }

        print "Extracting walk time matrix"
        mm.tool('inro.emme.transit_assignment.extended.matrix_results'
                )(spec, self.Scenario, self.ClassName, self.NCpus)

    def _save_volumes(self, demand_mid):
        spec = {
            "on_links": {
                "aux_transit_volumes": self.VolumeAttribute
            },
            "on_segments": None,
            "aggregated_from_segments": None,
            "analyzed_demand": demand_mid,
            "constraint": None,
            "type": "EXTENDED_TRANSIT_NETWORK_RESULTS"
        }
        mm.tool('inro.emme.transit_assignment.extended.network_results')(
            spec, self.Scenario, self.ClassName, self.NCpus)

    @m.method(return_type=m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
