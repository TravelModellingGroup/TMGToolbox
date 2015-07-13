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
Export Transit Line Boardings

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-06-23 by mattaustin222
    
'''

import inro.modeller as _m

from html import HTML
import csv
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
EMME_VERSION = _util.getEmmeVersion(tuple) 

##########################################################################################################

class ExtractStationBoardingsAlightings(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','

    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    StationNodeFile = _m.Attribute(str)
    ReportFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):

        if EMME_VERSION < (4,1,5):
            raise ValueError("Tool not compatible. Please upgrade to version 4.1.5+")

        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Station Boardings and Alightings v%s" %self.version,
                     description="Extracts total boardings and alightings for a list \
                         of nodes defined in a CSV file.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='ReportFile',
                           title="Report file",
                           file_filter= "*.csv",
                           window_type='save_file')

        pb.add_select_file(tool_attribute_name='StationNodeFile',
                           title="Station Node file:",
                           window_type='file',
                           file_filter= "*.csv",
                           note="Station node file contains the following two columns: \
                            <ul><li>node_id</li>\
                            <li>label</li></ul> \
                            where label is whatever you wish to label the node in the output.")        
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
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    

    ##########################################################################################################

    def __call__(self, xtmf_ScenarioNumber, ReportFile, StationNodeFile):
        
        if EMME_VERSION < (4,1,5):
            raise ValueError("Tool not compatible. Please upgrade to version 4.1.5+")

        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        if ReportFile:
            self.ReportFile = ReportFile
        else: 
            raise Exception("Report file location not indicated!")
        if StationNodeFile:
            self.StationNodeFile = StationNodeFile
        else:
            raise Exception("No station node file selected")
        
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
                raise Exception("Scenario %s has no transit results" %self.Scenario)

            network = self.Scenario.get_network()
            stations, badNodes = self._LoadStationNodeFile(network)

            if len(badNodes) > 0:
                print "%s node IDs were not found in the network and were skipped." %len(badIdSet)
                pb = _m.PageBuilder("NodeIDs not in network")
                
                pb.add_text_element("<b>The following node IDs were not found in the network:</b>")
                
                for id in badNodes:
                    pb.add_text_element(id)
                
                _m.logbook_write("Some IDs were not found in the network. Click for details.",
                                 value=pb.render())

            nodeValues = self._CalcBoardingAlighting(network,stations)
            self._OutputResults(nodeValues)


    ##########################################################################################################

    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts

    def _LoadStationNodeFile(self, network):
        badIds = set()
        nodeDict = {}
        with open(self.StationNodeFile) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)

            nodeCol = cells.index('node_id')
            labelCol = cells.index('label')
            
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                id = cells[nodeCol]
                label = cells[labelCol]
                node = network.node(id)
                
                if node == None:
                    badIds.add(id)
                    continue #Skip and report
                else:
                    nodeDict[node.id] = [node.id]
                    nodeDict[node.id].append(label)
            
        return nodeDict, badIds

    def _CalcBoardingAlighting(self, network, nodeIds):
        for id in nodeIds:
            node = network.node(id)
            totalBoard = 0
            totalAlight = 0
            for segment in node.outgoing_segments(include_hidden=True):
                board = segment.transit_boardings
                totalBoard += board
                voltr = segment.transit_volume
                index = segment.number - 1
                voltrLast = segment.line.segment(index).transit_volume
                totalAlight += (voltrLast + board - voltr)
            nodeIds[id].append(round(totalBoard))
            nodeIds[id].append(round(totalBoard - node.initial_boardings))
            nodeIds[id].append(round(totalAlight - node.final_alightings))
            nodeIds[id].append(round(totalAlight))
            
        return nodeIds

    def _OutputResults(self, valueDict):
        with open(self.ReportFile, 'wb') as csvfile:
            nodeWrite = csv.writer(csvfile, delimiter = ',')
            nodeWrite.writerow(['node_id', 'label', 'boardings', 'transfer_boardings', 'transfer_alightings', 'alightings'])
            for key, values in sorted(valueDict.iteritems()):
                nodeWrite.writerow(values)

