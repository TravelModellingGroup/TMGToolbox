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
Extract Line Group Transfer Matrix

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-04-04 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import tempfile as _tf
import shutil as _shutil
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExtractLineGroupTransferMatrix(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ExportFile = _m.Attribute(str)
    DemandMatrixId = _m.Attribute(str)
    
    LINE_GROUPS = [(1, "line=B_____", "Brampton"),
                   (2, "line=D_____", "Durham"),
                   (3, "mode=g", "GO Bus"),
                   (4, "mode=r", "GO Train"),
                   (5, "line=H_____", "Halton"),
                   (6, "line=W_____", 'Hamilton'),
                   (7, "line=M_____", "Mississauga"),
                   (8, "mode=s", "Streetcar"),
                   (9, "mode=m", "Subway"),
                   (10, "line=T_____ and mode=b", "TTC Bus"),
                   (12, "line=Y_____", "YRT"),
                   (11, "line=YV____", "VIVA")]
    
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="[TOOL NAME] v%s" %self.version,
                     description="[DESCRIPTION]",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name= 'ExportFile',
                           window_type='save_file',
                           title= "Exprot File")
        
        pb.add_select_matrix(tool_attribute_name= 'DemandMatrixId',
                             filter=['FULL'], allow_none=True, id=True,
                             title= "Demand to Analyze",
                             note= "If set to None, the tool will use the demand matrix from the assignment, \
                                 however this will affect run time for this tool.")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            resultMatrix = self._Execute()
            self._WriteExportFile(resultMatrix)
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumber, DemandMatrixId):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            return self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with nested(_util.tempMatrixMANAGER('Temp walk-all-way matrix'),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', description= 'Temp line group flag attribute'),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT', description= 'Temp initial boardings attribute'),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT', description= 'Temp final alightings attribute')) \
                    as (tempMatrix, flagAttribute, boardingAttribute, alightingsAttribute):
                
                with _m.logbook_trace("Flag line groups"):
                    self._FlagLineGroups(flagAttribute.id)
                
                with _m.logbook_trace("Extract transfer matrix"):
                    with self._TempDirectoryMANAGER() as dir:
                        tempFile = dir + "/traversalMatrix.311"
                        self._RunTransversalAnalysis(flagAttribute.id, tempFile)
                        resultMatrix = self._ParseTraversalResults(tempFile)
                
                with _m.logbook_trace("Export initial boardings and final alightings"):
                    self._RunNetworkResults(boardingAttribute.id, alightingsAttribute.id)
                    self._GetBoardingsAndAlightings(flagAttribute.id, boardingAttribute.id, alightingsAttribute.id, resultMatrix)
                
                with _m.logbook_trace("Export walk-all-way total"):
                    self._CalcWalkAllWayMatrix(tempMatrix.id)
                    self._GetWalkAllWayMatrix(tempMatrix.id, resultMatrix)
                
                return resultMatrix

    ##########################################################################################################   
    
    @contextmanager
    def _TempDirectoryMANAGER(self):
        foldername = _tf.mkdtemp()
        _m.logbook_write("Created temporary directory at '%s'" %foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            #_os.removedirs(foldername)
            _m.logbook_write("Deleted temporary directory at '%s'" %foldername)
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Export File": self.ExportFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _FlagLineGroups(self, flagAttributeId):
        
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        
        def flagGroup(value, selector):
            spec= {
                    "result": flagAttributeId,
                    "expression": str(value),
                    "aggregation": None,
                    "selections": {
                        "transit_line": selector
                    },
                    "type": "NETWORK_CALCULATION"
                }
            tool(spec, scenario=self.Scenario)
        
        self.TRACKER.startProcess(len(self.LINE_GROUPS))
        for value, selector, name in self.LINE_GROUPS:
            flagGroup(value, selector)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
    
    def _RunTransversalAnalysis(self, flagAttributeId, tempFile):
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.traversal_analysis')
        
        spec = {
                "portion_of_path": "COMPLETE",
                "gates_by_trip_component": {
                    "in_vehicle": None,
                    "aux_transit": None,
                    "initial_boarding": None,
                    "transfer_boarding": flagAttributeId,
                    "transfer_alighting": flagAttributeId,
                    "final_alighting": None
                },
                "analyzed_demand": self.DemandMatrixId,
                "path_analysis": None,
                "type": "EXTENDED_TRANSIT_TRAVERSAL_ANALYSIS"
            }
        
        if self.DemandMatrixId != None:
            spec['constraint'] = {
                                    "by_value": {
                                        "interval_min": 0,
                                        "interval_max": 0,
                                        "condition": "EXCLUDE",
                                        "od_values": self.DemandMatrixId
                                    },
                                    "by_zone": None
                                }
        else:
            spec['constraint'] = None
        
        self.TRACKER.runTool(tool, spec, tempFile, scenario=self.Scenario)
    
    def _ParseTraversalResults(self, tempFile):
        _m.logbook_write("Parsing traversal matrix")
        retval = {}
        
        with open(tempFile) as reader:
            line = ""
            while not line.startswith("a"):
                line = reader.readline()
            for line in reader:
                cells = line.strip().split()
                if len(cells) != 3: continue
                o = int(cells[0])
                d = int(cells[1])
                val = float(cells[2])
                od = (o,d)
                retval[od] = val
        return retval
    
    def _RunNetworkResults(self, boardingAttributeId, alightingAttributeId):
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
        
        spec= {
                "on_links": None,
                "on_segments": {
                    "initial_boardings": boardingAttributeId,
                    "final_alightings": alightingAttributeId
                },
                "aggregated_from_segments": None,
                "analyzed_demand": None,
                "constraint": None,
                "type": "EXTENDED_TRANSIT_NETWORK_RESULTS"
            }
        
        self.TRACKER.runTool(tool, spec, self.Scenario)
    
    def _GetBoardingsAndAlightings(self, flagAttributeId, boardingAttributeId, alightingAttributeId, resultMatrix):
        
        lineGroups = _util.fastLoadTransitLineAttributes(self.Scenario, [flagAttributeId])
        segmentData = _util.fastLoadTransitSegmentAttributes(self.Scenario, [boardingAttributeId, alightingAttributeId])
        
        groupData = {}
        
        for lineId, lineData in lineGroups.iteritems():
            groupId = lineData[flagAttributeId]
            
            segments = segmentData[lineId]
            initalBoardings = 0.0
            finalAlightings = 0.0
            for data in segments:
                initalBoardings += data[boardingAttributeId]
                finalAlightings += data[alightingAttributeId]
            if groupId in groupData:
                tup = groupData[groupId]
                tup[0] += initalBoardings
                tup[1] += finalAlightings
            else:
                groupData[groupId] = [initalBoardings, finalAlightings]
        
        for groupId, data in groupData.iteritems():
            initalBoardings, finalAlightings = data
            resultMatrix[(0, int(groupId))] = initalBoardings
            resultMatrix[(int(groupId)), 0] = finalAlightings
        
        self.TRACKER.completeTask()
        
        '''
        with open(self.ExportFile, 'a') as writer:
            for groupId, data in groupData.iteritems():
                initalBoardings, finalAlightings = data
                writer.write("\n0 %s %s" %(groupId, initalBoardings)) 
                writer.write("\n%s 0 %s" %(groupId, finalAlightings)) 
        '''
        
        
    def _CalcWalkAllWayMatrix(self, tempMatrixId):
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
        
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
                        "selected_demand": tempMatrixId,
                        "transit_volumes": None,
                        "aux_transit_volumes": None,
                        "total_boardings": None,
                        "total_alightings": None
                    },
                    "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
                }
        
        self.TRACKER.runTool(tool, spec, self.Scenario)
    
    def _GetWalkAllWayMatrix(self, tempMatrixId, resultMatrix):
        tool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
        spec = {
                "expression": tempMatrixId,
                "result": None,
                "constraint": {
                    "by_value": None,
                    "by_zone": None
                },
                "aggregation": {
                    "origins": "+",
                    "destinations": "+"
                },
                "type": "MATRIX_CALCULATION"
            }
        retval = self.TRACKER.runTool(tool, spec, scenario=self.Scenario)
        walkAllWayResults = retval['result']
        
        resultMatrix[(0,0)] = walkAllWayResults
        
        '''
        with open(self.ExportFile, 'a') as writer:
            writer.write("\n0 0 %s" %walkAllWayResults)
        '''
    
    def _WriteExportFile(self, resultMatrix):
        with open(self.ExportFile, 'w') as writer:
            groups = [(0, 'None')] + [(id, name) for id, selector, name in self.LINE_GROUPS]
            header = ",".join([''] + [name for id, name in groups])
            writer.write(header)
            
            for origin, name in groups:
                data = [name]
                for destination, name in groups:
                    od = (origin, destination)
                    if not od in resultMatrix:
                        val = 0.0
                    else:
                        val = resultMatrix[od]
                    data.append(str(val))
                line = "\n" + ",".join(data)
                writer.write(line)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        