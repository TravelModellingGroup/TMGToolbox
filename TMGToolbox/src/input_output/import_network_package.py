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

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
import zipfile as _zipfile
from os import path as _path
import shutil as _shutil
import tempfile as _tf

_MODELLER = _m.Modeller()  # Instantiate Modeller once.
_bank = _MODELLER.emmebank
_util = _MODELLER.module('tmg.common.utilities')
_tmg_tpb = _MODELLER.module('tmg.common.TMG_tool_page_builder')
merge_functions = _MODELLER.tool('tmg.input_output.merge_functions')
import_modes = _MODELLER.tool('inro.emme.data.network.mode.mode_transaction')
import_vehicles = _MODELLER.tool('inro.emme.data.network.transit.vehicle_transaction')
import_base = _MODELLER.tool('inro.emme.data.network.base.base_network_transaction')
import_link_shape = _MODELLER.tool('inro.emme.data.network.base.link_shape_transaction')
import_lines = _MODELLER.tool('inro.emme.data.network.transit.transit_line_transaction')
import_turns = _MODELLER.tool('inro.emme.data.network.turn.turn_transaction')
import_attributes = _MODELLER.tool('inro.emme.data.network.import_attribute_values')


class ComponentContainer(object):
    """A simple data container. It's fully written out so I can get auto-completion"""
    def __init__(self):
        self.mode_file = None
        self.vehicles_file = None
        self.base_file = None
        self.lines_file = None
        self.turns_file = None
        self.shape_file = None
        self.functions_file = None

        self.attribute_header_file = None
        self.attribute_value_files = None

        self.traffic_results_files = None
        self.transit_results_files = None
        self.aux_transit_results_file = None

    def reset(self):
        self.mode_file = None
        self.vehicles_file = None
        self.base_file = None
        self.lines_file = None
        self.turns_file = None
        self.shape_file = None
        self.functions_file = None

        self.attribute_header_file = None
        self.attribute_value_files = None

        self.traffic_results_files = None
        self.transit_results_files = None


class ImportNetworkPackage(_m.Tool()):
    version = '1.2.0'
    tool_run_msg = ""
    number_of_tasks = 9  # For progress reporting, enter the integer number of tasks here

    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)

    ScenarioId = _m.Attribute(int)  # common variable or parameter
    NetworkPackageFile = _m.Attribute(str)
    ScenarioDescription = _m.Attribute(str)
    OverwriteScenarioFlag = _m.Attribute(bool)
    ConflictOption = _m.Attribute(str)

    def __init__(self):
        # ---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker

        # ---Set the defaults of parameters used by Modeller
        self.ScenarioDescription = ""
        self.OverwriteScenarioFlag = False
        self.ConflictOption = merge_functions.EDIT_OPTION
        self._components = ComponentContainer()

    def page(self):
        pb = _tmg_tpb.TmgToolPageBuilder(self, title="Import Network Package v%s" % self.version,
                                         description="Imports a new scenario from a compressed network package \
                             (*.nwp) file.",
                                         branding_text="- TMG Toolbox")

        if self.tool_run_msg != "":  # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_file(tool_attribute_name='NetworkPackageFile',
                           window_type='file',
                           title="Network Package File",
                           file_filter='*.nwp')

        pb.add_html("""<div class="t_element" id="NetworkPackageInfoDiv" style="padding: 0px inherit;">
        </div>""")

        pb.add_text_box(tool_attribute_name='ScenarioId',
                        size=4,
                        title="New Scenario Number",
                        note="Enter a new or existing scenario")
        '''
        pb.add_new_scenario_select(tool_attribute_name='ScenarioId',
                                  title="New Scenario Number",
                                  note="'Next' picks the next available scenario.")
        '''

        pb.add_text_box(tool_attribute_name='ScenarioDescription',
                        size=60,
                        title="Scenario description")

        pb.add_select(tool_attribute_name='ConflictOption',
                      keyvalues=merge_functions.OPTIONS_LIST,
                      title="Function Conflict Option",
                      note="Select an action to take if there are conflicts found \
                      between the package and the current Emmebank.")

        # ---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        $("#NetworkPackageFile").bind('change', function()
        {
            $(this).commit();
            
            //Change the scenario description
            $("#ScenarioDescription")
                .val(tool.get_description_from_file())
            $("#ScenarioDescription").trigger('change');
            
            //Change the package info
            var info = tool.get_file_info();
            $("#NetworkPackageInfoDiv").removeAttr( 'style' );
            $("#NetworkPackageInfoDiv").html(info);
                
        });
        
        //$(this).parent().siblings(".t_after_widget").html(s);
        
        $("#ScenarioId").bind('change', function()
        {
            $(this).commit();
            
            var toolNote = $(this).parent().siblings(".t_after_widget");
            
            if (tool.check_scenario_exists())
            {    
                //Scenario exists
                var h = "Scenario already exists. Overwrite? <input type='checkbox' id='ScenarioOverwrite' />"
                toolNote.html(h);
                
                $("#ScenarioOverwrite").prop('checked', false)
                    .bind('change', function()
                {
                    $(this).commit();
                    
                    if ($(this).prop('checked'))
                    {
                        tool.set_overwrite_scenario_flag_true();
                    } else {
                        tool.set_overwrite_scenario_flag_false();
                    }
                });
                
                $("#ScenarioDescription").val(tool.get_existing_scenario_title())
                                        .trigger('change');
                
            } else {
                toolNote.html("Select an existing or new scenario.");
            }
        });
        
        $("#ScenarioId").trigger('change');
    });
</script>""" % pb.tool_proxy_tag)

        return pb.render()

    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        if self.ScenarioId < 1:
            raise Exception("Scenario '%s' is not a valid scenario" % self.ScenarioId)

        if self.NetworkPackageFile is None:
            raise IOError("Import file not specified")

        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Done. Scenario %s created." % self.ScenarioId)

    def __call__(self, NetworkPackageFile, ScenarioId, ConflictOption):

        self.NetworkPackageFile = NetworkPackageFile
        self.ScenarioDescription = ""
        self.ScenarioId = ScenarioId
        self.OverwriteScenarioFlag = True
        self.ConflictOption = ConflictOption

        try:
            self._execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)

    def _execute(self):
        with _m.logbook_trace(
                name="{classname} v{version}".format(classname=self.__class__.__name__, version=self.version),
                attributes=self._get_logbook_attributes()):

            if _bank.scenario(self.ScenarioId) is not None and not self.OverwriteScenarioFlag:
                raise IOError("Scenario %s exists and overwrite flag is set to false." % self.ScenarioId)

            self._components.reset()  # Clear any held-over contents from previous run

            with _zipfile.ZipFile(self.NetworkPackageFile) as zf, self._temp_file() as temp_folder:

                self._check_network_package(zf)  # Check the file format.

                if _bank.scenario(self.ScenarioId) is not None:
                    if not self.OverwriteScenarioFlag:
                        raise IOError("Scenario %s already exists." % self.ScenarioId)
                    sc = _bank.scenario(self.ScenarioId)
                    if sc.modify_protected or sc.delete_protected:
                        raise IOError("Scenario %s is protected against modifications" % self.ScenarioId)
                    _bank.delete_scenario(self.ScenarioId)
                scenario = _bank.create_scenario(self.ScenarioId)
                scenario.title = self.ScenarioDescription

                _m.logbook_write("Created new scenario %s" % self.ScenarioId)
                self.TRACKER.completeTask()

                self._batchin_modes(scenario, temp_folder, zf)
                self._batchin_vehicles(scenario, temp_folder, zf)
                self._batchin_base(scenario, temp_folder, zf)
                self._batchin_link_shapes(scenario, temp_folder, zf)
                self._batchin_lines(scenario, temp_folder, zf)
                self._batchin_turns(scenario, temp_folder, zf)

                if self._components.traffic_results_files is not None:
                    self._batchin_traffic_results(scenario, temp_folder, zf)

                if self._components.transit_results_files is not None:
                    self._batchin_transit_results(scenario, temp_folder, zf)

                if self._components.attribute_header_file is not None:
                    self._batchin_extra_attributes(scenario, temp_folder, zf)
                self.TRACKER.completeTask()

                if self._components.functions_file is not None:
                    self._batchin_functions(temp_folder, zf)
                self.TRACKER.completeTask()

    @_m.logbook_trace("Reading modes")
    def _batchin_modes(self, scenario, temp_folder, zf):
        zf.extract(self._components.mode_file, temp_folder)
        self.TRACKER.runTool(import_modes,
                             transaction_file=_path.join(temp_folder, self._components.mode_file),
                             scenario=scenario)

    @_m.logbook_trace("Reading vehicles")
    def _batchin_vehicles(self, scenario, temp_folder, zf):
        zf.extract(self._components.vehicles_file, temp_folder)
        self.TRACKER.runTool(import_vehicles,
                             transaction_file=_path.join(temp_folder, self._components.vehicles_file),
                             scenario=scenario)

    @_m.logbook_trace("Reading base network")
    def _batchin_base(self, scenario, temp_folder, zf):
            zf.extract(self._components.base_file, temp_folder)
            self.TRACKER.runTool(import_base,
                                 transaction_file=_path.join(temp_folder, self._components.base_file),
                                 scenario=scenario)

    @_m.logbook_trace("Reading link shapes")
    def _batchin_link_shapes(self, scenario, temp_folder, zf):
        zf.extract(self._components.shape_file, temp_folder)
        self.TRACKER.runTool(import_link_shape,
                             transaction_file=_path.join(temp_folder, self._components.shape_file),
                             scenario=scenario)

    @_m.logbook_trace("Reading transit lines")
    def _batchin_lines(self, scenario, temp_folder, zf):
        zf.extract(self._components.lines_file, temp_folder)
        self.TRACKER.runTool(import_lines,
                             transaction_file=_path.join(temp_folder, self._components.lines_file),
                             scenario=scenario)

    @_m.logbook_trace("Reading turns")
    def _batchin_turns(self, scenario, temp_folder, zf):
        zf.extract(self._components.turns_file, temp_folder)
        self.TRACKER.runTool(import_turns,
                             transaction_file=_path.join(temp_folder, self._components.turns_file),
                             scenario=scenario)

    @_m.logbook_trace("Reading extra attributes")
    def _batchin_extra_attributes(self, scenario, temp_folder, zf):
        types = self._load_extra_attributes(zf, temp_folder, scenario)
        self.TRACKER.startProcess(len(types))
        for t in types:
            if t == "TRANSIT_SEGMENT":
                filename = "exatt_segments.241"
            else:            
                filename = "exatt_%ss.241" % t.lower()
            
            zf.extract(filename, temp_folder)
            import_attributes(file_path=_path.join(temp_folder, filename),
                              field_separator=",",
                              scenario=scenario)
            self.TRACKER.completeSubtask()

    def _batchin_functions(self, temp_folder, zf):
        zf.extract(self._components.functions_file, temp_folder)
        merge_functions.FunctionFile = _path.join(temp_folder, self._components.functions_file)
        merge_functions.ConflictOption = self.ConflictOption
        merge_functions.run()

    @_m.logbook_trace("Importing traffic results")
    def _batchin_traffic_results(self, scenario, temp_folder, zf):
        scenario.has_traffic_results = True

        links_filename, turns_filename = self._components.traffic_results_files
        zf.extract(links_filename, temp_folder); zf.extract(turns_filename, temp_folder)

        links_filepath = _path.join(temp_folder, links_filename)
        turns_filepath = _path.join(temp_folder, turns_filename)

        attribute_names = 'auto_volume', 'additional_volume', 'auto_time'

        index, _ = scenario.get_attribute_values('LINK', ['data1'])
        tables = []
        with _util.tempExtraAttributeMANAGER(scenario, 'LINK', returnId=True) as temp_attribute:
            column_labels = {0: 'i_node', 1: 'j_node'}
            for i, attribute_name in enumerate(attribute_names):
                column_labels[i + 2] = temp_attribute
                import_attributes(links_filepath, ',', column_labels, scenario=scenario)
                del column_labels[i + 2]

                _, table = scenario.get_attribute_values('LINK', [temp_attribute])
                tables.append(table)
        scenario.set_attribute_values('LINK', attribute_names, [index] + tables)

        index, _ = scenario.get_attribute_values('TURN', ['data1'])
        tables = []
        with _util.tempExtraAttributeMANAGER(scenario, 'TURN', returnId=True) as temp_attribute:
            column_labels = {0: 'i_node', 1: 'j_node', 2: 'k_node'}
            for i, attribute_name in enumerate(attribute_names):
                column_labels[i + 3] = temp_attribute
                import_attributes(turns_filepath, ',', column_labels, scenario=scenario)
                del column_labels[i + 3]

                _, table = scenario.get_attribute_values('TURN', [temp_attribute])
                tables.append(table)
        scenario.set_attribute_values('TURN', attribute_names, [index] + tables)

    @_m.logbook_trace("Importing transit results")
    def _batchin_transit_results(self, scenario, temp_folder, zf):
        scenario.has_transit_results = True

        segments_filename = self._components.transit_results_files
        zf.extract(segments_filename, temp_folder)
        segments_filepath = _path.join(temp_folder, segments_filename)

        attribute_names = ['transit_boardings', 'transit_time', 'transit_volume']
        index, _ = scenario.get_attribute_values('TRANSIT_SEGMENT', ['data1'])
        tables = []
        with _util.tempExtraAttributeMANAGER(scenario, 'TRANSIT_SEGMENT', returnId=True) as temp_attribute:
            column_labels= {0: 'line', 1: 'i_node', 2: 'j_node', 3: 'loop_idx'}
            for i, attribute_name in enumerate(attribute_names):
                column_labels[i + 4] = temp_attribute
                import_attributes(segments_filepath, ',', column_labels, scenario=scenario)
                del column_labels[i + 4]

                _, table = scenario.get_attribute_values('TRANSIT_SEGMENT', [temp_attribute])
                tables.append(table)
        scenario.set_attribute_values('TRANSIT_SEGMENT', attribute_names, [index] + tables)

        # Technically, a file generated by 'export_network_package.py' should already have this file so long as there
        # are transit results. However, some older versions of the tool do NOT have this feature, but can actually have
        # transit results. So this conditional exists for backwards-compatibility.
        if self._components.aux_transit_results_file is not None:
            aux_transit_filename = self._components.aux_transit_results_file
            zf.extract(aux_transit_filename,temp_folder)
            aux_transit_filepath = _path.join(temp_folder, aux_transit_filename)

            aux_attribute_names = ['aux_transit_volume']
            index, _ = scenario.get_attribute_values('LINK', ['data1'])

            tables = []
            with _util.tempExtraAttributeMANAGER(scenario, 'LINK', returnId=True) as temp_attribute:
                column_labels = {0:  'i_node', 1: 'j_node'}
                for i, attribute_name in enumerate(aux_attribute_names):
                    column_labels[i + 2] = temp_attribute
                    import_attributes(aux_transit_filepath, ',', column_labels, scenario=scenario)
                    del column_labels[i + 2]

                    _, table = scenario.get_attribute_values('LINK', [temp_attribute])
                    tables.append(table)
            scenario.set_attribute_values('LINK', aux_attribute_names, [index] + tables)

    @contextmanager
    def _temp_file(self):
        foldername = _tf.mkdtemp()
        _m.logbook_write("Created temporary directory at '%s'" % foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            _m.logbook_write("Deleted temporary directory at '%s'" % foldername)

    def _check_network_package(self, package):
        """"""

        '''
        This method reads the NWP's version number and sets up the list of
        component files to extract. It also handles backwards compatibility.
        '''

        contents = package.namelist()
        if 'version.txt' in contents:
            (self._components.mode_file, self._components.vehicles_file, self._components.base_file,
             self._components.lines_file, self._components.turns_file, self._components.shape_file) = (
                'modes.201', 'vehicles.202', 'base.211', 'transit.221', 'turns.231', 'shapes.251'
            )

            vf = package.open('version.txt')
            version = float(vf.readline())

            if version >= 3:
                self._components.functions_file = 'functions.411'

            if 'link_results.csv' in contents and 'turn_results.csv' in contents:
                self._components.traffic_results_files = 'link_results.csv', 'turn_results.csv'

            if 'segment_results.csv' in contents:
                self._components.transit_results_files = 'segment_results.csv'

            if 'aux_transit_results.csv' in contents:
                self._components.aux_transit_results_file = 'aux_transit_results.csv'

            if "exatts.241" in contents:
                self._components.attribute_header_file = "exatts.241"


            return version

        renumber_count = 0
        for component in contents:
            if component.endswith(".201"):
                self._components.mode_file = component
                renumber_count += 1
            elif component.endswith(".202"):
                self._components.vehicles_file = component
                renumber_count += 1
            elif component.endswith(".211"):
                self._components.base_file = component
                renumber_count += 1
            elif component.endswith(".221"):
                self._components.lines_file = component
                renumber_count += 1
            elif component.endswith(".231"):
                self._components.turns_file = component
                renumber_count += 1
            elif component.endswith(".251"):
                self._components.shape_file = component
                renumber_count += 1
        if renumber_count != 6:
            raise IOError("File appears to be missing some components. Please contact TMG for assistance.")

        return 1.0

    def _get_logbook_attributes(self):
        atts = {
            "Scenario": self.ScenarioId,
            "Import File": self.NetworkPackageFile,
            "Version": self.version,
            "self": self.__MODELLER_NAMESPACE__}

        return atts

    def _load_extra_attributes(self, zf, temp_folder, scenario):
        zf.extract(self._components.attribute_header_file, temp_folder)
        types = set()
        with open(_path.join(temp_folder, self._components.attribute_header_file)) as reader:
            reader.readline()  # toss first line
            for line in reader.readlines():
                cells = line.split(',', 3)
                if len(cells) >= 3:
                    att = scenario.create_extra_attribute(cells[1], cells[0], default_value=float(cells[2]))
                    att.description = cells[3].strip().strip("'")
                    # strip called twice: once to remove the '\n' character, and once to remove both ' characters
                    types.add(att.type)
        return types

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    @_m.method(return_type=unicode)
    def get_description_from_file(self):
        if self.NetworkPackageFile:
            if not self.ScenarioDescription:
                return _path.splitext(_path.basename(self.NetworkPackageFile))[0]
            else:
                return self.ScenarioDescription

    @_m.method(return_type=unicode)
    def get_file_info(self):
        with _zipfile.ZipFile(self.NetworkPackageFile) as zf:
            nl = zf.namelist()
            if 'version.txt' in nl:
                vf = zf.open('version.txt')
                version = float(vf.readline())
            else:
                return (r"<table border='1' width='90&#37'><tbody><tr><td valign='top'><b>NWP Version:</b> 1.0</td>" +
                        r"<tr></tbody></table>")

            if 'info.txt' not in nl:
                return r"<table border='1' width='90&#37'><tbody><tr><td valign='top'><b>NWP Version:</b>" + \
                       " %s</td><tr></tbody></table>" % version

            info = zf.open('info.txt')
            lines = info.readlines()
            '''
            Lines = [Project Name,
                    Project Path,
                    Scenario Title
                    Export Date
                    subsequent comment lines]
            '''
            package_version = "<b>NWP Version:</b> %s" % version
            project_name = "<b>Project:</b> %s" % lines[0].strip()
            scenario_title = "<b>Scenario:</b> %s" % lines[2].strip()
            export_date = "<b>Export Date:</b> %s" % lines[3].strip()
            comment_lines = ["<b>User Comments:</b>"] + [l.strip() for l in lines[4:]]
            html_lines = [package_version, project_name, scenario_title, export_date, ''] + comment_lines
            cell = "<br>".join(html_lines)

            return "<table border='1' width='90&#37'><tbody><tr><td valign='top'>%s</td></tr></tbody></table>" % cell

    @_m.method()
    def set_overwrite_scenario_flag_true(self):
        self.OverwriteScenarioFlag = True

    @_m.method()
    def set_overwrite_scenario_flag_false(self):
        self.OverwriteScenarioFlag = False

    @_m.method(return_type=bool)
    def check_scenario_exists(self):
        return _bank.scenario(self.ScenarioId) is not None

    @_m.method(return_type=str)
    def get_existing_scenario_title(self):
        return _bank.scenario(self.ScenarioId).title
