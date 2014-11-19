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
    0.0.1 Created on 2014-08-07 by pkucirek
    
    1.0.0 Published on 20-08-2014
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
EMME_VERSION = _util.getEmmeVersion(float)

##########################################################################################################

class ExtractCongestionMatrix(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 2 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ResultMatrixId = _m.Attribute(str)
    ScalingFactor = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.ScalingFactor = 1.0
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Congestion Matrix v%s" %self.version,
                     description="Extracts a matrix of the cost of congestion resulting from \
                         a congested transit assignment run. The congestion cost must be stored \
                         in transit segment extra attribute '@ccost' which is used by default in \
                         the congested/capacitated assignment tools.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name= 'ResultMatrixId',
                             id= True, filter= ['FULL'],
                             title= "Result Matrix",
                             note= "Select a full matrix to store the congestion costs.")
        
        pb.add_text_box(tool_attribute_name= 'ScalingFactor',
                        size= 10,
                        title= "Scaling Factor")
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        try:
            if not self.ResultMatrixId:
                raise Exception("Result matrix not specified.")
            if self.ScalingFactor == None:
                raise Exception("Scaling factor not specified.")
            
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
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, ResultMatrixId, ScalingFactor):
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        _util.initializeMatrix(ResultMatrixId, name="", description= "Transit congestion impedance")
        self.ResultMatrixId = ResultMatrixId
        self.ScalingFactor = ScalingFactor
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if not self.Scenario.has_transit_results:
                raise Exception("Scenario %s has no transit assignment results." %self.Scenario)
            if self.Scenario.extra_attribute('@ccost') == None:
                raise Exception("Scenario %s has no '@ccost' attribute. Either the attribute has been deleted \
                or a non-congested assignment has been run." %self.Scenario)
            if self.Scenario.extra_attribute('@ccost').type != 'TRANSIT_SEGMENT':
                raise Exception("Scenario %s extra attribute @ccost is not a transit segment attribute." %self.Scenario)
            
            print "Extracting congestion matrix."
            
            stratTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
            matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
            
            spec = self._GetSpec()
            self.TRACKER.runTool(stratTool, spec, scenario= self.Scenario)
            
            if self.ScalingFactor != 1:
                spec = self._GetMatrixCalcSpec()
                self.TRACKER.runTool(matrixCalcTool, spec, scenario= self.Scenario)
            else:
                self.TRACKER.completeTask()
            

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Result Matrix": self.ResultMatrixId,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts

    def _GetSpec(self):
        return {
            "trip_components": {
                "boarding": None,
                "in_vehicle": "@ccost",
                "aux_transit": None,
                "alighting": None
            },
            "sub_path_combination_operator": "+",
            "sub_strategy_combination_operator": "average",
            "selected_demand_and_transit_volumes": {
                "sub_strategies_to_retain": "ALL",
                "selection_threshold": {
                    "lower": -999999,
                    "upper": 999999
                }
            },
            "analyzed_demand": None,
            "constraint": None,
            "results": {
                "strategy_values": self.ResultMatrixId,
                "selected_demand": None,
                "transit_volumes": None,
                "aux_transit_volumes": None,
                "total_boardings": None,
                "total_alightings": None
            },
            "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
        }
    
    def _GetMatrixCalcSpec(self):
        return {
                    "expression": "%s * %s" %(self.ResultMatrixId, self.ScalingFactor),
                    "result": self.ResultMatrixId,
                    "constraint": {
                        "by_value": None,
                        "by_zone": None
                    },
                    "aggregation": {
                        "origins": None,
                        "destinations": None
                    },
                    "type": "MATRIX_CALCULATION"
                }
        