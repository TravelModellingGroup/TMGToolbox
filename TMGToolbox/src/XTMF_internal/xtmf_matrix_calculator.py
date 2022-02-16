#---LICENSE----------------------
'''
    Copyright 2019 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Quick plug in from XTMF to the Emme Matrix Calculator. very basic, will add functionality later.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2019-01-30 by byusuf
   
'''

import inro.modeller as _m

_MODELLER = _m.Modeller() #Instantiate Modeller once.
matrixCalculator = _m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")

class XTMFMatrixCalculator(_m.Tool()):

    #---Parameters---
    Scenario = _m.Attribute(_m.InstanceType)
    xtmf_ScenarioNumber = _m.Attribute(str)
    xtmf_expression = _m.Attribute(str)
    xtmf_result = _m.Attribute(str)

    def __init__(self):
        self.Scenario = _MODELLER.scenario

    def __call__(self, xtmf_ScenarioNumber, xtmf_expression, xtmf_result):

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        self.expression = xtmf_expression
        self.result = xtmf_result
       
        spec = self.matrix_calculator_spec()

        report = matrixCalculator(spec, self.Scenario)
        return ""

    def matrix_calculator_spec(self):
        spec = {
            "result": self.result,
            "expression": self.expression,
            "type": "MATRIX_CALCULATION"            
            }
        return spec


