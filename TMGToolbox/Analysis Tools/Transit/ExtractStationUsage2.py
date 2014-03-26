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
[TITLE]

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-20 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

def getSubwayRouteNumber(lineId):
    #Assumes the form "TS01Bb"
    return int(lineId[2:4])

class ExtractStationUsage2(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    modeller_ExportFile = _m.Attribute(str) #Only when running from Modeller do we export a report
    
    '''
    NOTE: Skip Yonge-Sheppard and Sheppard-Yonge stations as they need to be
        separated by a transfer link in order to properly get their station
        boardings and alightings. (This is why they're currently commented out).
    '''
    STATIONS = [(97016,"FINCH",1),
                (97015,"NORTH YORK CENTRE",1),
                #(97014,"SHEPPARD-YONGE",1),
                (97013,"YORK MILLS",1),
                (97012,"LAWRENCE",1),
                (97011,"EGLINTON",1),
                (97010,"DAVISVILLE",1),
                (97009,"ST CLAIR",1),
                (97008,"SUMMERHILL",1),
                (97007,"ROSEDALE",1),
                (97006,"BLOOR-YONGE",1),
                (97005,"WELLESLEY",1),
                (97004,"COLLEGE",1),
                (97003,"DUNDAS",1),
                (97002,"QUEEN",1),
                (97001,"KING",1),
                (97000,"UNION",1),
                (97017,"ST ANDREW",1),
                (97018,"OSGOODE",1),
                (97019,"ST PATRICK",1),
                (97020,"QUEENS PARK",1),
                (97021,"MUSEUM",1),
                (97022,"ST GOERGE",1),
                (97023,"SPADINA",1),
                (97024,"DUPONT",1),
                (97025,"ST CLAIR WEST",1),
                (97026,"EGLINTON WEST",1),
                (97027,"GLENCAIRN",1),
                (97028,"LAWRENCE WEST",1),
                (97029,"YORKDALE",1),
                (97030,"WILSON",1),
                (97031,"DOWNSVIEW",1),
                (97032,"KIPLING",2),
                (97033,"ISLINGTON",2),
                (97034,"ROYAL YORK",2),
                (97035,"OLD MILL",2),
                (97036,"JANE",2),
                (97037,"RUNNYMEDE",2),
                (97038,"HIGH PARK",2),
                (97039,"KEELE",2),
                (97040,"DUNDAS WEST",2),
                (97041,"LANSDOWNE",2),
                (97042,"DUFFERIN",2),
                (97043,"OSSINGTON",2),
                (97044,"CHRISTIE",2),
                (97045,"BATHURST",2),
                (97046,"SPADINA",2),
                (97047,"ST GOERGE",2),
                (97048,"BAY",2),
                (97049,"YONGE-BLOOR",2),
                (97050,"SHERBOURNE",2),
                (97051,"CASTLE FRANK",2),
                (97052,"BROADVIEW",2),
                (97053,"CHESTER",2),
                (97054,"PAPE",2),
                (97055,"DONLANDS",2),
                (97056,"GREENWOOD",2),
                (97057,"COXWELL",2),
                (97058,"WOODBINE",2),
                (97062,"MAIN STREET",2),
                (97063,"VICTORIA PARK",2),
                (97065,"WARDEN",2),
                (97066,"KENNEDY",2),
                (97067,"KENNEDY",3),
                (97068,"LAWRENCE EAST",3),
                (97069,"ELLESMERE",3),
                (97070,"MIDLAND",3),
                (97071,"SCARBOROUGH TOWN CENTRE",3),
                (97072,"MCCOWAN",3),
                #(97014,"YONGE-SHEPPARD",4),
                (97090,"BAYVIEW",4),
                (97091,"BESSARION",4),
                (97092,"LESLIE",4),
                (97093,"DON MILLS",4)]
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Subway Station Usage v%s" %self.version,
                     description="Extracts boardings and alightings for TTC subway station \
                         based on auxiliary transit volumes on station-node access and \
                         egress links.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name= 'modeller_ExportFile',
                           window_type= 'save_file', file_filter= "*.csv",
                           title= "Export File")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            results = self._Execute()
            self._WriteReport(results)
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumber):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            return self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if not self.Scenario.has_transit_results:
                raise Exception("Scenario %s has no transit assignment results!" %self.Scenario)
            
            self.TRACKER.startProcess(len(self.STATIONS) + 2)
            network = self.Scenario.get_network()
            self.TRACKER.completeSubtask()
            self.TRACKER.completeSubtask()
            
            results = {}
            for nodeNumber, stationName, lineNumber in self.STATIONS:
                boardings = 0.0
                alightings = 0.0
                
                node = network.node(nodeNumber)
                if node == None:
                    raise Exception("Could not find node #%s for %s station" %(nodeNumber, stationName))
                
                for link in node.incoming_links():
                    boardings += link.aux_transit_volume
                for link in node.outgoing_links():
                    alightings += link.aux_transit_volume
                
                results[nodeNumber] = (boardings, alightings)
                
                self.TRACKER.completeSubtask()
            return results            

    ##########################################################################################################
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _WriteReport(self, results):
        with open(self.modeller_ExportFile, 'w') as writer:
            writer.write("Station,Line,Node,Boardings,Alightings")
            for nodeNumber, stationName, lineNumber in self.STATIONS:
                boardings, alightings = results[nodeNumber]
                cells = [stationName, lineNumber, nodeNumber, boardings, alightings]
                writer.write("\n" + ",".join([str(c) for c in cells]))

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        