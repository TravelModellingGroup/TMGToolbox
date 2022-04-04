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
Temp Extra Attribute Manager

    Authors: pkucirek

    Latest revision by: JamesVaughan
    
    
    Low-level tool to create an extra attribute context-manager equivalent for
    XTMF.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-25 by pkucirek
    0.0.2 Upgraded to only optionally reset the values to their default
     
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class TempAttributeManager(_m.Tool()):
    
    version = '0.0.2'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    xtmf_ScenarioNumber = _m.Attribute(int)
    xtmf_AttributeId = _m.Attribute(str)
    xtmf_AttributeDomain = _m.Attribute(str)
    xtmf_AttributeDefault = _m.Attribute(float)
    xtmf_DeleteFlag = _m.Attribute(bool)
    xtmf_ResetToDefault = _m.Attribute(bool)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Temp Attribute Manager",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_AttributeId, xtmf_AttributeDomain, 
                 xtmf_AttributeDefault, xtmf_DeleteFlag, xtmf_ResetToDefault):
        # Return True if the attribute was created, False otherwise
        scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)        
        if xtmf_DeleteFlag:
            return self._Delete(scenario, xtmf_AttributeId)
        else:
            return self._CreateIfDoesNotExist(scenario, xtmf_AttributeId, xtmf_AttributeDomain, xtmf_AttributeDefault, xtmf_ResetToDefault)
                
    def _Delete(self, scenario, attribute_id):
        exatt = scenario.extra_attribute(attribute_id)
        scenario.delete_extra_attribute(attribute_id)
        return exatt is not None
    
    def _CreateIfDoesNotExist(self, scenario, attribute_id, attributeDomain, attributeDefault, resetToDefault):
        exatt = scenario.extra_attribute(attribute_id)
        if exatt is None:
            scenario.create_extra_attribute(attributeDomain, attribute_id, attributeDefault)
            return True
        elif exatt.type != attributeDomain:
            self._Delete(scenario, attribute_id)
            exatt = scenario.create_extra_attribute(attributeDomain, attribute_id, attributeDefault)
        elif resetToDefault:
            exatt.initialize(attributeDefault)
        return False