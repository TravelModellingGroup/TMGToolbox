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
_MODELLER = _m.Modeller()
_util = _MODELLER.module('TMG2.Common.Utilities')

class ExportBinaryMatrix(_m.Tool()):
    
    MatrixNumber = _m.Attribute(int)
    MatrixType = _m.Attribute(int)
    
    FileName = _m.Attribute(str)
    
    ScenarioNumber = _m.Attribute(int)
    
    MATRIX_TYPES = {1: 'ms',
                    2: 'mo',
                    3: 'md',
                    4: 'mf'}
    
    def __init__(self):
        self.TRACKER = _util.ProgressTracker(1)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Export a matrix in binary format",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")      
        
        return pb.render()
    
    def __call__(self, MatrixType, MatrixNumber, FileName, ScenarioNumber):
        if not MatrixType in self.MATRIX_TYPES:
            raise IOError("Matrix type '%s' is not recognized. Valid types are " %MatrixType + 
                          "1 for scalar, 2 for origin, 3 for destination, and "+ 
                          "4 for full matrices.")
        
        bank = _MODELLER.emmebank
        
        mtxId = self.MATRIX_TYPES[MatrixType] + str(MatrixNumber)
        matrix =bank.matrix(mtxId)
        if matrix == None:
            raise IOError("Matrix '%s' does not exist." %mtxId)
        
        scenarioRequired = _util.databankHasDifferentZones(bank)
        
        if scenarioRequired:
            if bank.scenario(ScenarioNumber) == None:
                raise ArgumentError("A valid scenario must be specified as there are " +
                                    "multiple zone systems in this Emme project. "+
                                    "'%s' is not a valid scenario." %ScenarioNumber)
            data = matrix.get_data(ScenarioNumber)
        else:
            data = matrix.get_data()
        
        data.save(FileName)
            
        

    