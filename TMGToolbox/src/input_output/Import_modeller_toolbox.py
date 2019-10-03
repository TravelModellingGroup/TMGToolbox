"""
    Copyright 2018 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
"""

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import inro.modeller as _m
import os
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

class ExportSubareaTool(_m.Tool()):
    version = '1.1.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    #---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    
    xtmf_ModellerLocation = _m.Attribute(int)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario
             
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(
            self, title="Add Modeller Toolbox v%s" % self.version,
            description="Not Callable from Modeller. Please use XTMF. EXPERIMENTAL",
            branding_text="- XTMF")
        return pb.render()

    def __call__(self, xtmf_ModellerLocation):

        self.Scenario = _m.Modeller().emmebank.scenario(int(xtmf_ScenarioNumber))
        if os.path.isfile(self.ModellerLocation) == True:
            self.ModellerLocation = str(xtmf_ModellerLocation)
        else:
            raise Exception ("Modeller toolbox does not exist")

       
        try:
            print "Adding Toolbox"
            self._execute()
            print "Toolbox added"
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(self):
        with _m.logbook_trace(name="Adding Toolbox (%s v%s)" %(self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
            self._tracker.reset()
            _m.Modeller().desktop.add_modeller_toolbox(self.ModellerLocation)


    def _getAtts(self):
        atts = {"Run Title": "Add Modeller Toolbox",
                "Toolbox Location": self.ModellerLocation,
                "self": self.__MODELLER_NAMESPACE__}
        return atts