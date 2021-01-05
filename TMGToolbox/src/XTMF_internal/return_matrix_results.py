#---LICENSE----------------------
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
#---METADATA---------------------
'''
[TITLE]

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-13 by pkucirek
     
    0.0.2 Upgraded to use Strategy-based analysis to extract walk-all-way portion of tripsl.
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class SupplementalTransitMatrices(_m.Tool()):
    
    version = '0.0.2'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    xtmf_PartitionId = _m.Attribute(str)
    xtmf_DemandMatrixId = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Return Supplemental Matrices",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_PartitionId, xtmf_DemandMatrixId):
        
        database = _MODELLER.emmebank
        
        #---1 Set up scenario
        scenario = database.scenario(xtmf_ScenarioNumber)
        if (scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        if not scenario.has_transit_results:
            raise Exception("Scenario %s has no transit assignment results" %xtmf_ScenarioNumber)
        
        partition = database.partition(xtmf_PartitionId)
        if partition is None:
            raise Exception("Partition '%s' does not exist" %xtmf_PartitionId)
        
        demandMatrix = database.matrix(xtmf_DemandMatrixId)
        if demandMatrix is None:
            raise Exception("Demand matrix '%s' does not exist" %xtmf_DemandMatrixId)
        
        try:
            return self._Execute(scenario, partition, demandMatrix)
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self, scenario, partition, demandMatrix):
        
        modes = [id for id, type, description in _util.getScenarioModes(scenario, ['TRANSIT', 'AUX_TRANSIT'])]
        strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
        matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')
        partitionAggTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_partition_aggregation')
        partitionAverageTool = _MODELLER.tool('TMG2.Analysis.ExportPartitionAverage')
        
        with nested(_util.tempMatrixMANAGER('Avg Boardings'),\
                    _util.tempMatrixMANAGER('In Vehicle Times')) \
                as (avgBoardingsMatrix, walkAllWayMatrix):
        
            #Extract walk-all-way matrix
            spec = {
                    "trip_components": {
                        "boarding": None,
                        "in_vehicle": "length",
                        "aux_transit": None,
                        "alighting": None
                    },
                    "sub_path_combination_operator": "+",
                    "sub_strategy_combination_operator": ".min.",
                    "selected_demand_and_transit_volumes": {
                        "sub_strategies_to_retain": "FROM_COMBINATION_OPERATOR",
                        "selection_threshold": {
                            "lower": 0,
                            "upper": 0
                        }
                    },
                    "analyzed_demand": None,
                    "constraint": None,
                    "results": {
                        "strategy_values": None,
                        "selected_demand": walkAllWayMatrix.id,
                        "transit_volumes": None,
                        "aux_transit_volumes": None,
                        "total_boardings": None,
                        "total_alightings": None
                    },
                    "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
                }
            strategyAnalysisTool(spec, scenario)
            
            #Extract avg boardings
            spec = {
                    "by_mode_subset": {
                        "modes": modes,
                        "avg_boardings": avgBoardingsMatrix.id,
                    },
                    "type": "EXTENDED_TRANSIT_MATRIX_RESULTS"
                    }
            matrixResultsTool(spec, scenario)
            
            #Get the partition-aggregated results
            #The tool returns the MatrixData object
            walkOnlyResults = partitionAggTool(walkAllWayMatrix, partition, partition, scenario=scenario)
            avgBoardingResults = partitionAverageTool(scenario.id, partition.id, avgBoardingsMatrix.id, demandMatrix.id)
            
            results = {}
            for i, row in enumerate(avgBoardingResults.raw_data):
                origin = avgBoardingResults.indices[0][i]
                for j, cell in enumerate(row):
                    destination = avgBoardingResults.indices[1][j]
                    key = (origin, destination)
                    results[key] = [cell]
            for i, row in enumerate(walkOnlyResults.raw_data):
                origin = walkOnlyResults.indices[0][i]
                for j, cell in enumerate(row):
                    destination = walkOnlyResults.indices[1][j]
                    key = (origin, destination)
                    if not key in results:
                        results[key] = [0.0, cell]
                    else:
                        results[key].append(cell)
            resultList = []
            for key, val in results.iteritems():
                origin, destination = key
                col1 = val[0]
                col2 = val[1]
                resultList.append("%s %s %s %s" %(origin, destination, col1, col2))
            resultList.sort()
            return "\n".join(resultList)
            
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        