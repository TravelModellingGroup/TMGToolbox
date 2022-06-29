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
    0.0.1 Created on 2014-03-07 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class LineGroup():
    __slots__ = ['index', 'filter', 'name']
    
    def __init__(self, index, filter, name):
        self.index = index
        self.filter = filter
        self.name = name
    
    def select(self, scenario, attId):
        spec= {
                    "result": attId,
                    "expression": str(self.index),
                    "aggregation": None,
                    "selections": {
                        "transit_line": self.filter
                    },
                    "type": "NETWORK_CALCULATION"
                }
        
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        tool(spec, scenario= scenario)

class ReturnBoardingTypesByLineGroup(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    
    LINE_GROUPS = [
                    LineGroup(0,"mode=m","subway"),
                    LineGroup(1,"mode=s","streetcar"),
                    LineGroup(2,"mode=b and line=T_____","ttc_bus"),
                    LineGroup(3,"mode=r","go_train"),
                    LineGroup(4,"mode=g","go_bus"),
                    LineGroup(5,"line=Y_____","yrt"),
                    LineGroup(6,"line=YV____","viva"),
                    LineGroup(7,"line=D_____","durham"),
                    LineGroup(8,"line=B_____","brampton"),
                    LineGroup(9,"line=M_____","mississauga"),
                    LineGroup(10,"line=H_____","halton"),
                    LineGroup(11,"line=W_____","hamilton")
                    ]
    
    LINE_GROUP_MAP = dict([(group.index, group) for group in LINE_GROUPS])
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Return Boarding Types by Line Group",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
            
    def __call__(self, xtmf_ScenarioNumber):
        
        #---1 Set up scenario
        scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            return self._Execute(scenario)
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self, scenario):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with _util.tempExtraAttributeMANAGER(scenario, 'TRANSIT_LINE') as lineTypeAttribute:
                self._CalcLineType(scenario, lineTypeAttribute.id)
                lineTypes = self._GetLineTypes(scenario, lineTypeAttribute.id)
                self.TRACKER.completeTask()
            
            with _util.tempExtraAttributeMANAGER(scenario, 'TRANSIT_SEGMENT') as iBoardAttribiute, _util.tempExtraAttributeMANAGER(scenario, 'TRANSIT_SEGMENT') as tBoardAttribute:
                self._ApplyAnalysis(scenario, iBoardAttribiute.id, tBoardAttribute.id)
                lineBoardings = self._GetLineResults(scenario, iBoardAttribiute.id, tBoardAttribute.id)
            
        groupResults = {}
        self.TRACKER.startProcess(len(lineBoardings))
        for lineId, initialBoardings, transferBoardings in lineBoardings:
            type = lineTypes[lineId]
            typeName = self.LINE_GROUP_MAP[type].name
            
            if not typeName in groupResults:
                groupResults[typeName] = [initialBoardings, transferBoardings]
            else:
                groupResults[typeName][0] += initialBoardings
                groupResults[typeName][1] += transferBoardings
            self.TRACKER.completeSubtask()
        
        results = []
        for group in self.LINE_GROUPS:
            tup = groupResults[group.name]
            results.append(tup)
            
        return str(results) 
                
    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _CalcLineType(self, scenario, attId):
        for group in self.LINE_GROUPS:
            group.select(scenario, attId)
            
    def _GetLineTypes(self, scenario, ltypeAttributeId):
        #Performs a partial read of the network. The data structure is undocumented
        # so this method is subject to change in future versions of Emme.
        
        q = scenario.get_attribute_values('TRANSIT_LINE', [ltypeAttributeId])
        indices = q[0]
        values = q[1]
        
        retval = {}
        for id, index in six.iteritems(indices):
            id = str(id) #Normally stored in unicode.
            retval[id] = int(values[index])
        return retval
    
    def _ApplyAnalysis(self, scenario, iBoardAttributeId, tBoardAttributeId):
        spec = {
                "on_links": None,
                "on_segments": {
                    "transit_volumes": None,
                    "initial_boardings": iBoardAttributeId,
                    "transfer_boardings": tBoardAttributeId,
                    "total_boardings": None,
                    "final_alightings": None,
                    "transfer_alightings": None,
                    "total_alightings": None,
                    "thru_passengers": None
                },
                "aggregated_from_segments": None,
                "analyzed_demand": None,
                "constraint": None,
                "type": "EXTENDED_TRANSIT_NETWORK_RESULTS"
            }
        
        tool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
        self.TRACKER.runTool(tool, spec, scenario)
    
    def _GetLineResults(self, scenario, iBoardAttributeId, tBoardAttributeId):
        #Performs a partial read of the network. The data structure is undocumented
        # so this method is subject to change in future versions of Emme.
        
        q = scenario.get_attribute_values('TRANSIT_SEGMENT', [iBoardAttributeId, tBoardAttributeId])
        indices = q[0]
        iBoardArray = q[1]
        tBoardarray = q[2]
        
        retVal = []
        for id, segmentIndices in six.iteritems(indices):
            id = str(id) #Normally stored in unicode.
            
            valueIndices = segmentIndices[1]
            
            iBordSum = 0.0
            tBordSum = 0.0
            for index in valueIndices:
                iBordSum += iBoardArray[index]
                tBordSum += tBoardarray[index]
            retVal.append((id, iBordSum, tBordSum))
        
        return retVal
        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
            
        