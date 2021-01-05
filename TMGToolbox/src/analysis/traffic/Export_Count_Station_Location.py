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
Export Count Station Link Correspondence File

    Authors: David King

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    0.1.1 Created on 2015-03-13 by David King
    
    
'''

import inro.modeller as _m
import csv
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_mm = _m.Modeller()
net =_mm.scenario.get_network()
_util = _mm.module('tmg.common.utilities')
_tmgTPB = _mm.module('tmg.common.TMG_tool_page_builder')

class ExportCountStationLocation(_m.Tool()):
    
    version = '0.1.1'
    tool_run_msg = ""
    number_of_tasks = 1
    Scenario = _m.Attribute(_m.InstanceType)
    CordonExportFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _mm.scenario #Default is primary scenario
                
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Count Station-Link Correspondence File v%s" %self.version,
                     description="Exports a link and countpost correspondence file.\
                         Contained witin, is the link on which each countpost is found.\
                         Assumes that count stations are defined by '@stn1'.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)            
 
        
        pb.add_header("EXPORT CORDON DATA FILE")
        
        pb.add_select_file(tool_attribute_name='CordonExportFile',
                           window_type='save_file', file_filter='*.csv',
                           title="Cordon Count File",
                           note="Select Export Location:\
                               <ul><li>countpost_id</li>\
                               <li>link id (inode-jnode)</li>\
                               </ul>")
                        
        return pb.render()
    
    def __call__(self, Scen, TruthTable):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        self.Scenario = Scen
        self.CordonTruthTable = TruthTable
        
        try:            
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def run(self):
        
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
        
    def _Execute(self):
        
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
               
            lines =[]
            for link in net.links():
                if int(link['@stn1']) > 0:
                    lines.append((link['@stn1'],link.id))
                            
            
            with open(self.CordonExportFile, 'w') as writer:
                writer.write("Countpost ID ,Link (i-node j-node)")
                for line in lines:
                    line = [str(c) for c in line]
                    writer.write("\n" + ','.join(line))
    
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