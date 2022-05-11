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
    Validates existing centroid connectors against a variety of user-defined criteria.

    Author:  Monika Nasterska

'''

#---VERSION HISTORY
'''
    0.1.0 Created April 13, 2016
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

class ValidateConnectors(_m.Tool()):

    version = '0.1.0'
    tool_run_msg = ""
    report_html = ""
    Scenario = _m.Attribute(_m.InstanceType)
    FlagAttribute = _m.Attribute(_m.InstanceType)
    criteria = _m.Attribute(int)
    intCutoff = _m.Attribute(int)
    InfeasibleLinkSelector = _m.Attribute(str)
    ZoneSelector = _m.Attribute(str)


    def __init__(self):
        self.Scenario = _MODELLER.scenario
        self._tracker = _util.ProgressTracker(5)
        self.ZoneSelector = "all"
        self.InfeasibleLinkSelector = "mode = t"

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Validate Centroid Connectors v%s" %self.version,
                                description="Used to validate existing centroid \
                                connectors against user-selected criteria.\
                                <br><br>The criteria options are as follows: \
                                <br> <ul style=\"list-style-type:none\">\
                                <li><b>number of connectors</b>: zones with few connectors may artificially increase \
                                flows on certain links while reducing flows on others.  \
                                <li><b>connectors at intersections</b>: having connectors at intersections can artificially reduce \
                                volumes on neighbouring links, as agents are able to bypass them. \
                                <li><b>connectors to other connectors</b>: connectors to other connectors allow agents to bypass the \
                                transportation network altogether. \
                                <li><b>minimum connector length</b>: the shortest connector length for a particular zone. If this \
                                is too high, it can artificially inflate travel times. Transit mode share is especially sensitive to this.</ul>\
                                ",
                                branding_text="- TMG Toolbox")

        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)

        pb.add_select_scenario(tool_attribute_name="Scenario",
                        title="Select Scenario",
                        allow_none=False)

        pb.add_text_box(tool_attribute_name='ZoneSelector',
                size=300,
                multi_line=True,
                title='Specify which zones to validate.',
                note="Formatted the same as for a network calculation.")

        keyvalues = {1: 'number of connectors is less than the cutoff value', 
                     2: 'number of connectors at intersections is greater than the cutoff value',
                     3: 'number of connectors to other connectors is greater than the cutoff value',
                     4: 'minimum connector length is greater than the cutoff value (in length units)'}
    
        pb.add_radio_group(tool_attribute_name = "criteria",
                                keyvalues = keyvalues,
                                title = 'Select one validation criteria')

        pb.add_text_box(tool_attribute_name='intCutoff',
                        size=2,
                        title = "cutoff value")

        pb.add_text_box(tool_attribute_name='InfeasibleLinkSelector',
                        size=300,
                        multi_line=True,
                        title='Links which do not count as intersections or other connectors.',
                        note="Formatted the same as for a network calculation.")

        pb.add_select_attribute(tool_attribute_name="FlagAttribute",
            filter='NODE',
            allow_none=True,
            title="Attribute to flag zones.",
            note="Zones which meet the selected criteria will be flagged as True/1.")



        return pb.render()

    @_m.method(return_type=six.u)
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

    #########################################################################################

    def _execute(self):

        with _m.logbook_trace(name="{0} v{1}".format(self.__class__.__name__,self.version)):
            flagged_count = 0

            if not self.criteria or not self.intCutoff or not self.FlagAttribute:
                raise Exception ("Criteria, cutoff value and/or flag attribute not specified")

            with _util.tempExtraAttributeMANAGER(self.Scenario, 'NODE') as selectZone, \
                _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK') as excludeLink:
                    self._applyInfeasibleLinkFilter(excludeLink.id)
                    self._applyZoneFilter(selectZone.id) 
                    network = self.Scenario.get_network()

                    for node in network.centroids():
                    
                        #initialize variables
                        node[self.FlagAttribute.id] = False

                        if node[selectZone.id] == 1:

                            intersections = 0
                            connectors = 0
                            conn_centroids = 0
                            min_distance = float("inf")
                    
    
                            for connector in node.outgoing_links():
        
                                #count the number of connectors
                                connectors += 1
        
                                #find the minimum connector length
                                if connector.length < min_distance:
                                    min_distance = connector.length
        
                                #determine if connector is connecting to an intersection
                                #or another connector
                                connected_to_centroid = False
                                degree = 0    
                                for second_link in connector.j_node.outgoing_links():
                                    if second_link[excludeLink.id] == 0:
                                        second_node = second_link.j_node
                                        if second_node != node:
                                            if second_node.is_centroid == False:
                                                degree += 1
                                            else:
                                                connected_to_centroid = True
                                if degree > 2:
                                    intersections +=1
                                if connected_to_centroid:
                                    conn_centroids += 1
    
                            #criteria = number of connectors
                            if self.criteria == 1:
                                if connectors < self.intCutoff:
                                    node[self.FlagAttribute.id] = True
                                    flagged_count += 1
                            #criteria = number of connectors at intersections
                            elif self.criteria == 2:
                                if intersections > self.intCutoff:
                                    node[self.FlagAttribute.id] = True
                                    flagged_count += 1
                            #criteria = number of connectors to other connectors
                            elif self.criteria == 3:
                                if conn_centroids > self.intCutoff:
                                    node[self.FlagAttribute.id] = True
                                    flagged_count += 1
                            #criteria = minimum distance
                            elif self.criteria == 4:
                                if min_distance > self.intCutoff:
                                    node[self.FlagAttribute.id] = True
                                    flagged_count += 1

            self.Scenario.publish_network(network, resolve_attributes= True)

        self.tool_run_msg = _m.PageBuilder.format_info(" {0} zones were flagged.".format(flagged_count))

#----Filters and Exclusions----------------------------------------------------------------------------

    def _applyInfeasibleLinkFilter(self, attributeId): 
        if self.InfeasibleLinkSelector == "" or self.InfeasibleLinkSelector is None:
            self._tracker.completeTask() 
            return
        else:
            spec = {
                    "result": attributeId,
                    "expression": "1",
                    "aggregation": None,
                    "selections": {
                                   "link": self.InfeasibleLinkSelector
                                   },
                    "type": "NETWORK_CALCULATION"
                    }
        tool = None
        try:
            tool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
        except Exception as e:
            tool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
        
        self._tracker.runTool(tool, spec, scenario=self.Scenario)

#------------------------------------------------------------------------------------------------

    def _applyZoneFilter(self, attributeId):
        if self.ZoneSelector == "" or self.ZoneSelector is None:
            self._tracker.completeTask() 
            return
        else:
            spec = {
                    "result": attributeId,
                    "expression": "1",
                    "aggregation": None,
                    "selections": {
                                   "node": self.ZoneSelector + " and ci = 1"
                                   },
                    "type": "NETWORK_CALCULATION"
                    }
        tool = None
        try:
            tool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
        except Exception as e:
            tool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
        
        self._tracker.runTool(tool, spec, scenario=self.Scenario)
