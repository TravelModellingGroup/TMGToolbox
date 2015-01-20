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
Create Aggregation Selection File

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-01-19 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class CreateAggregationSelectionFile(_m.Tool()):
    
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
    
    AggTypeSelectionFile = _m.Attribute(str)

    TorontoSurfaceAgg = _m.Attribute(str)
    TorontoSubwayAgg = _m.Attribute(str)
    MississaugaAgg = _m.Attribute(str)
    DurhamAgg = _m.Attribute(str)
    YorkAgg = _m.Attribute(str)
    BramptonAgg = _m.Attribute(str)
    OakvilleAgg = _m.Attribute(str)
    BurlingtonAgg = _m.Attribute(str)
    MiltonAgg = _m.Attribute(str)
    HSRAgg = _m.Attribute(str)
    GORailAgg = _m.Attribute(str)
    GOBusAgg = _m.Attribute(str)
        
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Aggregation Selection File v%s" %self.version,
                     description="Creates an aggregation selection file that can be \
                         used with the Create Transit Time Period Tool. Every line in \
                         the network requires a aggregation type and this tool automates \
                         that process.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)
                
        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           title="File name",
                           window_type='save_file',
                           file_filter="*.csv")
        
        pb.add_header("TOOL INPUTS")
        
        #Add selections here for :
        #TTC Bus
        #TTC Streetcar
        #TTC Subway
        #Mississauga
        #YRT/VIVA
        #etc.

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
            self.TRACKER.completeTask()
            print "Loaded network"
            
            #

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 