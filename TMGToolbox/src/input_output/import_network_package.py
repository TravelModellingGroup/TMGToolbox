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

import json
import os
import shutil as _shutil
import tempfile as _tf
import traceback as _traceback
import zipfile as _zipfile
from contextlib import contextmanager
from os import path as _path

import inro.modeller as m
import six

mm = m.Modeller()
_util = mm.module('tmg.common.utilities')
_tmg_tpb = mm.module('tmg.common.TMG_tool_page_builder')
import_modes = mm.tool('inro.emme.data.network.mode.mode_transaction')
import_vehicles = mm.tool('inro.emme.data.network.transit.vehicle_transaction')
import_base = mm.tool('inro.emme.data.network.base.base_network_transaction')
import_link_shape = mm.tool('inro.emme.data.network.base.link_shape_transaction')
import_lines = mm.tool('inro.emme.data.network.transit.transit_line_transaction')
import_turns = mm.tool('inro.emme.data.network.turn.turn_transaction')
import_attributes = mm.tool('inro.emme.data.network.import_attribute_values')


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


class ImportNetworkPackage(m.Tool()):
    version = '1.2.3'
    tool_run_msg = ""
    number_of_tasks = 9  # For progress reporting, enter the integer number of tasks here

    ScenarioId = m.Attribute(int)
    NetworkPackageFile = m.Attribute(str)
    ScenarioDescription = m.Attribute(str)
    OverwriteScenarioFlag = m.Attribute(bool)
    ConflictOption = m.Attribute(str)
    AddFunction = m.Attribute(bool)
    ScenarioName = m.Attribute(str)
    SkipMergingFunctions = m.Attribute(bool)

    def __init__(self):
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker

        self.ScenarioDescription = ""
        self.OverwriteScenarioFlag = False
        self.ConflictOption = "PRESERVE"
        self._components = ComponentContainer()
        self.event = None
        self.merge_functions = None
        self.has_exception = False
        self.SkipMergingFunctions = False

    def page(self):
        merge_functions = mm.tool('tmg.input_output.merge_functions')
        pb = _tmg_tpb.TmgToolPageBuilder(
            self,
            title="Import Network Package v%s" % self.version,
            description="Imports a new scenario from a compressed network package (*.nwp) file.",
            branding_text="- TMG Toolbox"
        )

        if self.tool_run_msg:
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_file(
            tool_attribute_name='NetworkPackageFile', window_type='file', title="Network Package File",
            file_filter='*.nwp'
        )

        pb.add_html("""<div class="t_element" id="NetworkPackageInfoDiv" style="padding: 0px inherit;"></div>""")

        pb.add_text_box(
            tool_attribute_name='ScenarioId', size=5, title="New Scenario Number",
            note="Enter a new or existing scenario"
        )

        pb.add_text_box(tool_attribute_name='ScenarioDescription', size=60, title="Scenario description")

        pb.add_checkbox(
            tool_attribute_name='SkipMergingFunctions', label="Skip the merging of functions?",
            note="Set as TRUE to unchange the functional definitions in current Emmebank."
        )

        pb.add_select(
            tool_attribute_name='ConflictOption', keyvalues=merge_functions.OPTIONS_LIST,
            title="(Optional) Function Conflict Option",
            note="Select an action to take if there are conflicts found between the package and the current Emmebank. \
                  Ignore if 'SkipMergingFunctions' is checked."
        )

        pb.add_html("""

        <div id="modal" class="modal">
          <div class="modal-content">
            <span id="modal-close" class="close">&times;</span>
            <p>Conflicts detected between the database and the network package file for the following functions(s). Please resolve these conflicts
            by indicating which version(s) to save in the database.</p>

            <table id="conflicts-table">
              <thead>
                <tr>
                  <td>Id</td>
                  <td>Database</td>
                  <td>File</td>
                  <td>Other</td>
                  <td>Expression</td>
                </tr>
              </thead>
              <tbody>
              </tbody>
            </table>
            <div class="all-select">
              <input id="typeselectdatabase" type="radio" name="typeselect" value="alldatabase" checked><label for="typeselectdatabase">Database</label>
              <input id="typeselectfile" type="radio" name="typeselect" value="allfile"><label for="typeselectdatabase">File</label>
            </div>
            <div class="footer">
              <button id="modal-save-button">Save</button>
              <button id="modal-cancel-button">Cancel</button>
            </div>
          </div>
        </div>

        <style>
            .all-select {
                padding-left:15px;
                padding-top:10px;
                padding-bottom:10px;
            }

            .modal thead td {
                font-weight:bold;
            }

            .modal {
                display: none;
                position: fixed;
                z-index: 10;
                padding-top: 30px;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgb(0,0,0);
                background-color: rgba(0,0,0,0.4);
            }

            .modal-content {
                background-color: #fefefe;
                margin: auto;
                padding: 20px;
                border: 1px solid #888;
                width: 80%;
            }

            .close {
                color: #aaaaaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
            }

            .close:hover,
            .close:focus {
                color: #000;
                text-decoration: none;
                cursor: pointer;
            }

            td.radio, thead td {
                text-align:center;
            }

            #conflicts-table {
                width: 100%;
            }

            #conflicts-table tbody tr:nth-child(odd) {
                background-color:#eaeae8;
            }

            .expression_input {
                width: 100%;
            }
        </style>

        """)

        # ---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
        $(document).ready(function () {
            var conflicts = [];
            var modal = document.getElementById('modal');
            var tool = new inro.modeller.util.Proxy(%s) ;
            window.inp_tool = tool;
            window.con = [];

            $('#typeselectfile').on('change',function() {
                if($(this).prop('checked')) {
                  $('input[value="file"]').prop('checked',true).change();
                }
            });

            $('#typeselectfile').on('click',function() {
                if($(this).prop('checked')) {
                  $('input[value="file"]').prop('checked',true).change();
                }
            });

            $('#typeselectdatabase').on('change',function() {
                if($(this).prop('checked')) {
                  $('input[value="database"]').prop('checked',true).change();
                }
            });

            $('#typeselectdatabase').on('click',function() {
                if($(this).prop('checked')) {
                  $('input[value="database"]').prop('checked',true).change();
                }
            });

            var intervalFunction = function() {
                if(tool.should_show_merge_edit_dialog()) {
                    modal.style.display = "block";
                    clearInterval(dialogPollingInterval);

                    var conflictsString = tool.get_function_conflicts().replace(/'/g,'"');
                    window.con = JSON.parse(conflictsString);

                    for(var i = 0; i < con.length; i++) {
                        window.con[i]['resolve'] = 'database';
                        $('#conflicts-table tbody').append('<tr><td>'+con[i]['id'].toUpperCase()+'</td><td class="radio"><input type="radio" name="'+i+'" value="database" checked></td>' +
                        '<td class="radio">'+
                        '<input type="radio" name="'+i+'" value="file"></td><td class="radio">'+
                        '<input type="radio" name="'+i+'" value="other"></td><td><input class="expression_input" type="text" id="exp_'+i+'" name="expression" value="'+con[i]['database_expression']+'"></td></tr>');
                    }

                    $('#conflicts-table input').on('change', function() {
                        var idx = parseInt($(this)[0].name);

                        if($(this)[0].value == 'database') {
                            $('#exp_'+idx).val(window.con[idx]['database_expression']);
                            window.con[idx]['resolve'] = 'database';
                            window.con[idx]['expression'] = window.con[idx]['database_expression'];
                        } else if($(this)[0].value == 'file') {
                            $('#exp_'+idx).val(window.con[idx]['file_expression']);
                            window.con[idx]['resolve'] = 'file';
                            window.con[idx]['expression'] = window.con[idx]['file_expression'];
                        } else if($(this)[0].value == 'other') {
                            window.con[idx]['resolve'] = 'expression';
                            window.con[idx]['expression'] = $('#exp_'+idx).val()
                        }
                    });
                };
            }

            var dialogPollingInterval = setInterval(intervalFunction,200);

            $('#modal-save-button').bind('click', function(evt) {
                for(var i = 0; i < window.con.length; i++) {
                    if(window.con[i]['resolve'] == 'expression') {
                        window.con[i]['expression'] = $('#exp_'+i).val()
                    }
                }
                tool.set_function_conflict(JSON.stringify(window.con));
                window.con = [];
                $('#conflicts-table tbody').empty();
                modal.style.display = "none";
                tool.reset_tool();
            });

            $('#modal-close, #modal-cancel-button').bind('click', function(evt) {
                window.con = [];
                $('#conflicts-table tbody').empty();
                modal.style.display = "none";
                tool.reset_tool();
            });

            $("#NetworkPackageFile").bind('change', function() {
                $(this).commit();

                //Change the scenario description
                $("#ScenarioDescription").val(tool.get_description_from_file())
                $("#ScenarioDescription").trigger('change');

                //Change the package info
                var info = tool.get_file_info();
                $("#NetworkPackageInfoDiv").removeAttr('style');
                $("#NetworkPackageInfoDiv").html(info);
            });

            //$(this).parent().siblings(".t_after_widget").html(s);

            $("#ScenarioId").bind('change', function() {
                $(this).commit();

                var toolNote = $(this).parent().siblings(".t_after_widget");
                if (tool.check_scenario_exists()) {
                    // Scenario exists
                    var h = "Scenario already exists. Overwrite? <input type='checkbox' id='ScenarioOverwrite' />"
                    toolNote.html(h);

                    $("#ScenarioOverwrite").prop('checked', false).bind('change', function() {
                        $(this).commit();
                        if ($(this).prop('checked')) {
                            tool.set_overwrite_scenario_flag_true();
                        } else {
                            tool.set_overwrite_scenario_flag_false();
                        }
                    });

                    $("#ScenarioDescription").val(tool.get_existing_scenario_title()).trigger('change');
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
            self.tool_run_msg = m.PageBuilder.format_exception(e, _traceback.format_exc())
            raise

        self.tool_run_msg = m.PageBuilder.format_info("Done. Scenario %s created." % self.ScenarioId)

    def __call__(self, NetworkPackageFile, ScenarioId, ConflictOption, AddFunction = True, ScenarioName = " "):
        self.NetworkPackageFile = NetworkPackageFile
        self.ScenarioId = ScenarioId
        self.OverwriteScenarioFlag = True
        self.ConflictOption = ConflictOption
        self.AddFunction = AddFunction

        if ScenarioName == " ":
            self.ScenarioDescription = ""
        else:
            self.ScenarioDescription = ScenarioName

        try:
            self._execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)

    def _execute(self):
        emmebank = mm.emmebank
        logbook_attributes = {
            "Scenario": self.ScenarioId,
            "Import File": self.NetworkPackageFile,
            "Version": self.version,
            "self": self.__MODELLER_NAMESPACE__
        }
        logbook_entry_name = "{classname} v{version}".format(classname=self.__class__.__name__, version=self.version)
        with m.logbook_trace(name=logbook_entry_name, attributes=logbook_attributes):

            if emmebank.scenario(self.ScenarioId) is not None and not self.OverwriteScenarioFlag:
                self.has_exception = True
                raise IOError("Scenario %s exists and overwrite flag is set to false." % self.ScenarioId)

            self._components.reset()  # Clear any held-over contents from previous run

            with _zipfile.ZipFile(self.NetworkPackageFile) as zf, self._temp_file() as temp_folder:
                self._check_network_package(zf)  # Check the file format.

                if emmebank.scenario(self.ScenarioId) is not None:
                    if not self.OverwriteScenarioFlag:
                        raise IOError("Scenario %s already exists." % self.ScenarioId)
                    sc = emmebank.scenario(self.ScenarioId)
                    if sc.modify_protected or sc.delete_protected:
                        raise IOError("Scenario %s is protected against modifications" % self.ScenarioId)
                    emmebank.delete_scenario(self.ScenarioId)
                scenario = emmebank.create_scenario(self.ScenarioId)
                scenario.title = self.ScenarioDescription

                m.logbook_write("Created new scenario %s" % self.ScenarioId)
                self.TRACKER.completeTask()

                self._batchin_modes(scenario, temp_folder, zf)
                self._batchin_vehicles(scenario, temp_folder, zf)
                self._batchin_base(scenario, temp_folder, zf)
                self._batchin_link_shapes(scenario, temp_folder, zf)
                self._batchin_lines(scenario, temp_folder, zf)
                self._batchin_turns(scenario, temp_folder, zf)
                self._batchin_network_fields(scenario, temp_folder, zf)

                if self._components.traffic_results_files is not None:
                    self._batchin_traffic_results(scenario, temp_folder, zf)

                if self._components.transit_results_files is not None:
                    self._batchin_transit_results(scenario, temp_folder, zf)

                if self._components.attribute_header_file is not None:
                    self._batchin_extra_attributes(scenario, temp_folder, zf)
                self.TRACKER.completeTask()

                if self._components.functions_file is not None and not self.SkipMergingFunctions:
                    self._batchin_functions(temp_folder, zf)
                self.TRACKER.completeTask()

    @m.method(return_type=bool)
    def tool_exit_test(self):
        self.event.set()
        return True

    @m.method(return_type=six.text_type)
    def tool_get_conflicts(self):
        return self.merge_functions.function_conflicts

    @m.logbook_trace("Reading modes")
    def _batchin_modes(self, scenario, temp_folder, zf):
        fileName = zf.extract(self._components.mode_file, temp_folder)
        self.TRACKER.runTool(import_modes, transaction_file=fileName, scenario=scenario)

    @m.logbook_trace("Reading vehicles")
    def _batchin_vehicles(self, scenario, temp_folder, zf):
        zf.extract(self._components.vehicles_file, temp_folder)
        self.TRACKER.runTool(import_vehicles, transaction_file=_path.join(temp_folder, self._components.vehicles_file),
                             scenario=scenario)

    @m.logbook_trace("Reading base network")
    def _batchin_base(self, scenario, temp_folder, zf):
        zf.extract(self._components.base_file, temp_folder)
        self.TRACKER.runTool(import_base, transaction_file=_path.join(temp_folder, self._components.base_file),
                                scenario=scenario)

    @m.logbook_trace("Reading link shapes")
    def _batchin_link_shapes(self, scenario, temp_folder, zf):
        zf.extract(self._components.shape_file, temp_folder)
        self.TRACKER.runTool(import_link_shape, transaction_file=_path.join(temp_folder, self._components.shape_file),
                             scenario=scenario)

    @m.logbook_trace("Reading transit lines")
    def _batchin_lines(self, scenario, temp_folder, zf):
        # Check to see if there are any transit vehicles before loading the transit lines otherwise it will crash
        partial_network = scenario.get_partial_network(['TRANSIT_VEHICLE'], False)
        if partial_network.transit_vehicles().__length_hint__() > 0:
            zf.extract(self._components.lines_file, temp_folder)
            if self.transit_file_change is True:
                self._transit_line_file_update(temp_folder)
            self.TRACKER.runTool(import_lines, transaction_file=_path.join(temp_folder, self._components.lines_file),
                                 scenario=scenario)

    @m.logbook_trace("Reading turns")
    def _batchin_turns(self, scenario, temp_folder, zf):
        if self._components.turns_file is not None and (self._components.turns_file in zf.namelist()):
            zf.extract(self._components.turns_file, temp_folder)
            self.TRACKER.runTool(import_turns, transaction_file=_path.join(temp_folder, self._components.turns_file),
                                 scenario=scenario)

    @m.logbook_trace("Reading Network Fields")
    def _batchin_network_fields(self, scenario, temp_folder, zf):
        # We can only load in network fields if the version number is over 4.3
        if _util.getEmmeVersion(tuple) < (4, 4, 0):
            return
        tool = mm.tool("inro.emme.data.network_field.import_network_fields")
        def read_file_if_exists(zf, folder, file):
            if not file in zf.namelist():
                return
            file_to_read = _path.join(folder, file)
            zf.extract(file, folder)
            tool(file_to_read, scenario=scenario, field_separator=",", import_definitions=True, revert_on_error=False)
            return
        read_file_if_exists(zf, temp_folder, "netfield_links.csv")
        read_file_if_exists(zf, temp_folder, "netfield_modes.csv")
        read_file_if_exists(zf, temp_folder, "netfield_nodes.csv")
        read_file_if_exists(zf, temp_folder, "netfield_segments.csv")
        read_file_if_exists(zf, temp_folder, "netfield_transit_lines.csv")
        read_file_if_exists(zf, temp_folder, "netfield_turns.csv")
        read_file_if_exists(zf, temp_folder, "netfield_vehicles.csv")
        return

    @m.logbook_trace("Reading extra attributes")
    def _batchin_extra_attributes(self, scenario, temp_folder, zf):
        types = self._load_extra_attributes(zf, temp_folder, scenario)
        contents = zf.namelist()
        processed = [self._getZipFileName(x) for x in contents]
        self.TRACKER.startProcess(len(types))
        for t in types:
            if t == "TRANSIT_SEGMENT":
                filename = "exatt_segments.241"
            else:
                filename = "exatt_%ss.241" % t.lower()
            newfilename = self._getZipOriginalString(processed, contents, filename)
            if newfilename is not None:
                try:
                    import_attributes(
                        file_path=_path.join(temp_folder, zf.extract(newfilename, temp_folder)), field_separator=",",
                        scenario=scenario
                    )
                except:
                    import_attributes(
                        file_path=_path.join(temp_folder, zf.extract(newfilename, temp_folder)), field_separator=" ",
                        scenario=scenario
                    )
                self.TRACKER.completeSubtask()

    @m.logbook_trace("Reading functions")
    def _batchin_functions(self, temp_folder, zf):
        zf.extract(self._components.functions_file, temp_folder)
        extracted_function_file_name = _path.join(temp_folder, self._components.functions_file)

        if self.ConflictOption == 'OVERWRITE':
            # Replicate Overwrite here so that consoles won't crash with references to a GUI
            functions = self._LoadFunctionFile(extracted_function_file_name)
            emmebank = mm.emmebank
            for (id, expression) in six.iteritems(functions):
                func = emmebank.function(id)
                if func is None:
                    emmebank.create_function(id, expression)
                else:
                    func.expression = expression
        elif self.ConflictOption == 'EDIT' or self.ConflictOption == 'RAISE' or self.ConflictOption == 'PRESERVE':
            merge_functions = mm.tool('tmg.input_output.merge_functions')
            merge_functions.FunctionFile = extracted_function_file_name
            merge_functions.ConflictOption = self.ConflictOption
            import threading
            self.event = threading.Event()
            self.event.clear()
            self.merge_functions = merge_functions
            self.merge_functions.show_edit_dialog = False
            merge_functions.run(event=self.event,is_sub_call=True)

    def _LoadFunctionFile(self, file_name):
        functions = {}
        with open(file_name) as reader:
            expressionBuffer = ""
            trecord = False
            currentId = None

            for line in reader:
                line = line.rstrip()
                linecode = line[0]
                record = line[2:]

                if linecode == 'c':
                    pass
                elif linecode == 't':
                    if not record.startswith("functions"):
                        raise IOError("Wrong t record!")
                    trecord = True
                elif linecode == 'a':
                    if not trecord: raise IOError("A before T")
                    index = record.index('=')
                    currentId = record[:index].strip()
                    expressionBuffer = record[(index + 1):].replace(' ', '')
                    if currentId is not None:
                        functions[currentId] = expressionBuffer
                elif linecode == ' ':
                    if currentId is not None and trecord:
                        s = record.strip().replace(' ', '')
                        expressionBuffer += s
                        functions[currentId] = expressionBuffer
                elif linecode == 'd' or linecode == 'm':
                    currentId = None
                    expressionBuffer = ""
                else: raise KeyError(linecode)

        return functions

    def _getZipFileName(self, zipPath):
        try:
            indexOfLastSlash = zipPath[::-1].index("/")
            return zipPath[len(zipPath) - indexOfLastSlash:]
        except:
            return zipPath

    @m.logbook_trace("Importing traffic results")
    def _batchin_traffic_results(self, scenario, temp_folder, zf):
        scenario.has_traffic_results = True

        links_filename, turns_filename = self._components.traffic_results_files
        zf.extract(links_filename, temp_folder)
        zf.extract(turns_filename, temp_folder)

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

    @m.logbook_trace("Importing transit results")
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
        m.logbook_write("Created temporary directory at '%s'" % foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            m.logbook_write("Deleted temporary directory at '%s'" % foldername)

    def _getZipOriginalString(self, processed, contents, objective):
        for i in range(len(processed)):
            if processed[i] == objective:
                return contents[i]
        return None

    def _check_network_package(self, package):
        """This method reads the NWP's version number and sets up the list of component files to extract. It also
        handles backwards compatibility."""

        contents = package.namelist()
        processed = [self._getZipFileName(x) for x in contents]
        self.transit_file_change = False

        if 'version.txt' in processed:
            self._components.mode_file = self._getZipOriginalString(processed, contents, 'modes.201')
            self._components.vehicles_file = self._getZipOriginalString(processed, contents, 'vehicles.202')
            self._components.base_file = self._getZipOriginalString(processed, contents, 'base.211')
            self._components.lines_file = self._getZipOriginalString(processed, contents, 'transit.221')
            self._components.turns_file = self._getZipOriginalString(processed, contents, 'turns.231')
            self._components.shape_file = self._getZipOriginalString(processed, contents, 'shapes.251')
            s = self._getZipOriginalString(processed, contents, 'version.txt')
            if s is not None:
                vf = package.open(s)
                NWPversion = float(vf.readline())
                if NWPversion >= 3:
                    self._components.functions_file = self._getZipOriginalString(processed, contents, 'functions.411')
                self.transit_file_change = (NWPversion >= 4.0)

                s = self._getZipOriginalString(processed, contents, 'link_results.csv')
                s2 = self._getZipOriginalString(processed, contents, 'turn_results.csv')
                if s is not None and s2 is not None:
                    self._components.traffic_results_files = s, s2
                self._components.transit_results_files = self._getZipOriginalString(processed, contents, 'segment_results.csv')
                self._components.aux_transit_results_file = self._getZipOriginalString(processed, contents, 'aux_transit_results.csv')
                self._components.attribute_header_file = self._getZipOriginalString(processed, contents, "exatts.241")
                return NWPversion

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

    def _transit_line_file_update(self, temp_folder):
        lines = []
        with open(_path.join(temp_folder, self._components.lines_file),"r") as infile, open(_path.join(temp_folder, 'temp.221'),"w") as outfile:
            for line in infile:
                line_length = len(line)
                if line_length < 3:
                    continue
                if line[0] == 'c':
                    outfile.write(line.replace("'",""))
                elif line[0] == 'a':
                    # Load Line Name, Skip the initial comma to get the name
                    pos = 1
                    has_quote = False
                    if line[pos] == '\'':
                        pos = 2
                        has_quote = True

                    # Find the end of the line's name
                    line_name = None
                    if has_quote:
                        end_pos = line.find("'", 2)
                        if end_pos < 0:
                            raise IOError("Incorrect transit line file format: Line Mod Veh Headwy Speed Description Data1 Data2 Data3")
                        line_name = line[pos:end_pos]
                        pos = end_pos + 1
                    else:
                        while pos < line_length:
                            pos += 1
                            if line[pos] == '\'':
                                line_name = line[2:pos]
                                break
                        if line_name is None:
                            raise IOError("Incorrect transit line file format: Line Mod Veh Headwy Speed Description Data1 Data2 Data3")

                    # Find the start of the description and store the inner portion the way it is
                    start = pos
                    whitespace_state = True
                    inner_text = None
                    count = 0
                    while pos < line_length:
                        if whitespace_state:
                            if line[pos] != ' ':
                                count += 1
                                whitespace_state = False
                                # If we found the first character of the description (might be a quote)
                                if count >= 5:
                                    inner_text = line[start:pos]
                                    break
                        else:
                            if line[pos] == ' ' or line[pos] == "'":
                                whitespace_state = True
                        pos += 1

                    if inner_text is None:
                        raise IOError("Incorrect transit line file format: Line Mod Veh Headwy Speed Description Data1 Data2 Data3")

                    # Parse the description string
                    description = None
                    if line[pos] == '\'':
                        # Just find the next ' for the end of the description
                        end = line.find("'", pos + 1)
                        if end < 0:
                            raise IOError("Incorrect transit line file format: Line Mod Veh Headwy Speed Description Data1 Data2 Data3")
                        description = line[pos + 1:end]
                        pos = end + 1
                    else:
                        # Then the description is the next 20 characters, replacing quotes with `
                        description = line[pos:pos + 20].replace("'","`")
                        pos += 21 # 19 for the end of description + 1 for ' and + 1 for the start of the next entry

                    # Skip until we find the start of the next non-whitespace
                    while pos < line_length:
                        if line[pos] != ' ':
                            break
                        pos += 1

                    # Write out the final formatted string in a format that all versions of EMME can read
                    outfile.write('a\'{0}\' {1} \'{2}\' {3}\n'.format(line_name.ljust(6, ' '), inner_text, description.ljust(20, ' '),  line[pos:line_length - 1]))
                else:
                    # try to parse out the individual segments
                    # j-node, dwell time, ttf, us1, us2, us3 (and ignore the rest)
                    column_count = 0
                    last_whitespace = False
                    pos = 0
                    while pos < line_length:
                        if not last_whitespace and line[pos] == ' ':
                            last_whitespace = True
                            column_count += 1
                            if column_count == 7:
                                break
                        elif line[pos] != ' ':
                            last_whitespace = False
                        pos += 1

                    if column_count == 7:
                        # then there is some extra data so we need to clip it out
                        outfile.write(line[0:pos])
                    else:
                        outfile.write(line)
        outfile.close()
        os.remove(_path.join(temp_folder, self._components.lines_file))
        os.renames(_path.join(temp_folder, 'temp.221'),_path.join(temp_folder, self._components.lines_file))
        return None

    #@m.method(return_type=m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    @m.method(return_type=six.text_type)
    def get_description_from_file(self):
        if self.NetworkPackageFile:
            if not self.ScenarioDescription:
                return _path.splitext(_path.basename(self.NetworkPackageFile))[0]
            else:
                return self.ScenarioDescription

    @m.method(return_type=six.text_type)
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
            project_name = "<b>Project:</b> %s" % lines[0].decode().strip()
            scenario_title = "<b>Scenario:</b> %s" % lines[2].decode().strip()
            export_date = "<b>Export Date:</b> %s" % lines[3].decode().strip()
            comment_lines = ["<b>User Comments:</b>"] + [l.decode().strip() for l in lines[4:]]
            html_lines = [package_version, project_name, scenario_title, export_date, ''] + comment_lines
            cell = "<br>".join(html_lines)

            return "<table border='1' width='90&#37'><tbody><tr><td valign='top'>%s</td></tr></tbody></table>" % cell

    @m.method()
    def set_overwrite_scenario_flag_true(self):
        self.OverwriteScenarioFlag = True

    @m.method()
    def set_overwrite_scenario_flag_false(self):
        self.OverwriteScenarioFlag = False

    @m.method(return_type=bool)
    def check_scenario_exists(self):
        return mm.emmebank.scenario(self.ScenarioId) is not None

    @m.method(return_type=str)
    def get_existing_scenario_title(self):
        return mm.emmebank.scenario(self.ScenarioId).title

    @m.method(return_type=bool)
    def should_show_merge_edit_dialog(self):
        return False if self.merge_functions is None or self.exception else self.merge_functions.show_edit_dialog

    @m.method(return_type=str)
    def get_function_conflicts(self):
        return self.merge_functions.function_conflicts

    @m.method(argument_types=[str])
    def set_function_conflict(self,data):
        data_eval = json.loads(data)
        self.merge_functions.merge_changes(data_eval)

    @m.method()
    def reset_tool(self):
        self.OverwriteScenarioFlag = False
        self.has_exception = False
