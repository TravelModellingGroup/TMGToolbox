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
Extract Transit Origin and Destination Vectors

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    Runs a path analysis for a given line filter and outputs  
    origin and destination vectors. Combines both walk-access
    and drive-access trips.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-06-19 by mattaustin222
    
'''

import inro.modeller as _m
import inro.emme.matrix as _matrix
import traceback as _traceback
import numpy as np
from contextlib import contextmanager
from contextlib import nested
from multiprocessing import cpu_count
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculation = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
pathAnalysis = _m.Modeller().tool("inro.emme.transit_assignment.extended.path_based_analysis")
matrixAgg = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_aggregation")
matrixCopy = _m.Modeller().tool("inro.emme.data.matrix.copy_matrix")
matrixCalc = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

class ExtractTransitODVectors(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int)
    
    Scenario = _m.Attribute(_m.InstanceType)
    LineFilterExpression = _m.Attribute(str)

    LineODMatrixId = _m.Attribute(str)
    AggOriginMatrixId = _m.Attribute(str)
    AggDestinationMatrixId = _m.Attribute(str)
    AutoODMatrixId = _m.Attribute(str)

    xtmf_LineODMatrixNumber = _m.Attribute(int)
    xtmf_AggOriginMatrixNumber = _m.Attribute(int)
    xtmf_AggDestinationMatrixNumber = _m.Attribute(int)
    xtmf_AutoODMatrixId = _m.Attribute(int)

    NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario

        self.NumberOfProcessors = cpu_count()
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Transit Origin and Destination Vectors v%s" %self.version,
                     description="For a given subgroup of transit lines, this tool \
                         constructs origin and destination vectors for combined \
                         walk-access and drive-access trips",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='LineFilterExpression',
                        title="Line Filter Expression",
                        size=100, multi_line=True)

        pb.add_select_output_matrix(tool_attribute_name='LineODMatrixId',
                                title="Line OD Matrix",
                                include_none=False,
                                include_existing=True,
                                include_new=True)

        pb.add_select_output_matrix(tool_attribute_name='AggOriginMatrixId',
                                matrix_types=['ORIGIN'],
                                title="Aggregate Origin Vector",
                                include_none=False,
                                include_existing=True,
                                include_new=True)

        pb.add_select_output_matrix(tool_attribute_name='AggDestinationMatrixId',
                                matrix_types=['DESTINATION'],
                                title="Aggregate Destination Vector",
                                include_none=False,
                                include_existing=True,
                                include_new=True)
                                

        pb.add_select_matrix(tool_attribute_name='AutoODMatrixId',
                                title="Auto OD Matrix",                                 
                                filter=['FULL'],
                                allow_none=False,
                                id=True)
        
        return pb.render()

    ##########################################################################################################
        
    def __call__(self, xtmf_ScenarioNumber, LineFilterExpression, xtmf_LineODMatrixNumber,
                  xtmf_AggOriginMatrixNumber, xtmf_AggDestinationMatrixNumber, xtmf_AutoODMatrixId):

        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        self.LineFilterExpression = LineFilterExpression

        self.AutoODMatrixId = "mf%s" %xtmf_AutoODMatrixId

        if _MODELLER.emmebank.matrix(self.AutoODMatrixId) == None:
            raise Exception("Matrix %s was not found!" %self.AutoODMatrixId)

        self.LineODMatrixId = xtmf_LineODMatrixNumber
        _util.initializeMatrix(self.LineODMatrixId, name='lineOD', description= 'Demand for selected lines')
        self.AggOriginMatrixId = xtmf_AggOriginMatrixNumber
        _util.initializeMatrix(self.AggOriginMatrixId, name='aggO', 
                               description= 'Origins for selected lines', matrix_type= 'ORIGIN')
        self.AggDestinationMatrixId = xtmf_AggDestinationMatrixNumber
        _util.initializeMatrix(self.AggDestinationMatrixId, name='aggD', 
                               description= 'Destinations for selected lines', matrix_type= 'DESTINATION')

        try:           
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done")    

    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        _util.initializeMatrix(self.LineODMatrixId, name='lineOD', description= 'Demand for selected lines')
        _util.initializeMatrix(self.AggOriginMatrixId, name='aggO', 
                               description= 'Origins for selected lines', matrix_type= 'ORIGIN')
        _util.initializeMatrix(self.AggDestinationMatrixId, name='aggD', 
                               description= 'Destinations for selected lines', matrix_type= 'DESTINATION')
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done")    
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
                        
            with nested(_util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', description= 'Line Flag'),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK', description= 'Flagged Line Aux Tr Volumes'),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT', description= 'Flagged Line Tr Volumes'),
                        _util.tempMatrixMANAGER(description="Origin Probabilities", matrix_type='FULL'),              
                        _util.tempMatrixMANAGER(description="Destinations Probabilities", matrix_type='FULL'),
                        _util.tempMatrixMANAGER(description="DAT Origin Aggregation", matrix_type='ORIGIN'),
                        _util.tempMatrixMANAGER(description="DAT Destination Aggregation", matrix_type='DESTINATION')) \
                    as (lineFlag, auxTransitVolumes, transitVolumes, origProbMatrix, destProbMatrix, tempDatOrig, tempDatDest): 

                with _m.logbook_trace("Flagging chosen lines"):
                    networkCalculation(self._BuildNetCalcSpec(lineFlag.id), scenario=self.Scenario)
                with _m.logbook_trace("Running path analysis"):    
                    pathAnalysis(self._BuildPathSpec(lineFlag.id, transitVolumes.id, auxTransitVolumes.id), scenario=self.Scenario)

                with _m.logbook_trace("Aggregating WAT matrices"):
                    matrixAgg(self.LineODMatrixId, self.AggOriginMatrixId, agg_op="+")
                    matrixAgg(self.LineODMatrixId, self.AggDestinationMatrixId, agg_op="+")
                with _m.logbook_trace("Copying auto matrices"):
                    #This part may be able to be condensed. Can likely just carry forward the normal auto matrix and save calculations over top of
                    #the probability matrices
                    autoOrigMatrix = matrixCopy(self.AutoODMatrixId, None, matrix_name="autoOrigFull", matrix_description="", 
                                                scenario=self.Scenario)
                    autoDestMatrix = matrixCopy(self.AutoODMatrixId, None, matrix_name="autoDestFull", matrix_description="", 
                                                scenario=self.Scenario)
                with _m.logbook_trace("Building probability matrices"):
                    network = self.Scenario.get_network()
                    nodes = range(9700,9999) #consider allowing user inputted range later on
                    #Create a dictionary of origin/destination probabilities for the line group for all selected nodes 
                    stationProbs = self._CalcODProbabilities(network, nodes, auxTransitVolumes.id)
                    #Convert the dictionary in an origin and a destination probability matrix
                    self._ApplyODProbabilities(stationProbs, origProbMatrix, 'ORIGIN')
                    self._ApplyODProbabilities(stationProbs, destProbMatrix, 'DESTINATION')
                    #Multiply the probability matrices by the auto demand matrix to yield origin and destination DAT demands for the selected nodes
                    if EMME_VERSION >= (4,2,1):
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(origProbMatrix.id, " * ", autoOrigMatrix.id, autoOrigMatrix.id), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(destProbMatrix.id, " * ", autoDestMatrix.id, autoDestMatrix.id), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                    else:                    
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(origProbMatrix.id, " * ", autoOrigMatrix.id, autoOrigMatrix.id), self.Scenario)
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(destProbMatrix.id, " * ", autoDestMatrix.id, autoDestMatrix.id), self.Scenario)
                with _m.logbook_trace("Aggregating DAT demand and producing final O & D matrices"):
                    #Aggregate the adjusted DAT matrices
                    matrixAgg(autoOrigMatrix.id, tempDatOrig.id, agg_op="+")
                    matrixAgg(autoDestMatrix.id, tempDatDest.id, agg_op="+")
                    #Find the total O & D matrices
                    if EMME_VERSION >= (4,2,1):
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(autoOrigMatrix.id, " + ", self.AggOriginMatrixId, self.AggOriginMatrixId), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(autoDestMatrix.id, " + ", self.AggDestinationMatrixId, self.AggDestinationMatrixId), self.Scenario,
                                             num_processors=self.NumberOfProcessors)
                    else:
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(tempDatOrig.id, " + ", self.AggOriginMatrixId, self.AggOriginMatrixId), self.Scenario)
                        matrixCalc(self._BuildSimpleMatrixCalcSpec(tempDatDest.id, " + ", self.AggDestinationMatrixId, self.AggDestinationMatrixId), self.Scenario)

            _MODELLER.desktop.refresh_needed(True) #Tell the desktop app that a data refresh is required
                    
                    

    ##########################################################################################################

    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version,
                "Line Selector Expression": self.LineFilterExpression,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _BuildNetCalcSpec(self, resultAttId):
        spec = {
                "result": resultAttId,
                "expression": "1",
                "aggregation": None,
                "selections": {
                    "transit_line": self.LineFilterExpression
                },
                "type": "NETWORK_CALCULATION"
            }

        return spec

    def _BuildPathSpec(self, tripComponentId, voltrId, volaxId):
        spec = {
                "type": "EXTENDED_TRANSIT_PATH_ANALYSIS",
                "portion_of_path": "COMPLETE",
                "trip_components": {
                    "initial_boarding": tripComponentId,
                    "transfer_boarding": tripComponentId
                },
                "path_operator": ".max.",
                "path_selection_threshold": {
                    "lower": 1,
                    "upper": 1
                },
                "results_from_retained_paths": {
                    "paths_to_retain": "SELECTED",
                    "demand": self.LineODMatrixId,
                    "transit_volumes": voltrId,
                    "aux_transit_volumes": volaxId
                }
            }

        return spec

    def _BuildSimpleMatrixCalcSpec(self, input1MatrixId, operator, input2MatrixId, outputMatrixId):
        #takes in 3 matrix ids and an operator. The operator is applied to the first two matrices and outputted to the third
        spec = {
                "type": "MATRIX_CALCULATION",
                "result": outputMatrixId,
                "expression": input1MatrixId + operator + input2MatrixId}

        return spec

    def _CalcODProbabilities(self, network, nodeSet, flaggedVolaxId):
        probDict = {}
        for node in network.centroids():
            if node.number in nodeSet:
                flaggedInTotal = 0
                inTotal = 0
                for link in node.incoming_links():
                    flaggedInTotal += link[flaggedVolaxId]
                    inTotal += link.aux_transit_volume
                flaggedOutTotal = 0
                outTotal = 0
                for link in node.outgoing_links():
                    flaggedOutTotal += link[flaggedVolaxId]
                    outTotal += link.aux_transit_volume
                try:
                    destProb = flaggedInTotal / inTotal
                except:
                    destProb = 0
                try:
                    origProb = flaggedOutTotal / outTotal
                except:
                    origProb = 0 #if no volume, set to 0
                
                probDict[node.number] = (origProb, destProb)
        for key, prob in probDict.iteritems():
            if prob[0] >0:
                print (key, prob[0])
        return probDict

    def _ApplyODProbabilities(self, inputProbs, outputMatrix, probType):
        zoneList = self.Scenario.zone_numbers
        probMatrix = np.zeros((len(zoneList), len(zoneList)))
        if probType == 'ORIGIN':
            for key, probs in inputProbs.iteritems(): #iterate through the probability dictionary
                location = zoneList.index(key) #index the current station parking node in the zone list
                probMatrix[:,location] = probs[0] #insert a column (with the line group probability) at the station parking node location in the matrix
        elif probType == 'DESTINATION':
            for key, probs in inputProbs.iteritems(): #iterate through the probability dictionary
                location = zoneList.index(key) #index the current station parking node in the zone list
                probMatrix[location, :] = probs[1] #insert a row (with the line group probability) at the station parking node location in the matrix
        else:
            raise Exception("Need to specify either ORIGIN or DESTINATION")

        if EMME_VERSION >= (4,2):
            print outputMatrix.id
            outputMatrix.set_numpy_data(probMatrix, scenario_id=self.Scenario.id) # set the probability matrix data to the matrix we created earlier
        elif EMME_VERSION >= (4,1,2):
            zoneSystem = [self.Scenario.zone_numbers] * 2
            matrix_data = _matrix.MatrixData(zoneSystem, type='f') 
            matrix_data.from_numpy(probMatrix) #pull the data from the probability Matrix
            outputMatrix.set_data(matrix_data, self.Scenario.id) #and set it to the matrix we created earlier
        else:
            raise Exception("Please upgrade to at least Emme 4.1.2 to use this tool")
                        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        