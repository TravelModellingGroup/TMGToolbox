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
import inro.modeller as _m
import traceback as _traceback
from argparse import ArgumentError
from inro.emme.matrix import MatrixData
_MODELLER = _m.Modeller()
_util = _MODELLER.module('TMG2.Common.Utilities')

class ImportBinaryMatrix(_m.Tool()):
    
    MatrixNumber = _m.Attribute(int)
    MatrixType = _m.Attribute(int)
    MatrixDescription = _m.Attribute(str)
    
    FileName = _m.Attribute(str)
    
    ScenarioNumber = _m.Attribute(int)
    
    MATRIX_PREFIXES = {1: 'ms',
                    2: 'mo',
                    3: 'md',
                    4: 'mf'}
    
    MATRIX_TYPES = {1: 'SCALAR',
                    2: 'ORIGIN',
                    3: 'DESTINATION',
                    4: 'FULL'}
    
    def __init__(self):
        self.TRACKER = _util.ProgressTracker(1)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Import a matrix in binary format",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")      
        
        return pb.render()
    
    def __call__(self, MatrixType, MatrixNumber, MatrixDescription, FileName, ScenarioNumber):
        if not MatrixType in self.MATRIX_PREFIXES:
            raise IOError("Matrix type '%s' is not recognized. Valid types are " %MatrixType + 
                          "1 for scalar, 2 for origin, 3 for destination, and "+ 
                          "4 for full matrices.")
        
        bank = _MODELLER.emmebank
        
        scenarioRequired = _util.databankHasDifferentZones(bank)
        if scenarioRequired:
            scenario = bank.scenario(ScenarioNumber)
            if scenario == None:
                raise ArgumentError("A valid scenario must be specified as there are " +
                                    "multiple zone systems in this Emme project. "+
                                    "'%s' is not a valid scenario." %ScenarioNumber)
        else:
            for scenario in bank.scenarios(): break #Get any scenario, since they all have the same zones
        
        data = MatrixData.load(FileName)
        
        matrixId = self.MATRIX_PREFIXES[MatrixType] + str(MatrixNumber)
        matrix = bank.matrix(matrixId)
        if matrix == None:
            matrix = bank.create_matrix(matrixId)
            msg = "Created matrix %s." %matrixId
            print msg
            _m.logbook_write(msg)
        
        if MatrixDescription:
            matrix.description = MatrixDescription
        
        matrix.set_data(data, scenario)
            
        

    