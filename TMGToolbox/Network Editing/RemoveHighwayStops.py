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
Remove Highway Stops

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.1.0 [Description]
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_util = _m.Modeller().module('TMG2.Common.Utilities')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')
_MODELLER = _m.Modeller() #Instantiate Modeller once.

##########################################################################################################

class RemoveHighwayStops(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    HighwayLinkSelector = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.HighwayLinkSelector = "vdf=11 or vdf=12 or vdf=14 or vdf=16"
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Remove Highway Stops v%s" %self.version,
                     description="Disables transit stops on highways for all transit line segments.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='HighwayLinkSelector',
                        size=100,
                        title="Link selector expression",
                        multi_line=True)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            self.TRACKER.reset()
            
            with self._linkFlagAttributeMANAGER() as attId:
                
                self._FlagHighwayLinks(attId)
                
                network = self.Scenario.get_network()
                self.TRACKER.completeTask()
                
                with _m.logbook_trace("Processing transit segments"):
                    self._FixTransitSegments(network, attId)
                
                self.Scenario.publish_network(network)
                self.TRACKER.completeTask()
                

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _linkFlagAttributeMANAGER(self):
        att = self.Scenario.create_extra_attribute('LINK',"@hflag")
        _m.logbook_write("Created temporary link attribute '@hflag'")
        try:
            yield att.id
        finally:
            self.Scenario.delete_extra_attribute(att.id)
            _m.logbook_write("Deleted temporary link attribute '@hflag'")
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Link filter": self.HighwayLinkSelector,
                "Version": self.version,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _FlagHighwayLinks(self, attId):
        try:
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        except Exception, e:
            tool = _MODELLER.tool('inro.emme.standard.network_calculation.network_calculator')
        
        spec = {
                "result": attId,
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "link": self.HighwayLinkSelector
                               },
                "type": "NETWORK_CALCULATION"
                }
        self.TRACKER.runTool(tool, spec, scenario=self.Scenario)
    
    def _FixTransitSegments(self, network, attId):
        self.TRACKER.startProcess(network.element_totals['transit_segments'])
        fixedCount = 0
        
        for segment in network.transit_segments():
            link = segment.link
            if link == None:
                continue #segment is hidden
            
            if link[attId] == 0:
                continue # Skip non-highway links
            
            if segment.allow_alightings or segment.allow_boardings:
                fixedCount += 1
                                    
            segment.allow_alightings = False
            segment.allow_boardings = False
            
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        _m.logbook_write("Fixed %s transit segments which were permitting boarding or alighting on highways." %fixedCount)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    