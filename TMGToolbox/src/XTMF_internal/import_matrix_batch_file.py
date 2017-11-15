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

import os
import time
import math
import inro.modeller as _m
import traceback as _traceback

class LoadMatrix(_m.Tool()):
    
    MatrixFile = _m.Attribute(str)
    ScenarioId = _m.Attribute(int)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Load a matrix",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    def __call__(self, MatrixFile, ScenarioId):
        try:
            batch_matrix = None
            try:
                batch_matrix = _m.Modeller().tool("inro.emme.standard.data.matrix.matrix_transaction")
            except Exception, e:
                batch_matrix = _m.Modeller().tool("inro.emme.data.matrix.matrix_transaction")
            
            scenario = _m.Modeller().emmebank.scenario(ScenarioId)
            if not scenario:
                raise Exception("Scenario %s does not exist." % ScenarioId)
            
            #---Peek at the file to delete
            self._peek(MatrixFile)
            
            batch_matrix(transaction_file = MatrixFile,
                            throw_on_error = True,
                            scenario=scenario)
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
        
        self.XTMFBridge.ReportProgress(1.0)
        
    def _peek(self, file):
        batch = open(file)
        
        for line in batch.readlines():
            if line.startswith('a'):
                id = self._parseMatrixHeader(line)
                
                mtx = _m.Modeller().emmebank.matrix(id)
                if mtx is not None:
                    _m.Modeller().emmebank.delete_matrix(id)
                return
    
    def _parseMatrixHeader(self, header):
        args = header.split(' ')
        
        # Check if the matrix= keyword is used.
        for i in range(1, len(args)):
            arg = args[i]
            if arg.startswith('matrix='):
                return arg.split('=')[1]
        
        # Else, assume the first argument is the matrix name
        return args[1]
        
        
           