
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

    xtmf_transit_volumes_attribute = _m.Attribute(str)
    xtmf_aux_transit_attribute = _m.Attribute(str)
    xtmf_aux_transit_volumes_attribute = _m.Attribute(str)

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Strategy Based Analysis",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        return pb.render()

    def value_or_none(self, value):
        if value == '':
            return None
        else:
            return value

    def __call__(self, xtmf_ScenarioNumber, xtmf_ClassName, xtmf_DemandMatrixNumber, xtmf_sub_path_combination_operator, xtmf_StrategyValuesMatrixNumber,
                xtmf_in_vehicle_trip_component, xtmf_transit_volumes_attribute,
                xtmf_aux_transit_attribute, xtmf_aux_transit_volumes_attribute):
        
        xtmf_ClassName = self.value_or_none(xtmf_ClassName)
        xtmf_in_vehicle_trip_component = self.value_or_none(xtmf_in_vehicle_trip_component)

        xtmf_transit_volumes_attribute = self.value_or_none(xtmf_transit_volumes_attribute)
        xtmf_aux_transit_attribute = self.value_or_none(xtmf_aux_transit_attribute)
        xtmf_aux_transit_volumes_attribute = self.value_or_none(xtmf_aux_transit_volumes_attribute)

        database = _MODELLER.emmebank
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
        strategyValuesMatrixId = self.InitializeMatrix(database, xtmf_StrategyValuesMatrixNumber)
        spec = { 
            "trip_components": 
            {
              "boarding": None,
              "in_vehicle": xtmf_in_vehicle_trip_component,
              "aux_transit": xtmf_aux_transit_attribute,
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
              "strategy_values": strategyValuesMatrixId,
              "selected_demand": None,
              "transit_volumes": xtmf_transit_volumes_attribute,
              "aux_transit_volumes": xtmf_aux_transit_volumes_attribute,
              "total_boardings": None,
              "total_alightings": None
            },
            "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
        }
        tool(spec, database.scenario(xtmf_ScenarioNumber), class_name=xtmf_ClassName, num_processors='max')

    def InitializeMatrix(self, database, matrixNumber):
        if matrixNumber == 0:
            return None
        matrix_name = "mf" + str(matrixNumber)
        matrix = database.matrix(matrix_name)
        if matrix is None:
            matrix = database.create_matrix(matrix_name)
        return matrix.id
