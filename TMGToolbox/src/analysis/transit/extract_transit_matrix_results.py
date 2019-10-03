"""
    Copyright 2018 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
import traceback as _traceback
import time as _time
import math
from contextlib import contextmanager
from contextlib import nested
from multiprocessing import cpu_count
from re import split as _regex_split
from json import loads as _parsedict
import inro.modeller as _m
import csv
_trace = _m.logbook_trace
_MODELLER = _m.Modeller()
_bank = _MODELLER.emmebank
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_netEdit = _MODELLER.module('tmg.common.network_editing')
matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')
matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

class ExtractTransitMatrixResults(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    xtmf_ModeList = _m.Attribute(str)
    xtmf_MatrixNumbers = _m.Attribute(str)
    xtmf_AnalysisTypes = _m.Attribute(str)
    xtmf_ClassNames = _m.Attribute(str)
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.scenario = _MODELLER.scenario #Default is primary scenario
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Multi-Class Road Assignment",
                description="Cannot be called from Modeller.",
                runnable=False,
                branding_text="XTMF")
        return pb.render()

    
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_ModeList, xtmf_MatrixNumbers, xtmf_AnalysisTypes, xtmf_ClassNames):
        
        # Set up scenario
        self.scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        #set up mode lists
        modes = xtmf_ModeList.strip(" ").split(",")
        self.ModeList = []
        for i in range(0,len(modes)):
            self.ModeList.append([])
            for mode in modes[i]:
                self.ModeList[i].append(mode)
        self.MatrixIDList = xtmf_MatrixNumbers.strip(" ").split(",")

        if len(self.ModeList) != len(self.MatrixIDList):
            raise Exception("Each analysis must have mode(s) and matrices defined")

        self.AnalysisTypeList = []
        types = xtmf_AnalysisTypes.strip(" ").split(",")
        for i in range(0, len(types)):
            if types[i].lower() == "distance":
                self.AnalysisTypeList.append(1)
            elif types[i].lower() == "actualtime":
                self.AnalysisTypeList.append(2)
            elif types[i].lower() == "actualcost":
                self.AnalysisTypeList.append(3)
            elif types[i].lower() == "perceivedtime":
                self.AnalysisTypeList.append(4)
            elif types[i].lower() == "perceivedcost":
                self.AnalysisTypeList.append(5)
            else:
                raise Exception ("You must specify a proper analysis type")

        self.ClassNames = xtmf_ClassNames.strip(" ").split(",")
        names = _util.DetermineAnalyzedTransitDemandId(EMME_VERSION, self.scenario)
        
        if isinstance(names, dict):
            self.Multiclass = True
            for name in self.ClassNames:
                if name not in names.keys():
                    raise Exception ("Class Name %s is not correct" %name)
        else:
            self.Multiclass = False

        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            print "Extracting Transit Result Matrices"
            if not self.scenario.has_transit_results:
                raise Exception("Scenario %s has no transit results" %self.scenario)

            #initialize the matrices
            for matrix in self.MatrixIDList:
                _util.initializeMatrix(matrix)

            with self._getTempMatrices():

                #Get Spec and do Analysis

                for i in range(0,len(self.ModeList)):
                    spec = self._GetBaseSpec(self.ModeList[i], self.TempMatrices, self.AnalysisTypeList[i])
                    if self.Multiclass == True:
                        report = self.TRACKER.runTool(matrixResultsTool, specification = spec, scenario = self.scenario, class_name = self.ClassNames[i])
                    else:
                        report = self.TRACKER.runTool(matrixResultsTool, specification = spec, scenario = self.scenario)
                    spec = {
                        "type": "MATRIX_CALCULATION",
                        "result": self.MatrixIDList[i],
                        "expression": str(self.TempMatrices[0].id)+"+"+str(self.TempMatrices[1].id),
                        "constraint": None
                        }
                    report = self.TRACKER.runTool(matrixCalcTool, specification = spec, scenario = self.scenario)

            print "Finished Extracting Transit Result Matrices"

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.scenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _GetBaseSpec(self, modeList, matrix, analysisType):
        spec = {
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
            "by_mode_subset": {
                "modes": modeList,
                "distance": None,
                "avg_boardings": None,
                "actual_total_boarding_times": None,
                "actual_in_vehicle_times": None,
                "actual_aux_transit_times": None,
                "actual_total_boarding_costs": None,
                "actual_in_vehicle_costs": None,
                "actual_aux_transit_costs": None,
                "perceived_total_boarding_times": None,
                "perceived_in_vehicle_times": None,
                "perceived_aux_transit_times": None,
                "perceived_total_boarding_costs": None,
                "perceived_in_vehicle_costs": None,
                "perceived_aux_transit_costs": None,
            }
        }
        if analysisType == 1:
            spec["by_mode_subset"]["distance"] = matrix[0].id
        if analysisType == 2:
            spec["by_mode_subset"]["actual_in_vehicle_times"] = matrix[0].id
            spec["by_mode_subset"]["actual_aux_transit_times"] = matrix[1].id
        if analysisType == 3:
            spec["by_mode_subset"]["actual_in_vehicle_costs"] = matrix[0].id
            spec["by_mode_subset"]["actual_aux_transit_costs"] = matrix[1].id
        if analysisType == 4:
            spec["by_mode_subset"]["perceived_in_vehicle_times"] = matrix[0].id
            spec["by_mode_subset"]["perceived_aux_transit_times"] = matrix[1].id
        if analysisType == 5:
            spec["by_mode_subset"]["perceived_in_vehicle_costs"] = matrix[0].id
            spec["by_mode_subset"]["perceived_aux_transit_costs"] = matrix[1].id
        return spec
    
    @contextmanager
    def _getTempMatrices(self):
        self.TempMatrices = []
        created = {}
        for i in range(0,2):
            matrixCreated = True
            mtx = _util.initializeMatrix(default=0.0, description= 'Temporary matrix for matrix results', \
                        matrix_type='FULL')
            self.TempMatrices.append(mtx)
            created[mtx.id] = matrixCreated
        try:
            yield self.TempMatrices
        finally:
            for key in created:
                if created[key] == True:
                    _bank.delete_matrix(key) 