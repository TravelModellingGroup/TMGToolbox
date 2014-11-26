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
Return Line Group Boardings

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Returns a 'serialized' (e.g. string repr) of transit line boardings to XTMF.
    See XTMF for documentation.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-05 by pkucirek
    
    0.1.0 Upgraded to work with get_attribute_values (partial read)
    
    0.2.0 Modified to return a comma-separated string (instead of a dictionary)
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import shutil as _shutil
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class LineGroup():
    __slots__ = ['index', 'filter', 'name']
    
    def __init__(self, index, filter, name):
        self.index = index
        self.filter = filter
        self.name = name
    
    def select(self, scenario):
        spec= {
                    "result": "@ltype",
                    "expression": str(self.index),
                    "aggregation": None,
                    "selections": {
                        "transit_line": self.filter
                    },
                    "type": "NETWORK_CALCULATION"
                }
        
        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        tool(spec, scenario= scenario)

class ReturnBoardings(_m.Tool()):
    
    version = '0.2.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters necessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get initialized during construction (__init__)
    
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

        
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Return Boardings",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
            
    def __call__(self, xtmf_ScenarioNumber):
        
        _m.logbook_write("Extracting boarding results")
        
        #---1 Set up scenario
        scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        if not scenario.has_transit_results:
            raise Exception("Scenario %s does not have transit assignment results" %xtmf_ScenarioNumber)              
        
        try:
            return self._Execute(scenario)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    def _Execute(self, scenario):
        print "Extracting results from Emme"
                
        with self._lineTypeAttributeMANAGER(scenario):
            self._CalcLineType(scenario)
            lineTypes = self._GetLineTypes(scenario)
            self.TRACKER.completeTask()
        
        lineBoardings = self._GetLineResults(scenario)
        self.TRACKER.completeTask()
        
        results = {}
        self.TRACKER.startProcess(len(lineBoardings))
        for lineId, lineCount in lineBoardings.iteritems():
            type = lineTypes[lineId]
            typeName = self.LINE_GROUP_MAP[type].name
            
            if not typeName in results:
                results[typeName] = lineCount
            else:
                results[typeName] += lineCount
            self.TRACKER.completeSubtask()
        
        keys = [group.name for group in self.LINE_GROUPS]
        keys.sort()
        retval = [str(results[key]) for key in keys]
        return ",".join(retval)
                
    

    
    ##########################################################################################################
    
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _lineTypeAttributeMANAGER(self, scenario):
        #Code here is executed upon entry
        
        typeAttribute = scenario.create_extra_attribute('TRANSIT_LINE', '@ltype')
        
        try:
            yield
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            scenario.delete_extra_attribute('@ltype')
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------
        
    def _CalcLineType(self, scenario):
        for group in self.LINE_GROUPS:
            group.select(scenario)
    
    def _GetLineResults(self, scenario):
        
        results = _util.fastLoadSummedSegmentAttributes(scenario, ['transit_boardings'])
        retVal = {}
        for lineId, attributes in results.iteritems():
            id = str(lineId)
            retVal[id] = attributes['transit_boardings']
        
        return retVal
    
    def _GetLineTypes(self, scenario):
        #Performs a partial read of the network. The data structure is undocumented
        # so this method is subject to change in future versions of Emme.
        
        q = scenario.get_attribute_values('TRANSIT_LINE', ['@ltype'])
        indices = q[0]
        values = q[1]
        
        retval = {}
        for id, index in indices.iteritems():
            id = str(id) #Normally stored in unicode.
            retval[id] = int(values[index])
        return retval
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        