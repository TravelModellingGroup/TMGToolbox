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
Volume per Operator

    Authors: tnikolov

    Latest revision by: tnikolov
    
    
    Tool used to calculate the amount of riders on each operator within the system.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-05-04 by tnikolov
'''

import inro.modeller as _m

import traceback as _traceback
from contextlib import contextmanager
import tempfile as _tf
import shutil as _shutil
import csv
from re import split as _regex_split

_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculator = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
traversalAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.traversal_analysis')
networkResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
matrixCalculator = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
matrixAggregation = _MODELLER.tool('inro.emme.matrix_calculation.matrix_aggregation')
#matrixExportTool = _MODELLER.tool('inro.emme.data.matrix.export_matrices')
matrixExport = _MODELLER.tool('inro.emme.data.matrix.export_matrix_to_csv')
pathAnalysis = _MODELLER.tool('inro.emme.transit_assignment.extended.path_based_analysis')
EMME_VERSION = _util.getEmmeVersion(float)

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

@contextmanager
def blankContextManager(var= None):
    try:
        yield var
    finally:
        pass

@contextmanager
def getTemporaryFolder():
    folder = _tf.mkdtemp()
    try:
        yield folder
    finally:
        _shutil.rmtree(folder)


class RevenueCalculation(_m.Tool()):
    
    #---PARAMETERS
    xtmf_ScenarioNumbers = _m.Attribute(str)
    FilterString = _m.Attribute(str)        
    filePath = _m.Attribute(str)
    
    Scenarios = _m.Attribute(_m.ListType)

    #results = {"test": 1.0};

    #Emme input parameters
    tool_run_msg = ""
    scenario = _m.Attribute(_m.InstanceType) #_m.Attribute(str)
    LineFilter = _m.Attribute(str)
    ReportFile = _m.Attribute(str)
    version = '1.0.0'
            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   

        #---Set the defaults of parameters used by Modeller
        lines = ["GO Train: mode=r",
                 "GO Bus: mode=g",
                 "Subway: mode=m",
                 "Streetcar: mode=s",
                 "TTC Bus: line=T_____ and mode=bp",
                 "YRT: line=Y_____",
                 "VIVA: line=YV____",
                 "Brampton: line=B_____",
                 "MiWay: line=M_____",
                 "Durham: line=D_____",
                 "Halton: line=H_____",
                 "Hamilton: line=W_____"]

        self.filtersToCompute = "\n".join(lines)
        self.results = {}

    def page(self):
        """
        function to build and add the inputs for the Emme Modelle Gui
        """
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Revenue Calculation",
                     description="Revenue Calculation Tool",
                     branding_text="- TMG Toolbox")

        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        pb.add_text_box(tool_attribute_name='LineFilter',
                        size=50, title="Filter of lines use : eg Subway:mode=s ",
                        note="")
        pb.add_select_file(tool_attribute_name='ReportFile', title="Report File:", file_filter="*.csv",
                           window_type='save_file')
            
        return pb.render()

    def _GetAtts(self):
        atts = {
                "scenario" : str(self.scenario.id),
                "LineFilter": str(self.LineFilter),
                "Report File": self.ReportFile,
                "Version": self.version,
                "self": self.__MODELLER_NAMESPACE__
                }
        return atts
        
    def run(self):
        # run from Emme
        self.tool_run_msg = ""
        with _m.logbook_trace(
                name="{classname} v{version}".format(classname=self.__class__.__name__, version=self.version),
                attributes=self._GetAtts()):
            lineFilters = self.LineFilter
            sc = _MODELLER.emmebank.scenario(str(self.scenario.id))
            self.Scenarios = []
            self.Scenarios.append(sc)
            
            self.filtersToCompute = lineFilters
            self._Execute();

            with _util.open_csv_writer(self.ReportFile) as writer:
                writer.writerow(["Scenario", "Line Filter", "Revenue"])
                for scenario in sorted(self.results):
                    for lineFilter in sorted(self.results[scenario]):
                        writer.writerow([scenario, lineFilter, self.results[scenario][lineFilter]])
        print ('function successfully ran')
        
    def __call__(self, xtmf_ScenarioNumbers, FilterString, filePath):
        self.tool_run_msg = ""
        print("Starting Revenue Calculations")

        self.Scenarios = []
        for number in xtmf_ScenarioNumbers.split(','):
            sc = _MODELLER.emmebank.scenario(number)
            if (sc is None):
                raise Exception("Scenarios %s was not found!" %number)
            self.Scenarios.append(sc)

        self.filtersToCompute = FilterString
       
        self._Execute()

        with _util.open_csv_writer(filePath) as writer:
            writer.writerow(["Scenario", "Line Filter", "Revenue"])
            for scenario in sorted(self.results):
                for lineFilter in sorted(self.results[scenario]):
                    writer.writerow([scenario, lineFilter, self.results[scenario][lineFilter]])
        
        print("Finished Revenue calculations")

    def _Execute(self):

        if len(self.Scenarios) == 0: raise Exception("No scenarios selected.")      

        parsed_filter_list = self._ParseFilterString(self.filtersToCompute)
        for scenario in self.Scenarios:
            self.Scenario = _MODELLER.emmebank.scenario(scenario.id)
            self.results[scenario.id] = {}
            
            for filter in parsed_filter_list:
                spec = {
                    "expression": "voltr*@sfare",                    
                    "selections": {
                        "link": "all",
                        "transit_line": filter[1]
                        },
                    "type": "NETWORK_CALCULATION"
                }
                report = networkCalculator(spec, scenario=self.Scenario)                               

                self.results[scenario.id][filter[1]] =  report['sum']                     
      
    def _ParseFilterString(self, filterString):
        filterList = []
        components = _regex_split('\n|,', filterString) #Supports newline and/or commas
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 2:
                msg = "Error parsing penalty and filter string: Separate label and filter with colons label:filter"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            strippedParts = [item.strip() for item in parts]
            filterList.append(strippedParts)

        return filterList

    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
     