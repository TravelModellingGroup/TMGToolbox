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
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)


class CheckLinkLanes(_m.Tool()):
    
    Scenario = _m.Attribute(_m.InstanceType)
    tool_run_msg = ""
    
    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Check Link lanes",
                     description="Checks that special link type (centroid connectors, transit-only links) \
                                 meet NCS11 requirements.<br><br> Reports any errors in the logbook.",
                     branding_text="- TMG Toolbox")
        
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
        report = "<h3>Check Link Lanes</h3>\
                    <table><tr>\
                    <th>I Node</th><th>J Node</th><th>Link Class</th><th>Req'd Lanes</th><th>Actual Lanes</th>\
                    </tr>"
        
        with _m.logbook_trace(name="Check Link lanes",
                                     attributes={
                                         "Scenario" : self.Scenario.id,
                                         "self" : self.__MODELLER_NAMESPACE__}):
            _m.logbook_write(
                name="Checking link lanes for scenario %s" %self.Scenario.id,
                attributes={
                    "version":"1.0.1"})
            
            problemLinks = 0
            for link in self.Scenario.get_network().links():
                
                if link.i_node.is_centroid or link.j_node.is_centroid:
                    #link is a centroid connector
                    if link.num_lanes != 2.0:
                        report += "<tr><td>{inode}</td><td>{jnode}</td><td>Centroid connector\
                            </td><td>2.0</td><td>{lanes}</td></tr>".format(inode=link.i_node.id,
                                                                           jnode=link.j_node.id,
                                                                           lanes=str(link.num_lanes))
                        #report += "<br>Centroid connector link <b>" + link.id + "</b> should have 2.0 lanes, instead has " + str(link.num_lanes)
                        problemLinks += 1
                elif self.linkIsTransitOnly(link):
                    #link is exclusive ROW
                    if link.num_lanes != 0.0:
                        report += "<tr><td>{inode}</td><td>{jnode}</td><td>Exclusive transit link\
                            </td><td>0.0</td><td>{lanes}</td></tr>".format(inode=link.i_node.id,
                                                                           jnode=link.j_node.id,
                                                                           lanes=str(link.num_lanes))
                        
                        #report += "<br>Exclusive transit link <b>" + link.id + "</b> should have 0.0 lanes, instead has " + str(link.num_lanes)
                        problemLinks += 1
                elif self.linkHasMode(link, "t") or self.linkHasMode(link, "u"):
                    #transfer link
                    if link.num_lanes != 0.0:
                        report += "<tr><td>{inode}</td><td>{jnode}</td><td>Transfer link\
                            </td><td>0.0</td><td>{lanes}</td></tr>".format(inode=link.i_node.id,
                                                                           jnode=link.j_node.id,
                                                                           lanes=str(link.num_lanes))
                        report += "<br>Transfer link <b>" + link.id + "</b> should have 0.0 lanes, instead has " + str(link.num_lanes)
                        problemLinks += 1
            
            report += "</table>"
            _m.logbook_write(name="Report",
                             value=report)
                
        self.tool_run_msg = _m.PageBuilder.format_info("%s links were flagged as problems. See logbook for details." %problemLinks)
                
            
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
 
            