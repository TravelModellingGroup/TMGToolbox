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
Export Aggregate Average Matrix by Partition

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
    0.1.0 Added XTMF side, which returns the aggregated matrix in third-normalized form as
        a string. Also added the option to export the results in third-normalize form to
        the Modeller side.
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExportAggregateAverageMatrix(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ExportFile = _m.Attribute(str)
    Partition = _m.Attribute(_m.InstanceType)
    xtmf_PartitionId = _m.Attribute(str)
    MatrixIdToAggregate = _m.Attribute(str)
    WeightingMatrixId = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Aggregate Average Matrix v%s" %self.version,
                     description="Exports a result matrix (e.g. travel times), averaged \
                         over a given zone partition for a given matrix (e.g. demand). \
                         Zone groups with a zero summed weight will be averaged equally \
                         over all zones equally.\
                         <br><br><b>Temporary storage requirements:</b> 3 matrices",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name='MatrixIdToAggregate',
                             filter=['FULL'], id=True,
                             title="Matrix to aggregate")
        
        pb.add_select_matrix(tool_attribute_name='WeightingMatrixId',
                             filter=['FULL'], id=True,
                             title="Weighting Matrix")
        
        pb.add_select_partition(tool_attribute_name='Partition',
                                title="Zone Partition")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           title="Matrix Export")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute(True)
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_PartitionId, MatrixIdToAggregate, WeightingMatrixId):
        
        #raise NotImplementedError("XTMF side not yet implemented!")
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found." %xtmf_ScenarioNumber)
        
        self.Partition = _MODELLER.emmebank.partition(xtmf_PartitionId)
        if self.Partition == None:
            raise Exception("Partition '%s' was not found." %xtmf_PartitionId)
        
        self.MatrixIdToAggregate = MatrixIdToAggregate
        self.WeightingMatrixId = WeightingMatrixId
        
        try:
            return self._Execute(False)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self, writeToFile):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with nested(_util.tempMatrixMANAGER(), 
                        _util.tempMatrixMANAGER(),
                        _util.tempMatrixMANAGER())\
                    as (denominatorMatrix, adjustedDemandMatrix, finalAggregateMatrix):
                
                try:
                    partitionAggTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_partition_aggregation')
                    matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
                    exportMatrixTool = _MODELLER.tool('inro.emme.data.matrix.export_matrices')
                except Exception, e:
                    partitionAggTool = _MODELLER.tool('inro.emme.standard.matrix_calculation.matrix_partition_aggregation')
                    matrixCalcTool = _MODELLER.tool('inro.emme.standard.matrix_calculation.matrix_calculator')
                    exportMatrixTool = _MODELLER.tool('inro.emme.standard.data.matrix.export_matrices')
                
                matrixToAggregate = _MODELLER.emmebank.matrix(self.MatrixIdToAggregate)
                finalAggregateMatrix.description = matrixToAggregate.description 
                
                #Copy the weighting matrix into adjustedDemandMatrix
                self.TRACKER.runTool(matrixCalcTool, 
                                     specification=self._GetMatrixCopySpec(adjustedDemandMatrix.id),
                                     scenario = self.Scenario)
                
                #Aggregate weighting matrix into denominatorMatrix
                weightingMatrix = _MODELLER.emmebank.matrix(self.WeightingMatrixId)
                self.TRACKER.runTool(partitionAggTool,
                                     matrix=weightingMatrix,
                                     origin_partition=self.Partition,
                                     destination_partition=self.Partition,
                                     operator='sum',
                                     result_matrix=denominatorMatrix,
                                     scenario=self.Scenario)
                
                #For partitions with no trips (e.g. '0'), weight every cell with '1'
                self.TRACKER.runTool(matrixCalcTool,
                                     specification=self._GetFixDemandSpec(adjustedDemandMatrix.id,
                                                                          denominatorMatrix.id),
                                     scenario=self.Scenario)
                
                #Re-aggregate the denominator from the adjusted demand matrix
                self.TRACKER.runTool(partitionAggTool,
                                     matrix=adjustedDemandMatrix,
                                     origin_partition=self.Partition,
                                     destination_partition=self.Partition,
                                     operator='sum',
                                     result_matrix=denominatorMatrix)
                
                #Calculate the average
                self.TRACKER.runTool(matrixCalcTool,
                    specification=self._GetAggregateAverageSpec(adjustedDemandMatrix.id,
                                                                denominatorMatrix.id,
                                                                finalAggregateMatrix.id),
                    scenario=self.Scenario)
                
                #Return the average matrix
                retVal = partitionAggTool(finalAggregateMatrix, self.Partition, self.Partition)
                
                if writeToFile:
                    title = ["Value Matrix: %s" %matrixToAggregate.description,
                             "Weight Matrix: %s" %weightingMatrix.description,
                             "Partition: %s - %s" %(self.Partition.id, self.Partition.description)]
                    self._WriteToFile(retVal, "\n".join(title))
                
                return retVal
                
    ##########################################################################################################  
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _GetMatrixCopySpec(self, resultMatrixId):
        return {
                "expression": self.WeightingMatrixId,
                "result": resultMatrixId,
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
    
    def _GetFixDemandSpec(self, adjustedDemandMatrixId, denominatorMatrixId):
        return {
                "expression": "1",
                "result": adjustedDemandMatrixId,
                "constraint": {
                    "by_value": {
                        "interval_min": 0,
                        "interval_max": 0,
                        "condition": "INCLUDE",
                        "od_values": denominatorMatrixId
                    },
                    "by_zone": None
                },
                "aggregation": {
                    "origins": None,
                    "destinations": None
                },
                "type": "MATRIX_CALCULATION"
            }
    
    def _GetAggregateAverageSpec(self, adjustedDemandMatrixId, denominatorMatrixId, resultMatrixId):
        expression = "{weight} * {matrix} / {denom}".format(weight=adjustedDemandMatrixId,
                                                            matrix=self.MatrixIdToAggregate,
                                                            denom=denominatorMatrixId)
        
        return {
                "type": "MATRIX_CALCULATION",
                "expression": expression,
                "result": resultMatrixId,
                "aggregation": {
                    "origins": None,
                    "destinations": None
                },
                "constraint": {
                    "by_value": None,
                    "by_zone": None
                }
            }
    
    def _WriteToFile(self, data, title):
        with open(self.ExportFile, 'w') as writer:
            writer.write(title)
            writer.write("\nO D Val\n")
            writer.write(self._MatrixDataToString(data))
    
    @staticmethod
    def _MatrixDataToString(data):
        rows = []
        
        dim1 = data.indices[0]
        dim2 = data.indices[1]
        
        for i, row in enumerate(data.raw_data):
            index1 = dim1[i]
            for j, cell in enumerate(row):
                index2 = dim2[j]
                s = "%s %s %s" %(index1, index2, cell)
                rows.append(s)
        
        return "\n".join(rows)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    