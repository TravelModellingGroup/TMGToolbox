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
Import TTS Count Station Data

    Authors: David King

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    0.1.1 Created on 2015-03-12 by David King
    1.0.0 Added functionality, to be called from XTMF
    
'''

import inro.modeller as _m
import csv
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_mm = _m.Modeller() #Instantiate Modeller once.
_util = _mm.module('tmg.common.utilities')
_tmgTPB = _mm.module('tmg.common.TMG_tool_page_builder')


class ImportCordonCounts(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1
    Scenario = _m.Attribute(_m.InstanceType)
    CordonTruthTable = _m.Attribute(str)
    
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _mm.scenario #Default is primary scenario
                
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Populate Cordon Count Data v%s" %self.version,
                     description="Loads the cordon count results from a file for the \
                         purpose of validating traffic assignment. An extra attribute \
                         is created that stores the cordon counts on the relevant links.\
                         The difference in assigned volumes and counts can be visualized\
                         using the Link Layer in Desktop. (Bar Value = Volau - @cord).",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario',
                               allow_none=False)        
    
        
        pb.add_header("CORDON DATA FILE")
        
        pb.add_select_file(tool_attribute_name='CordonTruthTable',
                           window_type='file', file_filter='*.csv',
                           title="Cordon Count File",
                           note="Requires three columns:\
                               <ul><li>countpost_id</li>\
                               <li>link id (form of inode-jnode)</li>\
                               <li>cordon_count</li></ul>")
                        
        return pb.render()
    
    def __call__(self, Scen, TruthTable):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        self.Scenario = Scen
        self.CordonTruthTable = TruthTable
        
        try:            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def run(self):
        
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
        
    def _Execute(self):
        
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
                                   
            #Creating a link extra attribute to hold TTS Cordon Counts
            if self.Scenario.extra_attribute('@cord') is not None:                       
                        _m.logbook_write("Deleting Previous Extra Attributes.")
                        self.Scenario.delete_extra_attribute('@cord')
                        print "Cleared previously created Cordon attribute"                    
            
            _m.logbook_write("Created extra attribute for cordon counts.")
            self.Scenario.create_extra_attribute('LINK', '@cord', default_value=0)
            print "Created extra attribute for cordon counts"
            
            net = self.Scenario.get_network()
                        
            with open(self.CordonTruthTable) as input:
                next(input, None)
                for row in input:
            #process individual row
                    column = row.split(',')
                    countpostlinkid = column[1].split("-")
                    value = column[2].strip()
            #apply the values
                    ourLink = net.link(countpostlinkid[0],countpostlinkid[1])
                    if ourLink != None:
                        print value
                        ourLink["@cord"] = int(value)
                    else:                    
                        print "%d - %d" %countpostlinki %value                        
            
            self.Scenario.publish_network(net)
                    
      #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}                
        return atts
                
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
   
            
            