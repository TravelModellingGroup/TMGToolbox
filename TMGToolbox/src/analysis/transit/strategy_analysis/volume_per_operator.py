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

    Latest revision by: mattaustin222
    
    
    Tool used to calculate the amount of riders on each operator within the system.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-05-04 by tnikolov
    0.0.2 Created on 2015-11-13 by mattaustin222
'''

import inro.modeller as _m

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os.path import exists
from json import loads as _parsedict
from multiprocessing import cpu_count
from os.path import dirname
import tempfile as _tf
import shutil as _shutil
import csv
import numpy as np
from re import split as _regex_split

_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculator = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
traversalAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.traversal_analysis')
networkResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
matrixCalculator = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
matrixAggregation = _MODELLER.tool('inro.emme.matrix_calculation.matrix_aggregation')
#matrixExportTool = _MODELLER.tool('inro.emme.data.matrix.export_matrices')
matrixExport = _MODELLER.tool('inro.emme.data.matrix.export_matrix_to_csv')
stratAnalysis = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
EMME_VERSION = _util.getEmmeVersion(tuple) 

##########################################################################################################

@contextmanager
def blankContextManager(var= None):
    try:
        yield var
    finally:
        pass

@contextmanager
def getTemporaryFolder():
    folder = _tf.mkdtemp()
    try:
        yield folder
    finally:
        _shutil.rmtree(folder)


class VolumePerOperator(_m.Tool()):
    
    #---PARAMETERS
    xtmf_ScenarioNumbers = _m.Attribute(str)
    FilterString = _m.Attribute(str)             
    VolumeMatrix = _m.Attribute(str)
    filePath = _m.Attribute(str)

    Scenarios = _m.Attribute(_m.ListType)

    #results = {"test": 1.0};
            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   

        #---Set the defaults of parameters used by Modeller
        lines = ["GO Train: mode=r",
                 "GO Bus: mode=g",
                 "Subway: mode=m",
                 "Streetcar: mode=s",
                 "TTC Bus: line=T_____ and mode=bp",
                 "YRT: line=Y_____",
                 "VIVA: line=YV____",
                 "Brampton: line=B_____",
                 "MiWay: line=M_____",
                 "Durham: line=D_____",
                 "Halton: line=H_____",
                 "Hamilton: line=W_____"]
        self.multiclass = False
        self.filtersToCompute = "\n".join(lines)
        self.results = {};     
        
    def run(self):
        self.tool_run_msg = ""
        #self.TRACKER.reset()
        """
        try:
            if self.ExportTransferMatrixFlag or self.ExportWalkAllWayMatrixFlag:
                
                if self.ExportTransferMatrixFlag and not self.VolumeMatrix:
                    raise IOError("No transfer matrix file specified.")
                
                if self.ExportWalkAllWayMatrixFlag:
                    if not self.AggregationPartition: raise TypeError("No aggregation partition specified")
                    if not self.WalkAllWayExportFile: raise TypeError("No walk-all-way matrix file specified")
                    
                self._Execute()
                _MODELLER.desktop.refresh_needed(False)
        except Exception as e:
            _MODELLER.desktop.refresh_needed(False)
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
        """        

        lineFilters = 'Subway:mode=s'

        sc = _MODELLER.emmebank.scenario("12")
        self.Scenarios = []
        self.Scenarios.append(sc)


        self.filtersToCompute = lineFilters
        self._Execute();

                
        with open(r'C:\Users\TMG\Desktop\test.csv', 'wb') as csvfile:               
            writer = csv.writer(csvfile, delimiter=',')
            for line in self.results:
                writer.writerow([line, self.results[line]])                    


    def __call__(self, xtmf_ScenarioNumbers, FilterString, filePath):
        self.tool_run_msg = ""
        print "Starting Ridership Calculations"

        self.Scenarios = []
        for number in xtmf_ScenarioNumbers.split(','):
            sc = _MODELLER.emmebank.scenario(number)
            if (sc is None):
                raise Exception("Scenarios %s was not found!" %number)
            self.Scenarios.append(sc)

        self.filtersToCompute = FilterString
       
        self._Execute()

        with open(filePath, 'wb') as csvfile:               
            writer = csv.writer(csvfile, delimiter=',')
            if self.multiclass == False:
                writer.writerow(["Scenario", "Line Filter", "Ridership"])
                for scenario in sorted(self.results):
                    for lineFilter in sorted(self.results[scenario]):
                        writer.writerow([scenario, lineFilter, self.results[scenario][lineFilter]])
            elif self.multiclass == True:
                writer.writerow(["Scenario", "Line Filter", "Class", "Ridership"])
                for scenario in sorted(self.results):
                    for lineFilter in sorted(self.results[scenario]):
                        for EmmeClass in sorted(self.results[scenario][lineFilter]):
                            writer.writerow([scenario, lineFilter, EmmeClass, self.results[scenario][lineFilter][EmmeClass]])
        
        print "Finished Ridership calculations"

    def _Execute(self):

        if len(self.Scenarios) == 0: raise Exception("No scenarios selected.")      

        parsed_filter_list = self._ParseFilterString(self.filtersToCompute)
        self.NumberOfProcessors = cpu_count()
        for scenario in self.Scenarios:
            self.Scenario = _MODELLER.emmebank.scenario(scenario.id)
            self.results[scenario.id] = {}
            
            for filter in parsed_filter_list:
                demandMatrixId = _util.DetermineAnalyzedTransitDemandId(EMME_VERSION, self.Scenario)
                if type(demandMatrixId) == type(dict()):
                    self.multiclass = True
                    self.results[scenario.id][filter[1]] = {}
                    for key in demandMatrixId:
                        managers = [_util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', description= "Extra attribute"),
                                    _util.tempMatrixMANAGER('Intermediate operator counts', 'FULL'),
                                    _util.tempMatrixMANAGER('Aggregated operator counts', 'SCALAR')]       
                        with nested(*managers) as (operatorMarker, tempIntermediateMatrix, tempResultMatrix):
                            networkCalculator(self.assign_line_filter(filter[1], operatorMarker), scenario=self.Scenario)
                            if EMME_VERSION >= (4, 3, 2):
                                report = stratAnalysis(self.count_ridership(operatorMarker, tempIntermediateMatrix, demandMatrixId[key]), scenario=self.Scenario, class_name=key, num_processors = self.NumberOfProcessors)
                            else:
                                report = stratAnalysis(self.count_ridership(operatorMarker, tempIntermediateMatrix, demandMatrixId[key]), scenario=self.Scenario, class_name=key)
                            tempMatrix = _MODELLER.emmebank.matrix(tempIntermediateMatrix.id)
                            numpyData = tempMatrix.get_numpy_data(scenario_id = scenario.id)
                            count = 0 
                            for i in range(numpyData.shape[0]-1):
                                if numpyData[i,i] != 0:
                                    numpyData[i,i] = 0
                                    count += 1
                            tempMatrix.set_numpy_data(numpyData, scenario_id = scenario.id)
                            matrixCalculator(self._CalcRidership(tempIntermediateMatrix.id, demandMatrixId[key]), scenario=self.Scenario)
                            matrixAggregation(tempIntermediateMatrix.id, tempResultMatrix.id, agg_op="+", scenario=self.Scenario)
                            self.results[scenario.id][filter[1]][key] = tempResultMatrix.data
                else:
                    self.multiclass = False
                    managers = [_util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', description= "Extra attribute"),
                                    _util.tempMatrixMANAGER('Intermediate operator counts', 'FULL'),
                                    _util.tempMatrixMANAGER('Aggregated operator counts', 'SCALAR')]
                    with nested(*managers) as (operatorMarker, tempIntermediateMatrix, tempResultMatrix):
                        networkCalculator(self.assign_line_filter(filter[1], operatorMarker), scenario=self.Scenario)
                        if EMME_VERSION >= (4, 3, 2):
                            report = stratAnalysis(self.count_ridership(operatorMarker, tempIntermediateMatrix, demandMatrixId), scenario=self.Scenario, num_processors = self.NumberOfProcessors)  
                        else:
                            report = stratAnalysis(self.count_ridership(operatorMarker, tempIntermediateMatrix, demandMatrixId), scenario=self.Scenario)
                        tempMatrix = _MODELLER.emmebank.matrix(tempIntermediateMatrix.id)
                        numpyData = tempMatrix.get_numpy_data(scenario_id = scenario.id)
                        count = 0 
                        for i in range(numpyData.shape[0]):
                            if numpyData[i,i] != 0:
                                numpyData[i,i] = 0
                                count += 1
                        tempMatrix.set_numpy_data(numpyData, scenario_id = scenario.id)                         
                        matrixCalculator(self._CalcRidership(tempIntermediateMatrix.id, demandMatrixId), scenario=self.Scenario)
                        matrixAggregation(tempIntermediateMatrix.id, tempResultMatrix.id, agg_op="+", scenario=self.Scenario)         
                        self.results[scenario.id][filter[1]] =  tempResultMatrix.data

    def assign_line_filter(self, lineFilter, marker):
        return {"result": marker.id,
                    "expression": "1",
                    "aggregation": None,
                    "selections": {
                        "transit_line": lineFilter
                        },
                    "type": "NETWORK_CALCULATION"
                }

    def count_ridership(self, operator, tempIntermediateMatrix, demandMatrixId):
        ret = {
                "trip_components": {
                    "boarding": operator.id,
                    "in_vehicle": None,
                    "aux_transit": None,
                    "alighting": None
                },
                "sub_path_combination_operator": ".max.",
                "sub_strategy_combination_operator": "average",
                "selected_demand_and_transit_volumes": {
                    "sub_strategies_to_retain": "ALL",
                    "selection_threshold": {
                        "lower": -999999,
                        "upper": 999999
                    }
                },
                "analyzed_demand": demandMatrixId,
                "constraint": None,
                "results": {
                    "strategy_values": tempIntermediateMatrix.id,
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        return ret

    def _CalcRidership(self, fractionMatrixId, demandMatrixId):

        return {
                "expression": fractionMatrixId + " * " + demandMatrixId,
                "result": fractionMatrixId,
                "constraint": {
                    "by_value": None,
                    "by_zone": None
                },
                "aggregation": {
                    "origins": None,
                    "destinations": None
                },
                "type": "MATRIX_CALCULATION"
            }

    def _ParseFilterString(self, filterString):
        filterList = []
        components = _regex_split('\n|,', filterString) #Supports newline and/or commas
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 2:
                msg = "Error parsing penalty and filter string: Separate label and filter with colons label:filter"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            strippedParts = [item.strip() for item in parts]
            filterList.append(strippedParts)

        return filterList