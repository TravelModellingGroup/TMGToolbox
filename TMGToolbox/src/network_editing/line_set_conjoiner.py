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
Line Set Conjoiner

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    This tool takes in a set of transit lines that are to be
    combined into one single, "looped" line that starts and ends
    at the same node. EMME no longer restricts such loops, so 
    for the purpose of cleaning networks, this is a useful tool.
    
    It will allow for the combination of trips within a Combined
    Service Table, as well, so that the Create Transit Time
    Period tool will still be viable after a cleaning overhaul of 
    a base network.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-01-29 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class LineSetConjoiner(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    BaseScenario = _m.Attribute(_m.InstanceType)
    
    TransitServiceTableFile = _m.Attribute(str)
    NewServiceTableFile = _m.Attribute(str)
    LineSetFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Line Set Conjoiner v%s" %self.version,
                     description="Takes a set of transit lines and combines them \
                         into single, looped lines. Also adjusts the Combined Service\
                         Table accordingly so that accurate headways can be generated \
                         later using the Create Transit Time Period tool.\
                         Each line in the input file must be an sequential list of \
                         transit line IDs.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)

        pb.add_header("DATA FILES")
        
        #pb.add_select_file(tool_attribute_name='TransitServiceTableFile',
        #                   window_type='file', file_filter='*.csv',
        #                   title="Transit service table",
        #                   note="Requires three columns:\
        #                       <ul><li>emme_id</li>\
        #                       <li>trip_depart</li>\
        #                       <li>trip_arrive</li></ul>")

        pb.add_select_file(tool_attribute_name='LineSetFile',
                           window_type='file', file_filter='*.csv',
                           title="Line sets",
                           note="Input line IDs must be ordered")

        #pb.add_select_file(tool_attribute_name='NewServiceTableFile',
        #                   window_type='save_file', file_filter='*.csv',
        #                   title="New output service table")

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
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            network = self.BaseScenario.get_network()
            print "Loaded network"

            lineIds = self._ReadSetFile()
            print "Loaded lines"

            self._ConcatenateLines(network, lineIds)
            print "Lines concatenated"
            
            print "Publishing network"
            self.BaseScenario.publish_network(network)
            self.TRACKER.completeTask()

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _ReadSetFile(self):
        with open(self.LineSetFile) as reader:
            lines = []
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                lines.append(cells)

        return lines

    def _ConcatenateLines(self, network, lineIds):
        #add in a logbook trace folder here
        for lineSet in lineIds:
            try:
                _util.lineConcatenator(network, lineSet)
            except Exception:
                print 'This line set is not valid', lineSet

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg