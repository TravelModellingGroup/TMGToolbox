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
import os.path
import time
import math
import inro.modeller as _m
import math
import traceback as _traceback

class CheckConnectorSpeeds(_m.Tool()):
    
    Scenario = _m.Attribute(_m.InstanceType)
    tool_run_msg = ""
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Check connector speeds",
                     description="Checks that all connectors are set to 40 km/hr as per NCS11.<br><br>\
                                 Reports any errors in the logbook.",
                                 branding_text= "- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
                pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select scenario",
                               allow_none=False)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        try:
           self()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
    
    def __call__(self):
        report = ""
        
        with _m.logbook_trace(name="Check connector speeds",
                                     attributes={
                                         "Scenario" : self.Scenario.id,
                                         "self" : self.__MODELLER_NAMESPACE__}):
            _m.logbook_write(
                name="Checking connector speeds for scenario %s" %self.Scenario.id,
                attributes={
                    "version":"1.00.00"})
            
            linksChecked = 0
            problemLinks = 0
            for link in self.Scenario.get_network().links():
                
                if link.i_node.is_centroid or link.j_node.is_centroid:
                    #link is a centroid connector
                    if link.data2 != 40:
                        report += "<br>Centroid connector link <b>" + link.id + "</b> speed should be 40, instead is " + str(link.data2)
                        problemLinks += 1
                
                linksChecked += 1
            _m.logbook_write(name="Report",
                             value=report)
                
        self.tool_run_msg = "Tool complete. " + str(linksChecked) + " links were checked, " + str(problemLinks) + " were flagged as problems. See logbook for details."
                
            
    def linkHasMode(self, Link, Char):
        for c in Link.modes:
            if c.id == Char:
                return True
        
        return False
    
    def linkIsTransitOnly(self, Link):
        hasTransit = False
        hasAuto = False
        
        for c in Link.modes:
            if c.type == 'AUTO':
                hasAuto = True
            elif c.type == 'TRANSIT':
                hasTransit = True
        
        return hasTransit and not hasAuto
 