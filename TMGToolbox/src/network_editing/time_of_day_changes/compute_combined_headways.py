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
Compute Combined Headways

    Authors: Matt Austin

    Latest revision by: mattaustin222
    
    
    Calculates combined headways on groups of lines.
    Takes in pattern matching .csv and outputs headways.
    Typically used to compute combined headways along
    each direction of a line.    
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-01-19 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import csv
from inro.emme.core.exception import ModuleError
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ComputeCombinedHeadways(_m.Tool()):
    
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
    
    ImportFile = _m.Attribute(str)
    ExportFile = _m.Attribute(str)
        
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Aggregation Selection File v%s" %self.version,
                     description="Calculates combined headways along multiple branches \
                         in the same direction of a transit line. Takes in a .csv file  \
                         providing a list of all required lines and outputs combined \
                         headways.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)
                
        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='ImportFile',
                           title="Pattern File",
                           window_type='file',
                           file_filter="*.csv")

        pb.add_select_file(tool_attribute_name='ExportFile',
                           title="Combined Headway Outputs",
                           window_type='save_file',
                           file_filter="*.csv")
        

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
            
            patternList = self._ImportLinePatterns()
            
            with _util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_LINE', default = 999, description = "Pattern Index") as pattIndex:
                self._PatternMatching(patternList, pattIndex.id)
                network = self.BaseScenario.get_network()
                self.TRACKER.completeTask()
                print "Loaded network" 
                self._CalcHeadways(patternList, pattIndex.id, network)
                            

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _ImportLinePatterns(self):
        patternList = []

        with open(self.ImportFile) as reader:
            for line in reader.readlines():
               patternList.append(line[:6])

        return patternList                

    def _PatternMatching(self, patternList, pattId):

        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        def getSpec(value, selection):
            return {
                "result": pattId,
                "expression": str(value),
                "aggregation": None,
                "selections": {
                    "transit_line": selection
                },
                "type": "NETWORK_CALCULATION"
            }

        for i in range(len(patternList)):
            spec = getSpec(i, patternList[i])
            try:
                tool(spec, scenario= self.BaseScenario)
            except ModuleError:
                msg = "Emme runtime error processing line group '%s'." %(patternList[i])
                _m.logbook_write(msg)
                print msg
                raise

            msg = "Loaded group %s" %(patternList[i])
            print msg
            _m.logbook_write(msg)

    def _CalcHeadways(self, patternList, pattId, network):
        totalHeadway = [0] * len(patternList)
        for line in network.transit_lines():
            if line[pattId] < 999:
                _m.logbook_write(int(line[pattId]))
                _m.logbook_write(totalHeadway[int(line[pattId])])
                totalHeadway[int(line[pattId])] += (60 / line.headway) #adds freqs of individual branches
                
                _m.logbook_write(line.headway)
                _m.logbook_write(totalHeadway[int(line[pattId])])
        for i in range(len(totalHeadway)):
            if totalHeadway[i] != 0:
                totalHeadway[i] = 60 / totalHeadway[i] #converts total freq into combined headway
        
        with open(self.ExportFile, 'wb') as csvfile:
            hdwWrite = csv.writer(csvfile, delimiter = ',')
            hdwWrite.writerow(['line', 'comb_hdw'])
            for i in range(len(patternList)):
                hdwWrite.writerow([patternList[i], totalHeadway[i]])               
                
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg