#---LICENSE----------------------
'''
    Copyright 2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
#---METADATA---------------------
'''
Volume per Operator

    Authors: tnikolov

    Latest revision by: tnikolov
    
    
    Tool used to calculate the amount of riders on each operator within the system.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-05-12 by tnikolov
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os.path import exists
from json import loads as _parsedict
from os.path import dirname
import tempfile as _tf
import shutil as _shutil
import csv

_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculator = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
traversalAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.traversal_analysis')
networkResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
matrixCalculator = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
matrixAggregation = _MODELLER.tool('inro.emme.matrix_calculation.matrix_aggregation')
#matrixExportTool = _MODELLER.tool('inro.emme.data.matrix.export_matrices')
matrixExport = _MODELLER.tool('inro.emme.data.matrix.export_matrix_to_csv')
pathAnalysis = _MODELLER.tool('inro.emme.transit_assignment.extended.path_based_analysis')
EMME_VERSION = _util.getEmmeVersion(float)

class AccessibilityCalculations(_m.Tool()):

    def __init__(self):
        self.Scenario = _MODELLER.scenario

    # def run(self):

        

    # def __call__(self, xtmf_ScenarioNumbers, FilterString):
