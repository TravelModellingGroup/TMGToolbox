'''
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
'''

import os
import inro.modeller as _m
import traceback as _traceback
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')

class ImportBoardingPenalties(_m.Tool()):
    
    BoardingsFile = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType)
    ScenarioNumber = _m.Attribute(int)
    
    def __init__(self):
        try:
            self.netCalcTool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
        except Exception, e:
            self.netCalcTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")

    def page(self):      
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Import Boarding Penalties from File",
                     description="Imports boarding penalties into UT3 (line attribute 3) from a file",
                     branding_text="- TMG Toolbox")
        
        #pb.add_file_example(header_text="boarding_penalty;filter_expression;description",
                            #body_text="0.0; ut1=26 and mode=m; TTC subway")
        
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select Scenario")
        
        try:
            root = os.path.dirname(_m.Modeller().desktop.project_filename())
        except Exception, e:
            root = os.path.dirname(_m.Modeller().desktop.project_file_name())
        pb.add_select_file(tool_attribute_name="BoardingsFile",
                            window_type="file",
                            file_filter="*.txt",
                            start_path=root,
                            title="File with boardings",
                            note="A table with columns separated by ';'")
        
        with pb.add_table(visible_border=True, title="File example:") as t:
            t.add_table_header(["boarding_penalty", "filter_expression", "description"])
            t.new_row()
            with t.table_cell():
                pb.add_plain_text("0.0")
            with t.table_cell():
                pb.add_plain_text("ut1=26 and mode=m")
            with t.table_cell():
                pb.add_html("TTC subway")
        
        return pb.render()
    
    def run(self):
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, ScenarioNumber, BoardingsFile):
        self.Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.Scenario is None:
            raise Exception("Could not find scenario '%s' in emmebank!" %ScenarioNumber)
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))    
    
    def _execute(self):
        with _m.logbook_trace("Load Boarding Penalties From File"):
            _m.logbook_write("Opening file:'%s'" %self.BoardingsFile)
            file = open(self.BoardingsFile,'r')
            line = file.readline()
            cells = line.split(';')
            if cells.count('boarding_penalty') < 1 :
                raise Exception("Boardings file does not have a boarding_penalty header!")
            if cells.count('filter_expression') < 1 :
                raise Exception("Boardings file does not have a filter_expression header!")
            headers = {'penalty': cells.index('boarding_penalty'), 'expression' : cells.index('filter_expression')}
            
            for line in file.readlines():
                try:
                    cells = line.split(';')
                    val = float(cells[headers['penalty']])
                    expr = cells[headers['expression']]
                    
                    specification={
                                   "result": "ut3",
                                   "expression": "%s" %val,
                                   "aggregation": None,
                                   "selections": {
                                                  "transit_line": expr
                                                  },
                                   "type": "NETWORK_CALCULATION"
                                   }
                    self.netCalcTool(specification)
                    
                except ValueError:
                    continue