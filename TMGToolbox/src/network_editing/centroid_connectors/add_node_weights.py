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
Automatic Node Weight Generator

    Authors:  Monika Nasterska, Peter Kucirek

    Intended for use with CCGEN
'''

#---VERSION HISTORY
'''
    0.1.0 Created April 12, 2016
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

class AddNodeWeights(_m.Tool()):

    version = '0.1.0'
    tool_run_msg = ""
    report_html = ""
    Scenario = _m.Attribute(_m.InstanceType)
    MassAttribute = _m.Attribute(_m.InstanceType)

    def __init__(self):
        self.Scenario = _MODELLER.scenario
        self._tracker = _util.ProgressTracker(5)

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Add Node Weights v%s" %self.version,
                                description="Adds node weights to existing network nodes \
                                for use in centroid generation. Higher weights are \
                                more likely to be connected to centroid connectors in CCGEN.\
                                <br><br>The node weights are assigned as follows: \
                                <br> <ul style=\"list-style-type:none\">\
                                <li><b>1</b>: default value \
                                <li><b>2</b>: nodes at intersections with transit stop(s) \
                                <li><b>3</b>: mid-block nodes without any transit stops \
                                <li><b>4</b>: mid-block nodes with transit stop(s) \
                                <li><b>5</b>: dead-end nodes without any transit stops \
                                <li><b>6</b>: dead-end nodes with transit stop(s)</ul>\
                                ",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario(tool_attribute_name="Scenario",
                        title="Select Scenario",
                        allow_none=False)

        pb.add_select_attribute(tool_attribute_name="MassAttribute",
            filter='NODE',
            allow_none=True,
            title="Node weight attribute",
            note="Attribute which node weights will be stored in.")

        return pb.render()

    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
                     
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise

    def _execute(self):
        network = self.Scenario.get_network()
        print 'loaded network'

        network.create_attribute('NODE', 'is_stop', False)
        for segment in network.transit_segments():
            if segment.allow_boardings or segment.allow_alightings:
                segment.i_node.is_stop = True
        print 'flagged all transit stops'

        network.create_attribute('NODE', 'degree', 0)
        for node in network.regular_nodes():
            neighbours = set()
            for link in node.outgoing_links():
                j_node = link.j_node
                if j_node.is_centroid: continue #Skip connected centroids
                neighbours.add(j_node.number)
            for link in node.incoming_links():
                i_node = link.i_node
                if i_node.is_centroid: continue #Skip connected centroids
                neighbours.add(i_node.number)
            node.degree = len(neighbours)
        print "calculated degrees"

        for node in network.regular_nodes():
            weight = 1
            degree = node.degree
            if degree == 1:
                weight = 5
            elif degree == 2:
                weight = 3
    
            if node.is_stop: weight += 1
            node[self.MassAttribute.id] = weight
        print "processed node weight"

        self.Scenario.publish_network(network, resolve_attributes= True)
        print "published network"

        self.tool_run_msg = _m.PageBuilder.format_info("Node weights have successfully been added to %s." %(self.MassAttribute.id))