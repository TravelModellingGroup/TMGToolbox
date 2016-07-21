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
from contextlib import contextmanager
from contextlib import nested
from multiprocessing import cpu_count

_MODELLER = _m.Modeller() #Instantiate Modeller once.
networkCalculation = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")

class XTMFNetworkCalculator(_m.Tool()):

    #---Parameters---
    Scenario = _m.Attribute(_m.InstanceType)
    xtmf_ScenarioNumber = _m.Attribute(str)
    domain = _m.Attribute(str)
    expression = _m.Attribute(str)
    node_selection = _m.Attribute(str)
    link_selection = _m.Attribute(str)
    transit_line_selection = _m.Attribute(str)
    result = _m.Attribute(str)

    def __init__(self):
        self.Scenario = _MODELLER.scenario

    def __call__(self, xtmf_ScenarioNumber, domain, expression, node_selection, link_selection, transit_line_selection, result):

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        self.expression = expression
        self.domain = domain
        if result != None and result != "None":
            self.result = result
        else:
            self.result = None
        
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
        if report.has_key("sum"):
            return report["sum"]
        return ""

    def network_calculator_spec(self):
        spec = {
            "result": self.result,
            "expression": self.expression,
            "aggregation": None,
            "selections": {
                "node": self.node_selection,
                "link": self.link_selection,
                "transit_line": self.transit_line_selection
                },
            "type": "NETWORK_CALCULATION"            
            }

        return spec


