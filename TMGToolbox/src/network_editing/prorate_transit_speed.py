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
Pro-rate Segment Speeds for Select Lines

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-30 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ProrateSegmentSpeedsByLine(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType)
    LineFilterExpression = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Prorate Transit Line Speed v%s" %self.version,
                     description="For a given subgroup of transit lines, this tool \
                         prorates the line speed over each segment to get the segment \
                         speed (stored in US1). Each segment's speed is based on the \
                         link's freeflow speed (UL2).",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='LineFilterExpression',
                        title="Line Filter Expression",
                        size=100, multi_line=True)
        
        return pb.render()

    ##########################################################################################################
        
    def __call__(self, scen, filter):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        self.Scenario = _MODELLER.emmebank.scenario(scen)
        self.LineFilterExpression = filter

        try:
           
            linesModified = self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done. %s lines modified" %linesModified)    

    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            linesModified = self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done. %s lines modified" %linesModified)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            try:
                networkCalculationTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
            except Exception, e:
                networkCalculationTool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
            
            with self._lineAttributeMANAGER() as flagAttributeId:
                with _m.logbook_trace("Flagging slected lines"):
                    self.TRACKER.runTool(networkCalculationTool, 
                                         self._GetNetCalcSpec(flagAttributeId), self.Scenario)
                
                network = self.Scenario.get_network()
                
                flaggedLines = [line for line in network.transit_lines() if line[flagAttributeId] == 1]
                self.TRACKER.startProcess(len(flaggedLines))
                for line in flaggedLines:
                    self._ProcessLine(line)
                    self.TRACKER.completeSubtask()
                self.TRACKER.completeTask()
                    
                self.Scenario.publish_network(network)
            
            return len(flaggedLines)

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _lineAttributeMANAGER(self):
        # Code here is executed upon entry {
        
        self.Scenario.create_extra_attribute('TRANSIT_LINE', '@tlf1')
        _m.logbook_write("Created temporary attribute @tlf1")
        
        # }
        try:
            yield '@tlf1'
        finally:
            self.Scenario.delete_extra_attribute('@tlf1')
            _m.logbook_write("Deleted temporary attribute @tlf1")
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version,
                "Line Selector Expression": self.LineFilterExpression,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _GetNetCalcSpec(self, flagAttributeId):
        return {
                "result": flagAttributeId,
                "expression": "1",
                "aggregation": None,
                "selections": {
                    "transit_line": self.LineFilterExpression
                },
                "type": "NETWORK_CALCULATION"
                }
    
    def _ProcessLine(self, line):
        lineLength = sum([seg.link.length for seg in line.segments()]) #In km
                    
        scheduledCycleTime = lineLength / line.speed * 60.0 #In minutes
        # All speeds are assumed to be in km/hr
        
        freeflowTime = 0
        for segment in line.segments():
            speed = segment.link.data2
            if speed == 0:
                speed = 50 #Assume nominal speed of 50 km/hr if it's otherwise undefined
            
            freeflowTime += segment.link.length / speed * 60.0
        
        factor = freeflowTime / scheduledCycleTime
        
        for segment in line.segments():
            speed = segment.link.data2
            if speed == 0:
                speed = 50.0 #Assume nominal speed of 50 km/hr if it's otherwise undefined
            
            segment.data1 = speed * factor
                        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        