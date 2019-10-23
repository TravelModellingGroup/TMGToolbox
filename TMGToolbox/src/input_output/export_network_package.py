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
from os import path as _path
from datetime import datetime as _dt
import shutil as _shutil
import zipfile as _zipfile
import tempfile as _tf

_MODELLER = _m.Modeller()  # Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmg_tpb = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_inro_export_util = _MODELLER.module("inro.emme.utility.export_utilities")
_export_modes = _MODELLER.tool('inro.emme.data.network.mode.export_modes')
_export_vehicles = _MODELLER.tool('inro.emme.data.network.transit.export_vehicles')
_export_base_network = _MODELLER.tool('inro.emme.data.network.base.export_base_network')
_export_transit_lines = _MODELLER.tool('inro.emme.data.network.transit.export_transit_lines')
_export_link_shapes = _MODELLER.tool('inro.emme.data.network.base.export_link_shape')
_export_turns = _MODELLER.tool('inro.emme.data.network.turn.export_turns')
_export_attributes = _MODELLER.tool('inro.emme.data.extra_attribute.export_extra_attributes')
_export_functions = _MODELLER.tool('inro.emme.data.function.export_functions')
_pdu = _MODELLER.module('tmg.common.pandas_utils')


class ExportNetworkPackage(_m.Tool()):
    version = '1.2.1'
    tool_run_msg = ""
    number_of_tasks = 11  # For progress reporting, enter the integer number of tasks here

    Scenario = _m.Attribute(_m.InstanceType)
    ExportFile = _m.Attribute(str)
    ExportAllFlag = _m.Attribute(bool)
    AttributeIdsToExport = _m.Attribute(_m.ListType)
    ExportMetadata = _m.Attribute(str)

    xtmf_AttributeIdString = _m.Attribute(str)
    xtmf_ScenarioNumber = _m.Attribute(int)

    def __init__(self):
        # Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker

        # Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario  # Default is primary scenario
        self.ExportMetadata = ""

    def page(self):
        pb = _tmg_tpb.TmgToolPageBuilder(
            self, title="Export Network Package v%s" % self.version,
            description="Exports all scenario data files (modes, vehicles, nodes, links, transit lines, link shape, " +
                        "turns) to a compressed network package file (*.nwp).",
            branding_text="- TMG Toolbox")

        if self.tool_run_msg != "":  # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)

        pb.add_select_file(tool_attribute_name='ExportFile',
                           title="File name",
                           window_type='save_file',
                           file_filter="*.nwp")

        pb.add_checkbox(tool_attribute_name='ExportAllFlag',
                        label="Export all extra attributes?")

        keyval = self._get_select_attribute_options_json()
        pb.add_select(tool_attribute_name="AttributeIdsToExport", keyvalues=keyval,
                      title="Extra Attributes", searchable=True,
                      note="Optional")

        pb.add_text_box(tool_attribute_name='ExportMetadata',
                        size=255, multi_line=True,
                        title="Export comments")

        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        if (tool.check_all_flag())
        {
            $("#AttributeIdsToExport").prop('disabled', true);
        } else {
            $("#AttributeIdsToExport").prop('disabled', false);
        }
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#AttributeIdsToExport")
                .empty()
                .append(tool._get_select_attribute_options_html())
            inro.modeller.page.preload("#AttributeIdsToExport");
            $("#AttributeIdsToExport").trigger('change');
        });
        $("#ExportAllFlag").bind('change', function()
        {
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
            raise IOError("Export file not specified")

        self.ExportFile = _path.splitext(self.ExportFile)[0] + ".nwp"

        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Done. Scenario exported to %s" % self.ExportFile)

    @_m.method(return_type=bool)
    def check_all_flag(self):
        return self.ExportAllFlag

    def __call__(self, xtmf_ScenarioNumber, ExportFile, xtmf_AttributeIdString):

        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if self.Scenario is None:
            raise Exception("Scenario %s was not found!" % xtmf_ScenarioNumber)

        self.ExportFile = ExportFile
        if xtmf_AttributeIdString.lower() == 'all':
            self.ExportAllFlag = True  # if true, self.AttributeIdsToExport gets set in execute
        else:
            cells = xtmf_AttributeIdString.split(',')
            self.AttributeIdsToExport = [str(c.strip()) for c in cells if c.strip()]  # Clean out null values

        try:
            self._execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)

    def _execute(self):
        with _m.logbook_trace(
                name="{classname} v{version}".format(classname=self.__class__.__name__, version=self.version),
                attributes=self._get_logbook_attributes()):
            # Due to the dynamic nature of the selection process, it could happen that attributes are
            # selected which don't exist in the current scenario. The method checks early to catch
            # any problems
            if self.ExportAllFlag:
                self.AttributeIdsToExport = [att.name for att in self.Scenario.extra_attributes()]

            self._check_attributes()
            with _zipfile.ZipFile(self.ExportFile, 'w', _zipfile.ZIP_DEFLATED) as zf, self._temp_file() as temp_folder:
                version_file = _path.join(temp_folder, "version.txt")
                EMMEversion = _util.getEmmeVersion(returnType= str)
                with open(version_file, 'w') as writer:
                    writer.write("%s\n%s" % (str(5.0), EMMEversion))
                zf.write(version_file, arcname="version.txt")

                info_path = _path.join(temp_folder, "info.txt")
                self._write_info_file(info_path)
                zf.write(info_path, arcname="info.txt")

                self._batchout_modes(temp_folder, zf)
                self._batchout_vehicles(temp_folder, zf)
                self._batchout_base(temp_folder, zf)
                self._batchout_shapes(temp_folder, zf)
                self._batchout_lines(temp_folder, zf)
                self._batchout_turns(temp_folder, zf)
                self._batchout_functions(temp_folder, zf)

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

    @_m.logbook_trace("Exporting modes")
    def _batchout_modes(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "modes.201")
        self.TRACKER.runTool(_export_modes,
                             export_file=export_file,
                             scenario=self.Scenario)
        zf.write(export_file, arcname="modes.201")

    @_m.logbook_trace("Exporting vehicles")
    def _batchout_vehicles(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "vehicles.202")
        if self.Scenario.element_totals['transit_vehicles'] == 0:
            self._export_blank_batch_file(export_file, "vehicles")
            self.TRACKER.completeTask()
        else:
            self.TRACKER.runTool(_export_vehicles,
                                 export_file=export_file,
                                 scenario=self.Scenario)
        zf.write(export_file, arcname="vehicles.202")

    @_m.logbook_trace("Exporting base network")
    def _batchout_base(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "base.211")
        self.TRACKER.runTool(_export_base_network,
                             export_file=export_file,
                             scenario=self.Scenario,
                             export_format='ENG_DATA_FORMAT')
        zf.write(export_file, arcname="base.211")

    @_m.logbook_trace("Exporting link shapes")
    def _batchout_shapes(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "shapes.251")
        self.TRACKER.runTool(_export_link_shapes,
                             export_file=export_file,
                             scenario=self.Scenario)
        zf.write(export_file, arcname="shapes.251")

    @_m.logbook_trace("Exporting transit lines")
    def _batchout_lines(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "transit.221")
        if self.Scenario.element_totals['transit_lines'] == 0:
            self._export_blank_batch_file(export_file, "lines")
            self.TRACKER.completeTask()
        else:
            self.TRACKER.runTool(_export_transit_lines,
                                 export_file=export_file,
                                 scenario=self.Scenario,
                                 export_format='ENG_DATA_FORMAT')

        zf.write(export_file, arcname="transit.221")

    @_m.logbook_trace("Exporting turns")
    def _batchout_turns(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "turns.231")
        if self.Scenario.element_totals['turns'] == 0:
            #self._export_blank_batch_file(export_file, "turns")
            self.TRACKER.completeTask()
        else:
            self.TRACKER.runTool(_export_turns,
                                 export_file=export_file,
                                 scenario=self.Scenario,
                                 export_format='ENG_DATA_FORMAT')
            zf.write(export_file, arcname="turns.231")

    @_m.logbook_trace("Exporting Functions")
    def _batchout_functions(self, temp_folder, zf):
        export_file = _path.join(temp_folder, "functions.411")
        self.TRACKER.runTool(_export_functions,
                             export_file=export_file)
        zf.write(export_file, arcname="functions.411")

    @_m.logbook_trace("Exporting extra attributes")
    def _batchout_extra_attributes(self, temp_folder, zf):
        _m.logbook_write("List of attributes: %s" % self.AttributeIdsToExport)

        extra_attributes = [self.Scenario.extra_attribute(id_) for id_ in self.AttributeIdsToExport]
        types = set([att.type.lower() for att in extra_attributes])

        self.TRACKER.runTool(_export_attributes, extra_attributes,
                             temp_folder,
                             field_separator=',',
                             scenario=self.Scenario,
                             export_format='SCI_DATA_FORMAT')
        for t in types:
            if t == 'transit_segment':
                t = 'segment'
            filename = _path.join(temp_folder, "extra_%ss_%s.csv" % (t, self.Scenario.number))
            zf.write(filename, arcname="exatt_%ss.241" % t)

        summary_file = _path.join(temp_folder, "exatts.241")
        self._export_attribute_definition_file(summary_file, extra_attributes)
        zf.write(summary_file, arcname="exatts.241")

    def _batchout_traffic_results(self, temp_folder, zf):
        link_filepath = _path.join(temp_folder, "link_results.csv")
        turn_filepath = _path.join(temp_folder, "turn_results.csv")
        traffic_result_attributes = ['auto_volume', 'additional_volume', 'auto_time']

        links = _pdu.load_link_dataframe(self.Scenario).loc[:, traffic_result_attributes]
        links.to_csv(link_filepath, index=True)
        zf.write(link_filepath, arcname=_path.basename(link_filepath))

        turns = _pdu.load_turn_dataframe(self.Scenario)
        if not (turns is None):
            turns = turns.loc[:, traffic_result_attributes]
            turns.to_csv(turn_filepath)
            zf.write(turn_filepath, arcname=_path.basename(turn_filepath))


    def _batchout_transit_results(self, temp_folder, zf):
        segment_filename = "segment_results.csv"
        segment_filepath = _path.join(temp_folder, segment_filename)
        result_attributes = ['transit_boardings', 'transit_time', 'transit_volume', 'aux_transit_volume']

        segments = _pdu.load_transit_segment_dataframe(self.Scenario).loc[:, result_attributes]
        segments.to_csv(segment_filepath)
        zf.write(segment_filepath, arcname=segment_filename)


        aux_transit_filename = "aux_transit_results.csv"
        aux_transit_filepath = _path.join(temp_folder,aux_transit_filename)
        aux_result_attributes = ['aux_transit_volume']

        aux_transit = _pdu.load_link_dataframe(self.Scenario).loc[:, aux_result_attributes]
        aux_transit.to_csv(aux_transit_filepath)
        zf.write(aux_transit_filepath, arcname=aux_transit_filename)


    @contextmanager
    def _temp_file(self):
        foldername = _tf.mkdtemp()
        _m.logbook_write("Created temporary directory at '%s'" % foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            _m.logbook_write("Deleted temporary directory at '%s'" % foldername)

    def _get_logbook_attributes(self):
        atts = {
            "Scenario": str(self.Scenario.id),
            "Export File": _path.splitext(self.ExportFile)[0],
            "Version": self.version,
            "self": self.__MODELLER_NAMESPACE__}

        return atts

    def _check_attributes(self):
        defined_attributes = [att.name for att in self.Scenario.extra_attributes()]
        for attribute_id in self.AttributeIdsToExport:
            if attribute_id not in defined_attributes:
                raise IOError("Attribute '%s' not defined in scenario %s" % (attribute_id, self.Scenario.number))

    @staticmethod
    def _export_blank_batch_file(filename, t_record):
        with open(filename, 'w') as file_:
            file_.write("t %s init" % t_record)

    @staticmethod
    def _export_attribute_definition_file(filename, attribute_list):
        with open(filename, 'w') as writer:
            writer.write("name,type, default")
            for att in attribute_list:
                writer.write("\n{name},{type},{default},'{desc}'".format(
                    name=att.name, type=att.type, default=att.default_value, desc=att.description
                ))

    def _write_info_file(self, path):
        with open(path, 'w') as writer:
            bank = _MODELLER.emmebank
            time = _dt.now()
            lines = [str(bank.title),
                     str(bank.path),
                     "%s - %s" % (self.Scenario, self.Scenario.title),
                     "{y}-{m}-{d} {h}:{mm}".format(y=time.year, m=time.month, d=time.day,
                                                   h=time.hour, mm=time.minute),
                     self.ExportMetadata]

            writer.write("\n".join(lines))

    def _get_select_attribute_options_json(self):
        keyval = {}

        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            keyval[att.name] = label

        return keyval

    @_m.method(return_type=unicode)
    def _get_select_attribute_options_html(self):
        list_ = []

        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list_.append(html)
        return "\n".join(list_)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
