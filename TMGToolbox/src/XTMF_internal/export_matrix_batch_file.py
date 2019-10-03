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
_util = _m.Modeller().module('tmg.common.utilities')

class ExportMatrix(_m.Tool()):
    
    MatrixId = _m.Attribute(int)
    Filename = _m.Attribute(str)
    ScenarioNumber = _m.Attribute(int)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(1)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Export a matrix",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")      
        
        return pb.render()

    def __call__(self, MatrixId, Filename, ScenarioNumber):        
        with _m.logbook_trace("Exporting matrix %s to XTMF" %MatrixId): 
            scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
            if (scenario is None):
                raise Exception("Scenario %s was not found!" %ScenarioNumber)
            
            try:
                tool = None
                try:
                    tool = _m.Modeller().tool('inro.emme.standard.data.matrix.export_matrices')
                except Exception as e:
                    tool = _m.Modeller().tool('inro.emme.data.matrix.export_matrices')
                
                mtx = _m.Modeller().emmebank.matrix("mf%s" %MatrixId)
                if mtx is None:
                    raise Exception("No matrix found with id '%s'" %MatrixId)
                self._tracker.runTool(tool,
                                      export_file=Filename,
                                      field_separator='TAB',
                                      matrices=[mtx],
                                      full_matrix_line_format="ONE_ENTRY_PER_LINE",
                                      export_format="PROMPT_DATA_FORMAT",
                                      scenario=scenario,
                                      skip_default_values=False)
                
            except Exception as e:
                raise Exception(_traceback.format_exc(e))

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
    