'''
    Copyright 2016 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Delete Scenario

    Authors: JamesVaughan

    Latest revision by: JamesVaughan
    
    
    This tool will allow XTMF to be able to delete a matrix within 
    an EMME Databank.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2016-03-24 by JamesVaughan
    
    
'''
import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.

class DeleteMatrix(_m.Tool()):
    version = '0.0.1'
    Scenario = _m.Attribute(int)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Delete Matrix",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")
        
        return pb.render()
    
    def run(self):
        pass

    def __call__(self, Scenario):  
        try:
            self._execute(Scenario)
        except Exception as e:
            raise Exception(_traceback.format_exc())

    def _execute(self, Scenario):
        project = _MODELLER.emmebank
        scenario = project.scenario(str(Scenario))
        if scenario is None:
            print("A delete was requested for scenario " + str(Scenario) + " but the scenario does not exist.")
            return
        if scenario.delete_protected == True:
            scenario.delete_protected = False
        project.delete_scenario(scenario.id)