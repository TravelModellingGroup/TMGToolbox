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
import shutil
import tempfile
import traceback
import zipfile
from contextlib import contextmanager
from datetime import datetime
from os import path

import inro.modeller as m
import six

mm = m.Modeller()
_util = mm.module('tmg.common.utilities')
_tmg_tpb = mm.module('tmg.common.TMG_tool_page_builder')
_export_modes = mm.tool('inro.emme.data.network.mode.export_modes')
_export_vehicles = mm.tool('inro.emme.data.network.transit.export_vehicles')
_export_base_network = mm.tool('inro.emme.data.network.base.export_base_network')
_export_transit_lines = mm.tool('inro.emme.data.network.transit.export_transit_lines')
_export_link_shapes = mm.tool('inro.emme.data.network.base.export_link_shape')
_export_turns = mm.tool('inro.emme.data.network.turn.export_turns')
_export_attributes = mm.tool('inro.emme.data.extra_attribute.export_extra_attributes')
_export_functions = mm.tool('inro.emme.data.function.export_functions')
_pdu = mm.module('tmg.common.pandas_utils')

# initalize python3 types
_util.initalizeModellerTypes(m)


class ExportNetworkPackage(m.Tool()):
    version = '1.2.3'
    tool_run_msg = ""
    number_of_tasks = 11  # For progress reporting, enter the integer number of tasks here

    Scenario = m.Attribute(m.InstanceType)
    ExportFile = m.Attribute(str)
    ExportAllFlag = m.Attribute(bool)
    AttributeIdsToExport = m.Attribute(m.ListType)
    ExportMetadata = m.Attribute(str)
    ExportToEmmeOldVersion = m.Attribute(bool)

    export_attributes = m.Attribute(str)
    scenario_number = m.Attribute(int)

    def __init__(self):
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker

        self.Scenario = mm.scenario  # Default is primary scenario
        self.ExportMetadata = ''
        self.ExportToEmmeOldVersion = False

    def page(self):
        pb = _tmg_tpb.TmgToolPageBuilder(
            self,
            title='Export Network Package v%s' % self.version,
            description="Exports all scenario data files (modes, vehicles, nodes, links, transit lines, link shape, "
                        "turns) to a compressed network package file (*.nwp). Descriptions that are empty, have single "
                        "quotes, or double quotes will be replaced by 'No Description', grave accents (`), and spaces.",
            branding_text='- TMG Toolbox'
        )

        if self.tool_run_msg:
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario('Scenario', title='Scenario', allow_none=False)

        pb.add_select_file('ExportFile', title='File name', window_type='save_file', file_filter="*.nwp")

        pb.add_checkbox('ExportToEmmeOldVersion', label='Export it to be compatible with Emme 4.3?',
                        note='Descriptions longer than 20 characters will be trimmed.')

        pb.add_checkbox('ExportAllFlag', label='Export all extra attributes?')

        pb.add_select('AttributeIdsToExport', keyvalues=self._get_select_attribute_options_json(),
                      title='Extra Attributes', searchable=True, note='Optional')

        pb.add_text_box('ExportMetadata', size=255, multi_line=True, title='Export comments')

        pb.add_html("""
<script type="text/javascript">
    $(document).ready(function() {
        var tool = new inro.modeller.util.Proxy(%s);
        if (tool.check_all_flag()) {
            $("#AttributeIdsToExport").prop('disabled', true);
        } else {
            $("#AttributeIdsToExport").prop('disabled', false);
        }
        $("#Scenario").on('change', function() {
            $(this).commit();
            $("#AttributeIdsToExport").empty().append(tool._get_select_attribute_options_html())
            inro.modeller.page.preload("#AttributeIdsToExport");
            $("#AttributeIdsToExport").trigger('change');
        });
        $("#ExportAllFlag").on('change', function() {
            $(this).commit();
            var not_flag = ! tool.check_all_flag();
            var flag = tool.check_all_flag();
            $("#AttributeIdsToExport").prop('disabled', flag);
        });
    });
</script>""" % pb.tool_proxy_tag)

        return pb.render()

    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        if self.ExportFile is None:
            raise IOError('Export file not specified')

        self.ExportFile = path.splitext(self.ExportFile)[0] + '.nwp'

        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = m.PageBuilder.format_exception(e, traceback.format_exc())
            raise

        self.tool_run_msg = m.PageBuilder.format_info('Done. Scenario exported to %s' % self.ExportFile)

    @m.method(return_type=bool)
    def check_all_flag(self):
        return self.ExportAllFlag

    def __call__(self, scenario_number, ExportFile, export_attributes):
        self.Scenario = mm.emmebank.scenario(scenario_number)
        if self.Scenario is None:
            raise Exception('Scenario %s was not found!' % scenario_number)

        self.ExportFile = ExportFile
        if export_attributes.lower() == 'all':
            self.ExportAllFlag = True  # if true, self.AttributeIdsToExport gets set in execute
        else:
            cells = export_attributes.split(',')
            self.AttributeIdsToExport = [str(c.strip()) for c in cells if c.strip()]  # Clean out null values

        try:
            self._execute()
        except Exception as e:
            msg = str(e) + "\n" + traceback.format_exc()
            raise Exception(msg)

    def _execute(self):
        logbook_attributes = {
            'Scenario': str(self.Scenario.id), 'Export File': path.splitext(self.ExportFile)[0],
            'Version': self.version, 'self': self.__MODELLER_NAMESPACE__
        }
        logbook_entry_name = '%s v%s' % (self.__class__.__name__, self.version)
        with m.logbook_trace(name=logbook_entry_name, attributes=logbook_attributes):
            # Save a snapshot of the inputs in the logbook
            snapshot = {
                "Scenario": self.Scenario.id,
                "ExportFile": self.ExportFile,
                "ExportToEmmeOldVersion": self.ExportToEmmeOldVersion,
                "ExportAllFlag": self.ExportAllFlag,
                "AttributeIdsToExport": self.AttributeIdsToExport,
                "ExportMetadata": self.ExportMetadata
            }
            m.logbook_snapshot(name=logbook_entry_name, comment='', namespace=str(self), value=json.dumps(snapshot))

            # Due to the dynamic nature of the selection process, it could happen that attributes are
            # selected which don't exist in the current scenario. The method checks early to catch
            # any problems
            defined_attributes = [att.name for att in self.Scenario.extra_attributes()]
            if self.ExportAllFlag:
                self.AttributeIdsToExport = defined_attributes
            else:
                missing_attributes = set(self.AttributeIdsToExport).difference(defined_attributes)
                if missing_attributes:
                    raise IOError('Attributes [%s] not defined in scenario %s' % (', '.join(missing_attributes),
                                                                                  self.Scenario.number))

            with zipfile.ZipFile(self.ExportFile, 'w', zipfile.ZIP_DEFLATED) as zf, self._temp_file() as temp_folder:
                version_file = path.join(temp_folder, 'version.txt')
                with open(version_file, 'w') as writer:
                    writer.write("%s\n%s" % (str(5.0), _util.getEmmeVersion(returnType=str)))
                zf.write(version_file, arcname='version.txt')

                info_path = path.join(temp_folder, 'info.txt')
                self._write_info_file(info_path)
                zf.write(info_path, arcname='info.txt')

                self._batchout_modes(temp_folder, zf)
                self._batchout_vehicles(temp_folder, zf)
                self._batchout_base(temp_folder, zf)
                self._batchout_shapes(temp_folder, zf)
                self._batchout_lines(temp_folder, zf)
                self._batchout_turns(temp_folder, zf)
                self._batchout_functions(temp_folder, zf)
                self._batchout_network_fields(temp_folder, zf)

                if len(self.AttributeIdsToExport) > 0:
                    self._batchout_extra_attributes(temp_folder, zf)
                else:
                    self.TRACKER.completeTask()

                if self.Scenario.has_traffic_results:
                    self._batchout_traffic_results(temp_folder, zf)
                self.TRACKER.completeTask()

                if self.Scenario.has_transit_results:
                    self._batchout_transit_results(temp_folder, zf)
                self.TRACKER.completeTask()

    @m.logbook_trace('Exporting modes')
    def _batchout_modes(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'modes.201')
        self.TRACKER.runTool(_export_modes, export_file=export_file, scenario=self.Scenario)
        zf.write(export_file, arcname='modes.201')

    @m.logbook_trace('Exporting vehicles')
    def _batchout_vehicles(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'vehicles.202')
        if self.Scenario.element_totals['transit_vehicles'] == 0:
            self._export_blank_batch_file(export_file, 'vehicles')
            self.TRACKER.completeTask()
        else:
            self.TRACKER.runTool(_export_vehicles, export_file=export_file, scenario=self.Scenario)
        zf.write(export_file, arcname='vehicles.202')

    @m.logbook_trace('Exporting base network')
    def _batchout_base(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'base.211')
        self.TRACKER.runTool(_export_base_network, export_file=export_file, scenario=self.Scenario,
                             export_format='ENG_DATA_FORMAT')
        zf.write(export_file, arcname='base.211')

    @m.logbook_trace('Exporting link shapes')
    def _batchout_shapes(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'shapes.251')
        self.TRACKER.runTool(_export_link_shapes, export_file=export_file, scenario=self.Scenario)
        zf.write(export_file, arcname='shapes.251')

    @m.logbook_trace('Exporting transit lines')
    def _batchout_lines(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'transit.221')
        if self.Scenario.element_totals['transit_lines'] == 0:
            self._export_blank_batch_file(export_file, 'lines')
            self.TRACKER.completeTask()
        else:
            # check if the description is empty or has single quote
            network = self.Scenario.get_network()
            for line in network.transit_lines():
                if len(line.description) == 0:
                    line.description = "No Description"
                else:
                    line.description = line.description.replace("'", "`").replace('"', ' ')
                    if len(line.description) > 20 and self.ExportToEmmeOldVersion:
                        line.description = line.description[0:19]
            self.Scenario.publish_network(network)

            self.TRACKER.runTool(_export_transit_lines, export_file=export_file, scenario=self.Scenario,
                                 export_format='ENG_DATA_FORMAT')
        zf.write(export_file, arcname='transit.221')

    @m.logbook_trace('Exporting turns')
    def _batchout_turns(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'turns.231')
        if self.Scenario.element_totals['turns'] == 0:
            self.TRACKER.completeTask()
        else:
            self.TRACKER.runTool(_export_turns, export_file=export_file, scenario=self.Scenario,
                                 export_format='ENG_DATA_FORMAT')
            zf.write(export_file, arcname='turns.231')

    @m.logbook_trace('Exporting Functions')
    def _batchout_functions(self, temp_folder, zf):
        export_file = path.join(temp_folder, 'functions.411')
        self.TRACKER.runTool(_export_functions, export_file=export_file)
        zf.write(export_file, arcname='functions.411')

    @m.logbook_trace('Exporting Network Fields')
    def _batchout_network_fields(self, temp_folder, zf):
        version = _util.getEmmeVersion(returnType=tuple)
        # we only can try to export fields if the EMME version is over 4.3
        if version >= (4, 4, 0) and len(self.Scenario.network_fields()) > 0:
            try:
                tool = mm.tool('inro.emme.data.network_field.export_network_fields')
                tool(network_fields="ALL",
                    export_path=temp_folder,
                    field_separator=',',
                    scenario=self.Scenario,
                    export_definitions=True
                    )
                def write_if_exists(zf, directory_name, local_name, scenario_number):
                    # The scenario number is appended as X_1.csv for scenario 1
                    exported_file = path.join(directory_name, local_name + "_" + str(scenario_number) + ".csv")
                    if path.isfile(exported_file):
                        zf.write(exported_file, arcname=local_name + ".csv")
                    return
                scenario = self.Scenario.number
                write_if_exists(zf, temp_folder, "netfield_links", scenario)
                write_if_exists(zf, temp_folder, "netfield_modes", scenario)
                write_if_exists(zf, temp_folder, "netfield_nodes", scenario)
                write_if_exists(zf, temp_folder, "netfield_segments", scenario)
                write_if_exists(zf, temp_folder, "netfield_transit_lines", scenario)
                write_if_exists(zf, temp_folder, "netfield_turns", scenario)
                write_if_exists(zf, temp_folder, "netfield_vehicles", scenario)
            except Exception as e:
                # If there is no network values, EMME throws an error
                # We can ignore this error and just continue
                pass
        return


    @m.logbook_trace('Exporting extra attributes')
    def _batchout_extra_attributes(self, temp_folder, zf):
        m.logbook_write('List of attributes: %s' % self.AttributeIdsToExport)

        extra_attributes = [self.Scenario.extra_attribute(id_) for id_ in self.AttributeIdsToExport]
        types = set([att.type.lower() for att in extra_attributes])

        self.TRACKER.runTool(_export_attributes, extra_attributes, temp_folder, field_separator=',',
                             scenario=self.Scenario, export_format='SCI_DATA_FORMAT')
        for t in types:
            if t == 'transit_segment':
                t = 'segment'
            filename = path.join(temp_folder, 'extra_%ss_%s.csv' % (t, self.Scenario.number))
            zf.write(filename, arcname='exatt_%ss.241' % t)
        summary_file = path.join(temp_folder, 'exatts.241')
        self._export_attribute_definition_file(summary_file, extra_attributes)
        zf.write(summary_file, arcname='exatts.241')

    def _batchout_traffic_results(self, temp_folder, zf):
        link_filepath = path.join(temp_folder, 'link_results.csv')
        turn_filepath = path.join(temp_folder, 'turn_results.csv')
        traffic_result_attributes = ['auto_volume', 'additional_volume', 'auto_time']

        links = _pdu.load_link_dataframe(self.Scenario)[traffic_result_attributes]
        links.to_csv(link_filepath, index=True)
        zf.write(link_filepath, arcname=path.basename(link_filepath))

        turns = _pdu.load_turn_dataframe(self.Scenario)
        if not (turns is None):
            turns = turns[traffic_result_attributes]
            turns.to_csv(turn_filepath)
            zf.write(turn_filepath, arcname=path.basename(turn_filepath))

    def _batchout_transit_results(self, temp_folder, zf):
        segment_filepath = path.join(temp_folder, 'segment_results.csv')
        result_attributes = ['transit_boardings', 'transit_time', 'transit_volume']
        segments = _pdu.load_transit_segment_dataframe(self.Scenario)[result_attributes]
        segments.to_csv(segment_filepath)
        zf.write(segment_filepath, arcname=path.basename(segment_filepath))

        aux_transit_filepath = path.join(temp_folder, 'aux_transit_results.csv')
        aux_result_attributes = ['aux_transit_volume']
        aux_transit = _pdu.load_link_dataframe(self.Scenario)[aux_result_attributes]
        aux_transit.to_csv(aux_transit_filepath)
        zf.write(aux_transit_filepath, arcname=path.basename(aux_transit_filepath))

    @contextmanager
    def _temp_file(self):
        foldername = tempfile.mkdtemp()
        m.logbook_write('Created temporary directory at `%s`' % foldername)
        try:
            yield foldername
        finally:
            shutil.rmtree(foldername, True)
            m.logbook_write('Deleted temporary directory at `%s`' % foldername)

    @staticmethod
    def _export_blank_batch_file(filename, t_record):
        with open(filename, 'w') as file_:
            file_.write('t %s init' % t_record)

    @staticmethod
    def _export_attribute_definition_file(filename, attribute_list):
        with open(filename, 'w') as writer:
            writer.write('name,type, default')
            for att in attribute_list:
                writer.write("\n{name},{type},{default},'{desc}'".format(
                    name=att.name, type=att.type, default=att.default_value, desc=att.description
                ))

    def _write_info_file(self, fp):
        with open(fp, 'w') as writer:
            bank = mm.emmebank
            lines = [
                str(bank.title), str(bank.path), '%s - %s' % (self.Scenario, self.Scenario.title),
                datetime.now().strftime('%Y-%m-%d %H:%M'), self.ExportMetadata
            ]
            writer.write("\n".join(lines))

    def _get_select_attribute_options_json(self):
        keyval = {}
        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            keyval[att.name] = label
        return keyval

    @m.method(return_type=six.text_type)
    def _get_select_attribute_options_html(self):
        list_ = []
        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = '<option value="{id}">{text}</option>'.format(id=att.name, text=label)
            list_.append(html)
        return six.u("\n".join(list_))

    @m.method(return_type=m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    # region Snapshot and stateful interfaces

    def to_snapshot(self):
        att_ids = None if len(self.AttributeIdsToExport) == 0 else self.AttributeIdsToExport
        snapshot = {
            "Scenario": self.Scenario.id,
            "ExportFile": self.ExportFile,
            "ExportToEmmeOldVersion": self.ExportToEmmeOldVersion,
            "ExportAllFlag": self.ExportAllFlag,
            "AttributeIdsToExport": att_ids,
            "ExportMetadata": self.ExportMetadata
        }
        return json.dumps(snapshot)

    def from_snapshot(self, snapshot):
        snapshot = json.loads(snapshot)
        att_ids = [] if snapshot["AttributeIdsToExport"] is None else snapshot["AttributeIdsToExport"]

        emmebank = mm.emmebank
        self.Scenario = emmebank.scenario(snapshot["Scenario"])
        self.ExportFile = snapshot["ExportFile"]
        self.ExportToEmmeOldVersion = bool(snapshot["ExportToEmmeOldVersion"])
        self.ExportAllFlag = bool(snapshot["ExportAllFlag"])
        self.AttributeIdsToExport = att_ids
        self.ExportMetadata = snapshot["ExportMetadata"]

    def __getitem__(self, key):
        value = getattr(self, key)
        return value

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def get_state(self):
        state = {
            "Scenario": self.Scenario,
            "ExportFile": self.ExportFile,
            "ExportToEmmeOldVersion": self.ExportToEmmeOldVersion,
            "ExportAllFlag": self.ExportAllFlag,
            "AttributeIdsToExport": self.AttributeIdsToExport,
            "ExportMetadata": self.ExportMetadata
        }
        return state

    # endregion
