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
Extract Transit Boardings by Group 

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-18 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class ExtractTransitBoardingsByGroup(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 14 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ExportFile = _m.Attribute(str) 
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Boardings by Line Group v%s" %self.version,
                     description="Extracts transit line boardings by line group, by mode and by operator, and saves the results" +
                                    " in a CSV file. The following line groups are hard-coded: <ul>" +
                                    "<li> TTC Subways " +
                                    "<li> TTC Streetcars " +
                                    "<li> TTC Buses " +
                                    "<li> GO Trains " +
                                    "<li> GO Buses " +
                                    "<li> Durham Buses " +
                                    "<li> YRT Buses (incl. VIVA) " +
                                    "<li> VIVA Buses only " +
                                    "<li> Mississauag Buses " +
                                    "<li> Brampton Buses (incl. ZUM) " +
                                    "<li> ZUM Buses only " +
                                    "<li> Halton Buses " +
                                    "<li> Hamilton Buses  </ul>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           title="Export File",
                           file_filter="*.csv")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            if self.ExportFile == None: raise NullPointerException("Export file not specified")
            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumber, ExportFile):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.ExportFile = ExportFile
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if not self.Scenario.has_transit_results:
                raise Exception("Scenario %s has no transit results to export" %self.Scenario)
            
            self.ExportFile = path.splitext(self.ExportFile)[0] + ".csv"
            
            network = self.Scenario.get_network()
            network.create_attribute('TRANSIT_LINE', 'boardings')
            for line in network.transit_lines():
                line.boardings = sum([seg.transit_boardings for seg in line.segments()])
            self.TRACKER.completeTask()
            
            def sumRouteGroup(function):
                return sum([line.boardings for line in network.transit_lines() if function(line)])
            
            with open(self.ExportFile, 'w') as writer:
                writer.write("LineGroup,Boardings")
                
                subwayCount = sumRouteGroup(lambda line: line.mode.id == 'm')
                writer.write("\nSubways,%s" %subwayCount)
                self.TRACKER.completeTask()
                
                tramCount = sumRouteGroup(lambda line: line.mode.id == 's')
                writer.write("\nStreetcars,%s" %tramCount)
                self.TRACKER.completeTask()
                
                ttcBusCount = sumRouteGroup(lambda line: line.mode.id == 'b' and line.id.startswith('T'))
                writer.write("\nTTC Buses,%s" %ttcBusCount)
                self.TRACKER.completeTask()
                
                goTrainCount = sumRouteGroup(lambda line: line.mode.id == 'r')
                writer.write("\nGO Train,%s" %goTrainCount)
                self.TRACKER.completeTask()
                
                goBusCount = sumRouteGroup(lambda line: line.mode.id == 'g')
                writer.write("\nGO Bus,%s" %goBusCount)
                self.TRACKER.completeTask()
                
                vivaCount = sumRouteGroup(lambda line: line.id.startswith('YV'))
                writer.write("\nVIVA,%s" %vivaCount)
                self.TRACKER.completeTask()
                
                yrtCount = sumRouteGroup(lambda line: line.id.startswith('Y'))
                writer.write("\nYRT,%s" %yrtCount)
                self.TRACKER.completeTask()
                
                bramptonCount = sumRouteGroup(lambda line: line.id.startswith('B'))
                writer.write("\nBrampton Transit,%s" %bramptonCount)
                self.TRACKER.completeTask()
                
                zumCount = sumRouteGroup(lambda line: 'Zum' in line.description)
                writer.write("\nBrampton ZUM,%s" %zumCount)
                self.TRACKER.completeTask()
                
                mississaugaCount = sumRouteGroup(lambda line: line.id.startswith('M'))
                writer.write("\nMiWay,%s" %mississaugaCount)
                self.TRACKER.completeTask()
                
                durhamCount = sumRouteGroup(lambda line: line.id.startswith('D'))
                writer.write("\nDRT,%s" %durhamCount)
                self.TRACKER.completeTask()
                
                haltonCount = sumRouteGroup(lambda line: line.id.startswith('H'))
                writer.write("\nHalton,%s" %haltonCount)
                self.TRACKER.completeTask()
                
                hsrCount = sumRouteGroup(lambda line: line.id.startswith('W'))
                writer.write("\nHSR,%s" %hsrCount)
                self.TRACKER.completeTask()
                
    ##########################################################################################################    
    
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
        