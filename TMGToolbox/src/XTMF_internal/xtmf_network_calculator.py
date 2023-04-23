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
Extract Transit Origin and Destination Vectors

    Authors: Trajce Nikolov

    Latest revision by: Trajce Nikolov
    
    
    Runs the network calculator tool and returns the sum from the report.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-10-06 by Trajce Nikolov
   
'''

import inro.modeller as _m
import inro.emme.matrix as _matrix
import traceback as _traceback
import numpy as np
from multiprocessing import cpu_count

_MODELLER = _m.Modeller() #Instantiate Modeller once.
networkCalculation = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")

class XTMFNetworkCalculator(_m.Tool()):

    #---Parameters---
    xtmf_ScenarioNumber = _m.Attribute(str)
    domain = _m.Attribute(str)
    expression = _m.Attribute(str)
    node_selection = _m.Attribute(str)
    link_selection = _m.Attribute(str)
    transit_line_selection = _m.Attribute(str)
    result = _m.Attribute(str)
    aggregation = _m.Attribute(int)

    def __init__(self):
        self.Scenario = _MODELLER.scenario

    def __call__(self, xtmf_ScenarioNumber, domain, expression, node_selection, link_selection,
                transit_line_selection, result,
                aggregation):

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        self.expression = expression
        self.domain = str(domain)
        if result is not None and result != "None":
            self.result = result
        else:
            self.result = None
        # If we have aggregations we need to specify the 
        # selections manually, if left empty then they will
        # be set to None when building the spec.
        if self.aggregation == 0:
            if self.domain == "0": #link
                self.node_selection = None
                self.link_selection = link_selection
                self.transit_line_selection = None
            elif self.domain == "1": #node
                self.node_selection = node_selection
                self.link_selection = None
                self.transit_line_selection = None
            elif self.domain == "2": #transit line
                self.node_selection = None
                self.link_selection = None
                self.transit_line_selection = transit_line_selection
            elif self.domain == "3": #transit segment
                self.node_selection = None
                self.link_selection = link_selection
                self.transit_line_selection = transit_line_selection


        spec = self.network_calculator_spec()

        report = networkCalculation(spec, self.Scenario)
        if "sum" in report:
            return report["sum"]
        return ""

    def network_calculator_spec(self):
        aggregation = self.get_aggregation()
        spec = {
            "result": self.result,
            "expression": self.expression,
            "aggregation": aggregation,
            "type": "NETWORK_CALCULATION"            
            }
        
        # So we have an issue here where in the original definition for most
        # of the selection functionality defaults everything to all
        # but as soon as we allow aggregation then the standard logic no longer applies.
        # Instead if an aggregation is specified we need to allow the user to manually set
        # the aggregations and ignore ones that are blank.
        def set_if_not_null(dictionary, attribute, value):
            if value:
                dictionary[attribute] = value

        selections = {}
        set_if_not_null(selections, "node", self.node_selection)
        set_if_not_null(selections, "link", self.link_selection)
        set_if_not_null(selections, "transit_line", self.transit_line_selection)
        if self.aggregation == 0 and len(selections) == 0:
            selections["node"] = "all"

        spec["selections"] = selections
        return spec
    
    def get_aggregation(self):
        
        # None = 0,
        # Sum = 1,
        # Average = 2,
        # Min = 3,
        # Max = 4,
        # BitwiseAnd = 5,
        # BitwiseOr = 6,
        
        if self.aggregation == 0:
            return None
        elif self.aggregation == 1:
            return '+'
        elif self.aggregation == 2:
            return 'average'
        elif self.aggregation == 3:
            return ".min."
        elif self.aggregation == 4:
            return ".max."
        elif self.aggregation == 5:
            return "&"
        elif self.aggregation == 6:
            return "|"
        return None

