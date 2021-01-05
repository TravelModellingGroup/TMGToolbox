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
MODIFY WALK MODES

    Authors: pkucirek

    Latest revision by: pkucirek 
    
    
    Adds modes 'v', 'u', and 'y' to the network, and modifies the network such that 
    'v' is used only on centroid connectors, 'w' is permitted on non-connector links,
    and that 'y' is only used on station-centroid-connectors. Also adds walk-only reverse 
    links for one-way roads (such as Richmond and Adelaide).
    
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created March 14, 2013
    
    0.1.1 Added the ability to add the 'y' mode to station-centroid-connector links.
            Also updated to perform the flagging first, in order to catch selector
            parsing errors early.
            
    0.1.2 Fixed the Y mode addition to also use the station egress links.
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_util = _m.Modeller().module('tmg.common.utilities')
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ModifyWalkModes(_m.Tool()):
    
    version = '0.1.2'
    tool_run_msg = ""
        
    #---Variables
    scenario = _m.Attribute(_m.InstanceType) #
    walkableRoadSelector = _m.Attribute(str)
    stationCentroidSelector =_m.Attribute(str)
    
    #---Internal variables
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Modify Walk Modes v%s" %self.version,
                                description="Adds modes 'v', 'u', and 'y' to the network, and modifies the network such that \
                                            'v' is used only on centroid connectors, 'w' is permitted on non-connector links, \
                                            and that 'y' is only used on station-centroid-connectors. Also adds walk-only reverse \
                                            links for one-way roads (such as Richmond and Adelaide).\
                                            <br><br>Assumes that rail and subway nodes are numbered according to \
                                            NCS11.\
                                            <br><br><b>This tool makes irreversible changes to your sceanrio! Be sure to back it \
                                            up before running.</b>",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="scenario",
                               title="Select a scenario",
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name="stationCentroidSelector",
                        size=100,
                        title="Selector for station centroids",
                        note="Write a node selector for station centroids.\
                            <br><br>A filter for centroids will automatically \
                            be applied.",
                        multi_line=True)
        
        pb.add_text_box(tool_attribute_name="walkableRoadSelector",
                        size=100,
                        title="Selector for walkable road links",
                        note="Write a link selector for links which permit walking. A \
                              filter for centroid connectors will automatically be \
                              applied.<br><br>\
                              This selector will also be applied for selecting \
                              walkable one-way road links.",
                        multi_line=True)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete. See logbook for report.")
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="NCS11 Modify Walk Modes v%s" %self.version,
                                     attributes=self._getAtts()):
            
            createModeTool = _m.Modeller().tool('inro.emme.data.network.mode.create_mode')
            changeModeTool = _m.Modeller().tool('inro.emme.data.network.mode.change_mode')
            networkCalcTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
            
            with nested(self._walkableLinkFlagAttributeMANAGER(), #self._yFlagAttributeMANAGER(),
                        self._stnNodeFlagAttributeMANAGER()):
                
                #---1. Flag links and nodes first to catch parsing errors before irreversible changes are made.
                with _m.logbook_trace("Flagging feasible links"):
                        networkCalcTool(self._getFlagReverseLinksSpec(), scenario=self.scenario)
                        
                with _m.logbook_trace("Flagging station centroids"):
                    networkCalcTool(self._getFlagStationsSpec(), scenario = self.scenario)
                
                #with _m.logbook_trace("Flagging transit connections from station centroids"):
                    #self._flagYLinks()
                
                #---2. Create modes V and U, and set their speed to walking speed.
                network = self.scenario.get_network()
                
                with _m.logbook_trace("Creating new auxiliary transit modes U, V, and Y"):
                    createModeTool(mode_type="AUX_TRANSIT",
                                   mode_id="v",
                                   mode_description="Ac_Transit",
                                   scenario = self.scenario)
                    
                    changeModeTool(mode = 'v',
                                   mode_speed = network.mode('w').speed,
                                   scenario = self.scenario)
                    
                    createModeTool(mode_type="AUX_TRANSIT",
                                   mode_id="u",
                                   mode_description="Diff_op_tr",
                                   scenario = self.scenario)
                    
                    changeModeTool(mode = 'u',
                                   mode_speed = network.mode('w').speed,
                                   scenario = self.scenario)
                    
                    createModeTool(mode_type="AUX_TRANSIT",
                                   mode_id="y",
                                   mode_description="walk_f_pnr",
                                   scenario = self.scenario)
                    
                    changeModeTool(mode = 'y',
                                   mode_speed = network.mode('w').speed,
                                   scenario = self.scenario)
                
                network = self.scenario.get_network() # Need to refresh the network
                #---3. Modify the network modes as required
                with _m.logbook_trace("Modifying network walk modes"):
                    
                    with _m.logbook_trace("Removing W mode from connectors"):
                        self._removeWModeFromConnectors(network.mode('w'))
                    
                    with _m.logbook_trace("Adding V mode to connectors"):
                        self._addVModeToConnectors(network.mode('v'))
                    
                    with _m.logbook_trace("Adding Y mode to station connectors"):
                        self._addYModeToStationConnectors(network.mode('y'))
                    
                    with _m.logbook_trace("Adding W mode to walkable road links"):
                        _m.logbook_write("Walkable links selector = '%s'" %self.walkableRoadSelector)
                        self._addWModeToRoads(network.mode('w'))
                
                #---4 Create walk-only reverse links on one-way roads (e.g. Richmond St. in Toronto)
                            
                with _m.logbook_trace("Creating walk only reverse links for one-way links"):
                    self._addWalkOnlyReverseLinksToNetwork()
                    

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    @contextmanager
    def _walkableLinkFlagAttributeMANAGER(self):
        #Code here is executed upon entry
        
        _m.logbook_write("Creating temporary link flag attribute.")
        self._walkableLinkFlag =  self.scenario.create_extra_attribute('LINK', '@flg1w', default_value=0)
        
        try:
            yield 
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _m.logbook_write("Deleting temporary link flag attribute.")
            self.scenario.delete_extra_attribute(self._walkableLinkFlag)
    '''
    @contextmanager
    def _yFlagAttributeMANAGER(self):
        #Code here is executed upon entry
        
        _m.logbook_write("Creating temporary y mode link flag attribute.")
        self._yModeLinkFlag =  self.scenario.create_extra_attribute('LINK', '@yflag', default_value=0)
        
        try:
            yield 
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _m.logbook_write("Deleting temporary y mode link flag attribute.")
            self.scenario.delete_extra_attribute(self._yModeLinkFlag)
    '''
    @contextmanager
    def _stnNodeFlagAttributeMANAGER(self):
                #Code here is executed upon entry
        
        _m.logbook_write("Creating temporary station centroid flag attribute.")
        self._stnNodeFlag =  self.scenario.create_extra_attribute('NODE', '@stn', default_value=0)
        
        try:
            yield 
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            _m.logbook_write("Deleting temporary station centroid flag attribute.")
            self.scenario.delete_extra_attribute(self._stnNodeFlag)
            
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "Station Node Selector" : self.stationCentroidSelector,
                "Walkable Links Selector": self.walkableRoadSelector,
                "Is running from XTMF?" : str(self.isRunningFromXTMF),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _getFlagReverseLinksSpec(self):
        return {
                "result": self._walkableLinkFlag.id,
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "link": "ci=0 and cj=0 and %s" %self.walkableRoadSelector
                                },
                "type": "NETWORK_CALCULATION"
                }
        
    def _getFlagStationsSpec(self):
        return {
                "result": self._stnNodeFlag.id,
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "node": "ci=1 and %s" %self.stationCentroidSelector
                                },
                "type": "NETWORK_CALCULATION"
                }
    '''  
    def _flagYLinks(self):
        network = self.scenario.get_network()
        linksFlagged = 0
        
        for link in network.links():
            #Only flag links which connect to identified stations
            if link.i_node[self._stnNodeFlag.id] == 1:
                transitOnlyLinks = 0
                allLinks = 0
                
                transitOnlyLinks += self._getNumberOfTransitOnlyLinks(link.j_node.outgoing_links())
                transitOnlyLinks += self._getNumberOfTransitOnlyLinks(link.j_node.incoming_links())
                allLinks += self._getNumberOfLinks(link.j_node.outgoing_links())
                allLinks += self._getNumberOfLinks(link.j_node.incoming_links())
                
                if allLinks == transitOnlyLinks:
                    link[self._yModeLinkFlag.id] = 1
                    linksFlagged += 1
                    
            elif link.j_node[self._stnNodeFlag.id] == 1:
                transitOnlyLinks = 0
                allLinks = 0
                
                transitOnlyLinks += self._getNumberOfTransitOnlyLinks(link.i_node.outgoing_links())
                transitOnlyLinks += self._getNumberOfTransitOnlyLinks(link.i_node.incoming_links())
                allLinks += self._getNumberOfLinks(link.i_node.outgoing_links())
                allLinks += self._getNumberOfLinks(link.i_node.incoming_links())
                
                if allLinks == transitOnlyLinks:
                    link[self._yModeLinkFlag.id] = 1
                    linksFlagged += 1
                    
        self.scenario.publish_network(network)
        _m.logbook_write("%s links flagged in network." %linksFlagged)
    
    def _getNumberOfLinks(self, linkSet):
        count = 0
        for l in linkSet:
            count += 1
        return count
    
    def _getNumberOfTransitOnlyLinks(self, linkSet):
        transitOnlyLinks = 0
        for link in linkSet:
            tModes = 0
            cModes = 0
            for m in link.modes:
                if m.type == 'AUTO':
                    cModes +=1
                elif m.type == 'TRANSIT':
                    tModes +=1
                    
            if tModes > 0  and cModes == 0:
                transitOnlyLinks += 1
        
        return transitOnlyLinks
    '''
    
    def _removeWModeFromConnectors(self, wMode):
        
        changeLinkModeTool = _m.Modeller().tool('inro.emme.data.network.base.change_link_modes')
        
        changeLinkModeTool(modes = wMode,
                           action = 'DELETE',
                           selection = "ci=1 or cj=1",
                           scenario = self.scenario)
    
    def _addVModeToConnectors(self, vMode):
        changeLinkModeTool = _m.Modeller().tool('inro.emme.data.network.base.change_link_modes')
        
        changeLinkModeTool(modes = vMode,
                           action = 'ADD',
                           selection = "ci=1 or cj=1",
                           scenario = self.scenario)
    
    def _addYModeToStationConnectors(self, yMode):
        
        
        changeLinkModeTool = _m.Modeller().tool('inro.emme.data.network.base.change_link_modes')
        
        changeLinkModeTool(modes = yMode,
                           action = 'SET',
                           selection = "{0}=1 and j=97000,99000".format(self._stnNodeFlag.id),
                           scenario = self.scenario)
        
        changeLinkModeTool(modes = yMode,
                           action = 'SET',
                           selection = "{0}j=1 and i=97000,99000".format(self._stnNodeFlag.id),
                           scenario = self.scenario)
    
    def _addWModeToRoads(self, wMode):
        changeLinkModeTool = _m.Modeller().tool('inro.emme.data.network.base.change_link_modes')
        
        changeLinkModeTool(modes = wMode,
                           action = 'ADD',
                           selection = "ci=0 and cj=0 and %s" %self.walkableRoadSelector,
                           scenario = self.scenario)
    
    def _addWalkOnlyReverseLinksToNetwork(self):
        network = self.scenario.get_network()
        
        modes = ['w']
        report = "<h2>Reverse Link Creation Report</h2>"
        counter = 0
        
        for link in network.links():
            if link[self._walkableLinkFlag.id] == 0:
                continue #skip links which shouldn't be one-way roads
            
            if link.reverse_link is None:
                # Reverse link doesn't exist, therefore it is a one way road
                
                rLink = network.create_link(link.j_node.id, link.i_node.id, modes)
                rLink.length = link.length
                rLink.type = link.type
                rLink.num_lanes = 0.0
                rLink.volume_delay_func = 90
                rLink.data2 = 40
                rLink.data3 = 9999
                
                report += "<br>Created link %s." %rLink
                counter += 1
        
        self.scenario.publish_network(network)
        _m.logbook_write("Created %s new links in the network. Click for report." %counter, value=report)
            
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    