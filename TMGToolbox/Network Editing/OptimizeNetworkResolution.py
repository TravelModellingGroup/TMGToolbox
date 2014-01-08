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
Optimize Network Resolution

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Deletes cosmetic nodes from the network, merging their connected links together.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created
    
    0.2.0 Expanded the tool to encompass transit as well. Added the ability to specify attribute
        aggregation functions
        
    0.3.0 Added the ability to disable re-computing link lengths.
    
    0.4.0 Fully debugged and working. This should be a stable version.
    
    0.5.0 Added the feature to perform optimization on only a subset of nodes.
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import numpy as _numpy
import math
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

# Static set function objects for later
def _avg(val1, val2):
    return (val1 + val2) / 2.0

def _sum(val1, val2):
    return val1 + val2

def _except(val1, val2):
    return val1

def _zero(val1, val2):
    return 0

AGGREGATIONS = {0: _except,
                1: _avg,
                2: _sum,
                3: min,
                4: max,
                5: _zero}

LINEATTS = ['description', 'headway', 'speed', 'layover_time', 'data1', 'data2', 'data3']
SEGATTS = ['allow_alightings', 'allow_boardings', 'dwell_time', 'factor_dwell_time_by_length',
           'transit_time_func', 'data1', 'data2', 'data3']

class OptimizeNetworkResolution(_m.Tool()):
    
    version = '0.5.0'
    tool_run_msg = ""
    number_of_tasks = 5 # For progress reporting, enter the integer number of tasks here
    significant_digits = 5 #Static number to round the emmebank's coordinate user length
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    OriginalScenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    NewScenario = _m.Attribute(int)
    RecalculateLinkLengths = _m.Attribute(bool)
    NodeSelectionExpression = _m.Attribute(str)
    
    LinkTypeAggregationOption = _m.Attribute(int)
    LinkLanesAggregationOption = _m.Attribute(int)
    LinkVdfAggregationOption = _m.Attribute(int)
    LinkData1AggregationOption = _m.Attribute(int)
    LinkData2AggregationOption = _m.Attribute(int)
    LinkData3AggregationOption = _m.Attribute(int)
    
    SegmentTtfAggregationOption = _m.Attribute(int)
    SegmentDwellTimeAggregationOption = _m.Attribute(int)
    SegmentData1AggregationOption = _m.Attribute(int)
    SegmentData2AggregationOption = _m.Attribute(int)
    SegmentData3AggregationOption = _m.Attribute(int)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.OriginalScenario = _MODELLER.scenario #Default is primary scenario
        self.NodeSelectionExpression = "all"
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Optimize Network Resolution v%s" %self.version,
                     description="<p class='tmg_left'>Removes unnecessary nodes from the network \
                         by converting them to link shape vertices. Nodes attached to centroid \
                         connectors, nodes as the j-node of an intersection, and nodes serving \
                         as transit stops are always preserved. \
                         Otherwise, nodes connected to exactly two nodes either through two or \
                         four links will be removed UNLESS selected attributes conflict across \
                         two links-to-be-merged.\
                         <br><br>Users can select how and if they want the various link and \
                         transit segment attributes merged using the various options below.\
                         Selecting the <b>'Except'</b> option disables merging and tells the \
                         tool to check for attribute conflicts.\
                         <br><br><font color='blue'><b>Update:</b></font> Can now remove only \
                         a selected subset of nodes. Use the 'Node Filter Expression' to select \
                         the subset of nodes to remove.\
                         <br><br><font color='red'>Warning: Currently does NOT merge any \
                         scenario extra attributes.</font></p>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='OriginalScenario',
                               title='Original Scenario:',
                               allow_none=False)
        
        pb.add_new_scenario_select(tool_attribute_name='NewScenario',
                                   title='Scenario copy')
        
        pb.add_checkbox(tool_attribute_name='RecalculateLinkLengths',
                        label="Recalculate Link Lengths?",
                        note="If left unchecked, merged links lengths\
                            <br>will simply be summed.")
        
        pb.add_text_box(tool_attribute_name='NodeSelectionExpression',
                        size=100, title="Node Filter Expression",
                        multi_line=True,
                        note="Only nodes which satisfy this expression will be considered.")
        
        pb.add_header("LINK ATTRIBUTE AGGREGATION OPTIONS")
        
        defaultKeyVal = {0: "Except",
                         1: "Average",
                         2: "Sum",
                         3: "Min",
                         4: "Max",
                         5: "Zero"}
        
        with pb.add_table(visible_border=False) as t:            
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkTypeAggregationOption',
                              title="Type",
                              keyvalues=defaultKeyVal)
            
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkLanesAggregationOption',
                              title="Lanes",
                              keyvalues=defaultKeyVal)
            
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkVdfAggregationOption',
                              title="VDF",
                              keyvalues={0: "Except",
                                         3: "Min",
                                         4: "Max"})
            t.new_row()
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkData1AggregationOption',
                              title="Data1",
                              keyvalues=defaultKeyVal)
            
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkData2AggregationOption',
                              title="Data2",
                              keyvalues=defaultKeyVal)
                
            with t.table_cell():
                pb.add_select(tool_attribute_name='LinkData3AggregationOption',
                              title="Data3",
                              keyvalues=defaultKeyVal)
                
        pb.add_header("TRANSIT SEGMENT ATTRIBUTE AGGREGATION OPTIONS")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_select(tool_attribute_name='SegmentTtfAggregationOption',
                              title="TTF",
                              keyvalues={0: "Except"})
            
            with t.table_cell():
                pb.add_select(tool_attribute_name='SegmentDwellTimeAggregationOption',
                              title="Dwell Time",
                              keyvalues=defaultKeyVal)
            
            with t.table_cell():
                pb.add_select(tool_attribute_name='SegmentData1AggregationOption',
                              title="Data1",
                              keyvalues=defaultKeyVal)
                
            with t.table_cell():
                pb.add_select(tool_attribute_name='SegmentData2AggregationOption',
                              title="Data2",
                              keyvalues=defaultKeyVal)
                
            with t.table_cell():
                pb.add_select(tool_attribute_name='SegmentData3AggregationOption',
                              title="Data3",
                              keyvalues=defaultKeyVal)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        #self.TRACKER.reset()
        
        try:
            count = self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done. %s nodes were removed from the network." %count)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            self.TRACKER.reset()
            self._userCoord = round(_MODELLER.emmebank.coord_unit_length, self.significant_digits)
            
            with self._NodeFlagAttributeMANAGER() as nodeFlagAttribute:
                
                self._FlagSelectedNodes(nodeFlagAttribute.id)
            
                network = self.OriginalScenario.get_network()
                self.TRACKER.completeTask()
                
                linkAttributes = {'type': AGGREGATIONS[self.LinkTypeAggregationOption],
                                'num_lanes': AGGREGATIONS[self.LinkLanesAggregationOption],
                                'volume_delay_func': AGGREGATIONS[self.LinkVdfAggregationOption],
                                'data1': AGGREGATIONS[self.LinkData1AggregationOption],
                                'data2': AGGREGATIONS[self.LinkData2AggregationOption],
                                'data3': AGGREGATIONS[self.LinkData3AggregationOption]}
                
                segmentAttribtues = {'transit_time_func': AGGREGATIONS[self.SegmentTtfAggregationOption],
                                     'dwell_time': AGGREGATIONS[self.SegmentDwellTimeAggregationOption],
                                     'data1':AGGREGATIONS[self.SegmentData1AggregationOption],
                                     'data2': AGGREGATIONS[self.SegmentData2AggregationOption],
                                     'data3': AGGREGATIONS[self.SegmentData3AggregationOption],
                                     'allow_alightings': _except,
                                     'allow_boardings': _except,
                                     'factor_dwell_time_by_length': _except}
                
                linkAttributesToCheck = [att for (att, option) in linkAttributes.iteritems() if option == 0]
                segmentAttributesToCheck = [att for (att, option) in segmentAttribtues.iteritems() if option == 0]
                
                with _m.logbook_trace("Flagging node transit stops"):
                    self._FlagTransitStops(network)
                
                with _m.logbook_trace("Flagging superfluous nodes"):
                    nodesToDelete = self._GetRemoveableNodes(network, linkAttributesToCheck, segmentAttributesToCheck)
                
                count = 0
                with _m.logbook_trace("Removing superfluous nodes"):
                    self.TRACKER.startProcess(len(nodesToDelete))
                    
                    for node in nodesToDelete:
                        try:
                            #self._SafeDeleteNode(node, network, linkAttributes, segmentAttribtues)
                            self._SafeDeleteNode2(node, linkAttributes, segmentAttribtues)
                            count += 1
                        except Exception, e:
                            _m.logbook_write("%s deleting node %s: %s" %(e.__class__.__name__, node.id, str(e))) 
                        self.TRACKER.completeSubtask()
                            
                    self.TRACKER.completeTask()
                    _m.logbook_write("Done. %s nodes were deleted." %count)
                
                newScenario = _MODELLER.emmebank.copy_scenario(self.OriginalScenario, self.NewScenario)
                desc = self.OriginalScenario.title.strip()
                if len(desc) > 48:
                    desc = desc[:48] + "...Optimized"
                else:
                    desc += " Optimized"
                newScenario.title = desc
                newScenario.publish_network(network, resolve_attributes=True)
                newScenario.delete_extra_attribute("@cnflg")
                self.TRACKER.completeTask()
                
                
                
                del self._userCoord
                
                return count

    ##########################################################################################################  
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _NodeFlagAttributeMANAGER(self):
        att = self.OriginalScenario.create_extra_attribute('NODE', '@cnflg')
        _m.logbook_write("Created temporary node flag attribute '@cnflg'.")
        
        try:
            yield att
        finally:
            self.OriginalScenario.delete_extra_attribute(att.id)
            _m.logbook_write("Deleted temporary node flag attribute '@cnflg'.")
            
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Original Scenario" : self.OriginalScenario.id,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _FlagSelectedNodes(self, attName):
        try:
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        except Exception, e:
            tool = _MODELLER.tool('inro.emme.standard.network_calculation.network_calculator')
        
        spec = {
                "result": attName,
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "node": self.NodeSelectionExpression
                               },
                "type": "NETWORK_CALCULATION"
                }
        
        self.TRACKER.runTool(tool, spec, scenario=self.OriginalScenario)
    
    def _FlagTransitStops(self, network):
        network.create_attribute('NODE', 'isStop', default_value=False)
        network.create_attribute('NODE', 'transitLines', default_value=None)
        
        self.TRACKER.startProcess(network.element_totals['transit_lines'])
        stops = 0
        for line in network.transit_lines():
            for segment in line.segments(include_hidden=True):
                if segment.allow_alightings or segment.allow_boardings:
                    if not segment.i_node['isStop']:
                        segment.i_node['isStop'] = True
                        stops += 1
                if segment.i_node.transitLines == None:
                    segment.i_node.transitLines = set()
                segment.i_node.transitLines.add(line)
            self.TRACKER.completeSubtask()
        
        _m.logbook_write("%s nodes flagged as stops" %stops)
    
    def _GetRemoveableNodes(self, network, linkAttributesToCheck, segmentAttributesToCheck):
        network.create_attribute('LINK', 'nextLink', default_value=None)
                
        #Get the set of deletable nodes
        nodesToDelete = []
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        for node in network.regular_nodes():
            if self._NodeIsRemovable(node, linkAttributesToCheck, segmentAttributesToCheck):
                nodesToDelete.append(node)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        
        _m.logbook_write("%s nodes flagged for removal" %len(nodesToDelete))
        
        return nodesToDelete
    
    def _NodeIsRemovable(self, node, linkAttributesToCheck, segmentAttributesToCheck):        
        if node['@cnflg'] == 0:
            return False
        
        if node['isStop']:
            return False # Can't remove a transit stop
        
        if node.is_intersection:
            return False # Can't remove an intersection
        
        neighbourNodes = set()
        inLinks, outLinks = 0, 0
        for link in node.incoming_links():
            if link.i_node.is_centroid:
                return False # Skip nodes attached to centroid connectors
            neighbourNodes.add(link.i_node)
            inLinks += 1
        for link in node.outgoing_links():
            if link.j_node.is_centroid: 
                return False # Skip nodes attached to centroid connectors
            outLinks += 1
            neighbourNodes.add(link.j_node)
        
        if len(neighbourNodes) != 2:
            return False #Skip nodes not connected to exactly two other nodes
        
        if inLinks != outLinks:
            return False #Skip nodes with asymmetrical connectivity
        
        if inLinks == 0:
            _m.logbook_write("Node %s is an orphan!" %node)
            return False
        
        # Check to see if the node is serving as link property inflection point
        # (e.g., the road narrows/widens at this node)
        self._MatchAdjacentLinks(node)
        
        for link in node.incoming_links():
            for att in linkAttributesToCheck:
                if link[att] != link['nextLink'][att]:
                    return False
                if link.modes != link['nextLink'].modes:
                    return False
            
            for segment in link.segments():
                for att in segmentAttributesToCheck:
                    nextSegment = segment.line.segment(segment.number + 1)
                    if segment[att] != nextSegment[att]:
                        return False
        
        return True #This node can safely be removed
       
    def _SafeDeleteNode(self, nodeToDelete, network, linkAttributes, segmentAttribtues):
        vertex = (nodeToDelete.x, nodeToDelete.y)
        lines = set()
                
        # Create the new bypass link(s)
        self._MatchAdjacentLinks(nodeToDelete)
        inLinks = [link for link in nodeToDelete.incoming_links()]
        link1 = inLinks[0]
        link2 = link1['nextLink']
        if link2 == None:
            raise Exception("Link has no adjacent! This should never happen!")
        
        for segment in link1.segments():
            lines.add(segment.line)
        
        newLink1 = self._Merge2Links(network, vertex, link1, link2, linkAttributes, segmentAttribtues)
        
        # For two-way links
        link3, link4, newLink2 = None, None, None
        if len(inLinks) == 2:
            link3 = inLinks[1]
            link4 = link1['nextLink']
            if link4 == None:
                raise Exception("Link has no adjacent! This should never happen!")
            
            for segment in link3.segments():
                lines.add(segment.line)
            self._Merge2Links(network, vertex, link3, link4, linkAttributes, segmentAttribtues)
        
        # Try to merge transit lines
        try:
            self._ChangeLines(network, lines, link1.j_node, segmentAttribtues)
        except Exception, e:
            # Revert new links
            network.delete_link(newLink1.i_node.id, newLink1.j_node.id)
            if newLink2 != None:
                network.delete_link(newLink2.i_node.id, newLink2.j_node.id)
            raise
        
        # Delete all original structures
        # Never cascade. preserve the original structure at all costs
        network.delete_link(link1.i_node.id, link1.j_node.id, cascade=False) 
        network.delete_link(link2.i_node.id, link2.j_node.id, cascade=False)
        if link3 != None:
            network.delete_link(link3.i_node.id, link3.j_node.id, cascade=False)
            network.delete_link(link4.i_node.id, link4.j_node.id, cascade=False)
        network.delete_node(nodeToDelete.id, cascade=False)
    
    def _SafeDeleteNode2(self, nodeToDelete, linkAttributes, segmentAttribtues):
        network = nodeToDelete.network
        vertex = (nodeToDelete.x, nodeToDelete.y)
        lines = set()
        for link in nodeToDelete.incoming_links():
            for segment in link.segments():
                lines.add(segment.line) 
        for link in nodeToDelete.outgoing_links():
            for segment in link.segments():
                lines.add(segment.line)
                        
        neighbours = [n for n in self._GetNeighbourNodes(nodeToDelete)]
        if len(neighbours) != 2:
            raise Exception("Node does not have exactly 2 nieghbours: %s" %neighbours)
        
        newLink1 = self._MergeNeighbours(nodeToDelete, neighbours[0], neighbours[1], linkAttributes)
        newLink2 = self._MergeNeighbours(nodeToDelete, neighbours[1], neighbours[0], linkAttributes)
        
        # Try to merge transit lines
        try:
            self._ChangeLines(network, lines, nodeToDelete, segmentAttribtues)
        except Exception, e:
            # Revert new links if an error occurs
            if newLink1 != None:
                network.delete_link(newLink1.i_node.id, newLink1.j_node.id)
            if newLink2 != None:
                network.delete_link(newLink2.i_node.id, newLink2.j_node.id)
            raise
        
        # Delete the node
        def tryDelete(i, j):
            if network.link(i.id,j.id) != None:
                network.delete_link(i.id, j.id, cascade=False)
        
        tryDelete(neighbours[0], nodeToDelete)
        tryDelete(neighbours[1], nodeToDelete)
        tryDelete(nodeToDelete, neighbours[0])
        tryDelete(nodeToDelete, neighbours[1])
        
        network.delete_node(nodeToDelete.id, cascade=False)
    
    def _MergeNeighbours(self, node, neighbour1, neighbour2, linkAttributes):
        network = neighbour1.network
        vertex = (node.x, node.y)
        
        if network.link(neighbour1.id, node.id) == None:
            return None #This direction does not exist.
        
        link1 = network.link(neighbour1.id, node.id)
        link2 = network.link(node.id, neighbour2.id)
        newLink = network.create_link(neighbour1.id, neighbour2.id, link1.modes)
        
        newLink.vertices.extend(link1.vertices) #Add the first link's vertices
        newLink.vertices.append(vertex) #Add the vertex to the link shape
        newLink.vertices.extend(link2.vertices) #Add the next link's vertices
        
        if self.RecalculateLinkLengths:
            newLink.length = self._CalculateLinkLength(newLink)
        else:
            newLink.length = link1.length + link2.length
        
        # Update the new link's attributes
        for (att, func) in linkAttributes.iteritems():
            newLink[att] = func(link1[att], link2[att])
        
        return newLink
        
    def _ChangeLines(self, network, setOfLines, nodeToDelete, segmentAttributes):
        tempLines = {}
        lineCounter = 0
        
        # Attempt to modify the lines, making copies as we go
        for line in setOfLines:
            try:
                tempLine = self._CreateTempMergedLine(network, line, nodeToDelete, segmentAttributes, lineCounter)
                tempLines[line] = tempLine
                lineCounter += 1
            except Exception, e:
                _m.logbook_write("%s encountered while attempting to delete node %s from line \
                    %s: %s" %(e.__class__.__name__, nodeToDelete.id, line.id, e))
                # Remove temporary transit lines
                for tempLine in tempLines.itervalues():
                    network.delete_transit_line(tempLine.id)
                raise
        
        # Overwrite the original line with the copy
        for (originalLine, copy) in tempLines.iteritems():
            self._CopyTempLine(network, originalLine, copy)
    
    def _Merge2Links(self, network, vertex, link1, link2, linkAttributes, segmentAttributes):
        neighbour1 = link1.i_node
        neighbour2 = link2.j_node
        
        # Create the new bypass links before deleting.
        newLink = network.create_link(neighbour1.id, neighbour2.id, link1.modes)
        newLink.vertices.extend(link1.vertices) #Add the first link's vertices
        newLink.vertices.append(vertex) #Add the vertex to the link shape
        newLink.vertices.extend(link2.vertices) #Add the next link's vertices
        if self.RecalculateLinkLengths:
            newLink.length = self._CalculateLinkLength(newLink)
        else:
            newLink.length = link1.length + link2.length
        
        # Update the new link's attributes
        for (att, func) in linkAttributes.iteritems():
            newLink[att] = func(link1[att], link2[att])
        
        return newLink
    
    def _CreateTempMergedLine(self, network, originalLine, nodeToDelete, segmentAttributes, lineCounter):
        #Copy the itinerary
        itinerary = [node.id for node in originalLine.itinerary()]
        maxSegmentIndex = len(itinerary) - 1
        removalIndices = [] #Contains the location(s) of the deleted node in the line's itinerary
        while(nodeToDelete.id in itinerary):
            removalIndices.append(itinerary.index(nodeToDelete.id))
            itinerary.remove(nodeToDelete.id)

        newLine = network.create_transit_line("TMP%s" %lineCounter, originalLine.vehicle.id, itinerary)
        for att in LINEATTS: #Copy line attributes
            newLine[att] = originalLine[att]
        
        offset = 0
        for newSegment in newLine.segments(include_hidden=True):
            if (newSegment.number + 1 + offset) in removalIndices:
                #This segment was merged
                originalSegment1 = originalLine.segment(newSegment.number + offset)
                originalSegment2 = originalLine.segment(originalSegment1.number + 1)
                
                #Merge its attributes
                for (att, func) in segmentAttributes.iteritems():
                    newSegment[att] = func(originalSegment1[att], originalSegment2[att])
                
                #Increment the offset
                offset += 1
            else:
                #Segment was not merged
                originalSegment = originalLine.segment(newSegment.number + offset)
                for att in SEGATTS:
                    newSegment[att] = originalSegment[att]
        
        return newLine
    
    def _CopyTempLine(self, network, originalLine, tempLine):
        id = originalLine.id
        network.delete_transit_line(id)
        itin = [node.id for node in tempLine.itinerary()]
        newLine = network.create_transit_line(id, tempLine.vehicle, itin)
        for att in LINEATTS:
            newLine[att] = tempLine[att]
            
        for newSegment in newLine.segments(include_hidden=True):
            for att in SEGATTS:
                newSegment[att] = tempLine.segment(newSegment.number)[att]
        
        network.delete_transit_line(tempLine.id)        
        
    def _CalculateLinkLength(self, link):
        length = 0
        prevVertex = (link.i_node.x, link.i_node.y)
        for vertex in link.vertices:
            length += math.sqrt((vertex[0] - prevVertex[0]) * (vertex[0] - prevVertex[0]) +
                                  (vertex[1] - prevVertex[1]) * (vertex[1] - prevVertex[1]))
            prevVertex = vertex
        vertex = (link.j_node.x, link.j_node.y)
        length += math.sqrt((vertex[0] - prevVertex[0]) * (vertex[0] - prevVertex[0]) +
                                  (vertex[1] - prevVertex[1]) * (vertex[1] - prevVertex[1]))
        
        return length * self._userCoord
    
    def _GetNeighbourNodes(self, node):
        neighbours = set()
        for link in node.incoming_links():
            neighbours.add(link.i_node)
        for link in node.outgoing_links():
            neighbours.add(link.j_node)
        return neighbours
    
    def _MatchAdjacentLinks(self, node):
        inLinks = [link for link in node.incoming_links()]
        outLinks = [link for link in node.outgoing_links()]
        
        if len(inLinks) == 1:
            inLinks[0]['nextLink'] = outLinks[0]
            outLinks[0]['nextLink'] = inLinks[0]
        elif len(inLinks) == 2:
            if inLinks[0].reverse_link == outLinks[0]:
                inLinks[0]['nextLink'] = outLinks[1]
                outLinks[1]['nextLink'] = inLinks[0]
                inLinks[1]['nextLink'] = outLinks[0]
                outLinks[0]['nextLink'] = inLinks[1]
            else:
                inLinks[0]['nextLink'] = outLinks[0]
                outLinks[1]['nextLink'] = inLinks[1]
                inLinks[1]['nextLink'] = outLinks[1]
                outLinks[0]['nextLink'] = inLinks[0]
        else:
            raise Exception("Cannot match adjacent links for node %s with degrees %s != 2" %(node, len(inLinks)))
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    