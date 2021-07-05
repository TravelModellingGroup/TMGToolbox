#---LICENSE----------------------
'''
    Copyright 2021 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
[TITLE]

    Authors: JamesVaughan

    Latest revision by: JamesVaughan
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2021-07-03 by JamesVaughan
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

class StrategyBasedAnalysis(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here

    xtmf_ScenarioNumber = _m.Attribute(int)
    xtmf_ClassName = _m.Attribute(str)
    xtmf_DemandMatrixNumber = _m.Attribute(int)
    xtmf_sub_path_combination_operator = _m.Attribute(str)
    xtmf_StrategyValuesMatrixNumber = _m.Attribute(int)

    xtmf_in_vehicle_trip_component = _m.Attribute(str)

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Strategy Based Analysis",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        return pb.render()

    def __call__(self, xtmf_ScenarioNumber, xtmf_ClassName, xtmf_DemandMatrixNumber, xtmf_sub_path_combination_operator, xtmf_StrategyValuesMatrixNumber, xtmf_in_vehicle_trip_component):
        if xtmf_ClassName == '':
            xtmf_ClassName = None
        if xtmf_in_vehicle_trip_component == '':
            xtmf_in_vehicle_trip_component = None
        database = _MODELLER.emmebank
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
        strategyValuesMatrixNumber = self.InitializeMatrix(database, xtmf_StrategyValuesMatrixNumber)
        spec = { 
            "trip_components": 
            {
              "boarding": None,
              "in_vehicle": xtmf_in_vehicle_trip_component,
              "aux_transit": None,
              "alighting": None
            },
            "sub_path_combination_operator": xtmf_sub_path_combination_operator,
            "sub_strategy_combination_operator": "average",
            "selected_demand_and_transit_volumes": 
            {
              "sub_strategies_to_retain": "ALL",
              "selection_threshold": { "lower": -999999, "upper": 999999 }
            }, 
            "analyzed_demand": "mf" + str(xtmf_DemandMatrixNumber),
            "constraint": None,
            "results": 
            { 
              "strategy_values": strategyValuesMatrixNumber.id,
              "selected_demand": None,
              "transit_volumes": None,
              "aux_transit_volumes": None,
              "total_boardings": None,
              "total_alightings": None
            },
            "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
        }
        tool(spec, database.scenario(xtmf_ScenarioNumber), class_name=xtmf_ClassName, num_processors='max')

    def InitializeMatrix(self, database, matrixNumber):
        matrix_name = "mf" + str(matrixNumber)
        matrix = database.matrix(matrix_name)
        if matrix is None:
            matrix = database.create_matrix(matrix_name)
        return matrix
