from os import path
import traceback as tb

import inro.modeller as m
mm = m.Modeller()
util = mm.module('tmg.common.utilities')
pdu = mm.module('tmg.common.pandas_utils')


class ExportNetworkTables(m.Tool()):
    tool_run_msg = ""

    SourceScenario = m.Attribute(m.InstanceType)
    TargetFolder = m.Attribute(str)
    FilePrefix = m.Attribute(str)

    NodeTableFlag = m.Attribute(bool)
    LinkTableFlag = m.Attribute(bool)
    TurnTableFlag = m.Attribute(bool)
    LineTableFlag = m.Attribute(bool)
    SegmentTableFlag = m.Attribute(bool)

    def __init__(self):
        self.tool_run_msg = ""
        self.tracker = util.ProgressTracker(5)

        self.SourceScenario = mm.scenario
        self.FilePrefix = ''

        self.NodeTableFlag = True
        self.LinkTableFlag = True
        self.TurnTableFlag = False
        self.LineTableFlag = False
        self.SegmentTableFlag = False

    def page(self):
        pb = m.ToolPageBuilder(
            self, title="Export Network Tables",
            description="Exports up to 5 CSV tables from the selected scenario. Table columns are limited to "
                        "'standard', 'extra' and 'result' categories as defined in the Network API (so link mode "
                        "codes are omitted).",
            branding_text="- TMG Toolbox"
        )

        if self.tool_run_msg != "":  # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario('SourceScenario', title="Scenario", allow_none=False)

        pb.add_select_file('TargetFolder', window_type='directory', title="Folder",
                           note="Folder to contain output CSVs")

        pb.add_text_box('FilePrefix', title="File prefix",
                        note="Optional text to prepend to export files. Otherwise the files will be named 'links.csv', "
                             "etc.")

        group_data = [
            {'attribute': 'NodeTableFlag', 'label': 'Export node table?'},
            {'attribute': 'LinkTableFlag', 'label': 'Export link table?'},
            {'attribute': 'TurnTableFlag', 'label': 'Export turn table?'},
            {'attribute': 'LineTableFlag', 'label': 'Export transit line table?'},
            {'attribute': 'SegmentTableFlag', 'label': 'Export transit segment table?'}
        ]
        pb.add_checkbox_group(group_data, title="Flags for network elements",
                              note="<div id='ux_all'>Export all elements?</div>")

        return pb.render()

    @m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    @m.method(return_type=m.TupleType)
    def percent_completed(self):
        return self.tracker.getProgress()

    def run(self):
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = m.PageBuilder.format_exception(e, tb.format_exc(e))

    def __call__(self, scenario_id, target_folder, file_prefix, export_nodes, export_links, export_turns, export_lines,
                 export_segments):
        try:
            self.SourceScenario = mm.emmebank.scenario(scenario_id)
            assert self.SourceScenario is not None, "Scenario %s does not exist" % scenario_id

            self.TargetFolder = target_folder
            self.FilePrefix = file_prefix
            self.NodeTableFlag = export_nodes
            self.LinkTableFlag = export_links
            self.TurnTableFlag = export_turns
            self.LineTableFlag = export_lines
            self.SegmentTableFlag = export_segments

        except Exception as e:
            msg = str(e) + "\n" + tb.format_exc(e)
            raise Exception(msg)

    def _execute(self):
        self.tool_run_msg = ""
        self.tracker.reset()

        with m.logbook_trace(name=self.__class__.__name__, attributes=self.logbook_attributes):
            assert self.TargetFolder is not None, "Target folder is not set"

            if self.NodeTableFlag:
                df = pdu.load_node_dataframe(self.SourceScenario)
                self._to_csv(df, 'nodes')
            self.tracker.completeTask()

            if self.LineTableFlag:
                df = pdu.load_link_dataframe(self.SourceScenario)
                self._to_csv(df, 'links')
            self.tracker.completeTask()

            if self.TurnTableFlag:
                df = pdu.load_turn_dataframe(self.SourceScenario)
                self._to_csv(df, 'turns')
            self.tracker.completeTask()

            if self.LineTableFlag:
                df = pdu.load_transit_line_dataframe(self.SourceScenario)
                self._to_csv(df, 'transit_lines')
            self.tracker.completeTask()

            if self.SegmentTableFlag:
                df = pdu.load_transit_segment_dataframe(self.SourceScenario)
                self._to_csv(df, 'transit_segments')
            self.tracker.completeTask()

        self.tool_run_msg = m.PageBuilder.format_info("Done")

    def _to_csv(self, df, file_name):
        fn = "{}_{}.csv".format(self.FilePrefix, file_name) if self.FilePrefix else "%s.csv" % file_name
        fp = path.join(self.TargetFolder, fn)
        df.to_csv(fp, header=True, index=True)

    @property
    def logbook_attributes(self):
        return {
            'scenario': self.SourceScenario.number,
            'target_folder': self.TargetFolder,
            'export_nodes': self.NodeTableFlag,
            'export_links': self.LineTableFlag,
            'export_turns': self.TurnTableFlag,
            'export_lines': self.LineTableFlag,
            'export_segments': self.SegmentTableFlag
        }
