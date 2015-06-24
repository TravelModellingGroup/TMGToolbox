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
Export Specific Link Volumes

    Authors: tnikolov

    Latest revision by: mattaustin222
    
    
    Takes in a series of link filters and exports the
    associated volumes to file.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-06-03 by tnikolov
    0.1.0 Added the option to export total transit volumes on the link
    
'''

import inro.modeller as _m

from html import HTML
from re import split as _regex_split
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os.path import exists
from json import loads as _parsedict
from os.path import dirname
import tempfile as _tf
import shutil as _shutil
import csv

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculator = _MODELLER.tool('inro.emme.network_calculation.network_calculator')

##########################################################################################################

class LinkSpecificVolumes(_m.Tool()):

     #---PARAMETERS
    xtmf_ScenarioNumbers = _m.Attribute(str)
    FilterString = _m.Attribute(str)
    DemandMatrixId = _m.Attribute(str)                
    VolumeMatrix = _m.Attribute(str)
    filePath = _m.Attribute(str)

    TransitFlag = _m.Attribute(bool)

    Scenarios = _m.Attribute(_m.ListType)

    #results = {"test": 1.0};
            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   
        self.results = {};
        self.TransitFlag = True

    def run(self):
        self.tool_run_msg = ""        
        
    def __call__(self, xtmf_ScenarioNumbers, FilterString, filePath, TransitFlag=True):
        self.tool_run_msg = ""
        print "Starting Link volume calculations"

        self.Scenarios = []
        for number in xtmf_ScenarioNumbers.split(','):
            sc = _MODELLER.emmebank.scenario(number)
            if (sc == None):
                raise Exception("Scenarios %s was not found!" %number)
            self.Scenarios.append(sc)

        self.filtersToCompute = FilterString
        self.TransitFlag = TransitFlag
       
        self._Execute()

        with open(filePath, 'wb') as csvfile:               
            writer = csv.writer(csvfile, delimiter=',')
            if self.TransitFlag:
                writer.writerow(["Scenario", "Link Filter", "Auto Volume", "Transit Volume"])
            else:
                writer.writerow(["Scenario", "Link Filter", "Volume"])
            for scenario in sorted(self.results):
                for linkFilter in sorted(self.results[scenario]):
                    output = [scenario, linkFilter]
                    output.extend(self.results[scenario][linkFilter])
                    writer.writerow(output)

        print "Finished Link volume calculations"

    def _Execute(self):

        with _m.logbook_trace(name="{classname}".format(classname=(self.__class__.__name__)),
                                     attributes=self._GetAtts()):

            if len(self.Scenarios) == 0: raise Exception("No scenarios selected.")      

            parsed_filter_list = self._ParseFilterString(self.filtersToCompute)

            for scenario in self.Scenarios:
                self.Scenario = _MODELLER.emmebank.scenario(scenario.id)
                self.results[scenario.id] = {}
            
                for filter in parsed_filter_list:                                
                
                    spec1 = {
                        "expression": "volau",                    
                        "selections": {
                            "link": filter[1]
                            },
                        "type": "NETWORK_CALCULATION"
                    }
                    report1 = networkCalculator(spec1, scenario=self.Scenario)

                    if self.TransitFlag:
                        spec2 = {
                            "expression": "voltr",                    
                            "selections": {
                                "link": filter[1],
                                "transit_line": "all"
                                },
                            "type": "NETWORK_CALCULATION"
                        }

                        report2 = networkCalculator(spec2, scenario=self.Scenario)
                        self.results[scenario.id][filter[0]] = [report1['sum'], report2['sum']]

                    else:
                        self.results[scenario.id][filter[0]] = [report1['sum']]

    def _ParseFilterString(self, filterString):
        filterList = []
        components = _regex_split('\n|;', filterString) #Supports newline and/or semi-colons
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 2:
                print component;
                msg = "Error parsing label and filter string: Separate label and filter with colons label:filter"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            strippedParts = [item.strip() for item in parts]
            filterList.append(strippedParts)

        return filterList

    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
