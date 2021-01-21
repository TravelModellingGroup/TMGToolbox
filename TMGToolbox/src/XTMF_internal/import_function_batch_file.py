'''
    Copyright 2021 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Copy Scenario

    Authors: JamesVaughan

    Latest revision by: JamesVaughan
    
    
    This tool will allow XTMF to be able to execute a vdf batch file into
    an EMME Databank.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2021-01-20 by JamesVaughan
    
    
'''
import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
process = _m.Modeller().tool('inro.emme.data.function.function_transaction')

class CopyScenario(_m.Tool()):
    version = '0.0.1'
    batch_file = _m.Attribute(str)
    scenario_number = _m.Attribute(int)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Import VDF Batch File",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")
        
        return pb.render()
    
    def run(self):
        pass

    def __call__(self, batch_file, scenario_number):  
        try:
            project = _MODELLER.emmebank
            scenario = project.scenario(str(scenario_number))
            process(transaction_file=batch_file,
                    scenario=scenario,
                    throw_on_error = True)
        except Exception as e:
            raise Exception(_traceback.format_exc())
