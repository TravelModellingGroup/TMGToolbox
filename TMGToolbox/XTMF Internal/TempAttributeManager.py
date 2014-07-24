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

    Latest revision by: pkucirek
    
    
    Low-level tool to create an extra attribute context-manager equivalent for
    XTMF.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-03-25 by pkucirek
     
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

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
                 xtmf_AttributeDefault, xtmf_DeleteFlag):
        scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        exatt = scenario.extra_attribute(xtmf_AttributeId)
        if xtmf_DeleteFlag and exatt != None:
            scenario.delete_extra_attribute(xtmf_AttributeId)
        else:
            if exatt != None:
                scenario.delete_extra_attribute(xtmf_AttributeId)
            scenario.create_extra_attribute(xtmf_AttributeDomain, xtmf_AttributeId, xtmf_AttributeDefault)
    
    