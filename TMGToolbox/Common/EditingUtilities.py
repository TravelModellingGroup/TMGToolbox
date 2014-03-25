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
_MODELLER = _m.Modeller()
_util = _MODELLER.module('TMG2.Common.Utilities')
_geolib = _MODELLER.module('TMG2.Common.Geometry')
import math as _math
from warnings import warn as _warn

class Face(_m.Tool()):
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Network Utilities", branding_text="TMG",
                                description="Collection of small functions (including \
                                a shortest-path calculator) for network editing")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()

#-------------------------------------------------------------------------------------------

def createSegmentAlightingsAttribute(network):
    '''
    The Emme Network API does not by default define an attribute
    for transit alightings on a segment, so this utility function
    create and calculates that attribute.
    
    Since this is NOT an extra attribute, it can be accessed using
    the '.' operand e.g.:
    >>> segment.transit_alightings #This is valid
    '''
    
    if 'transit_alightings' in network.attributes('TRANSIT_SEGMENT'):
        #If the attribute already exists, re-initialize it.
        network.delete_attribute('TRANSIT_SEGMENT', 'transit_alightings') 
    network.create_attribute('TRANSIT_SEGMENT', 'transit_alightings', 0.0)
    
    for line in network.transit_lines():
        for i, segment in enumerate(line.segments(include_hidden=True)):
            if i > 0:
                a = prevVolume + segment.transit_boardings - segment.transit_volume
                if a < 0: a = 0.0 #Alightings can be negative due to rounding error
                segment.transit_alightings = a
            prevVolume = segment.transit_volume 

#-------------------------------------------------------------------------------------------

def isLinkParallel(link):
    '''
    Tests if a link is parallel with its reverse, based on vertices.
    
    Args:
        - link: The link to test
        
    Returns: True if link's reverse exists and is parallel, False otherwise.
    '''
    
    reverse = link.reverse_link
    if reverse == None:
        return False
    revertices = [vtx for vtx in reverse.vertices]
    revertices.reverse()
    
    return revertices == link.vertices

#-------------------------------------------------------------------------------------------

TEMP_LINE_ID = '999999'

def splitLink(newNodes, link, twoWay=True, onLink=True, coordFactor=None, stopOnNewNodes=False):
    '''
    Splits a link at a given node (or nodes). Uses geometry to determine which vertices
    get assigned to which subsequently-created new link (and in what order).
    
    Args:
        - newNodes: A new node (or iterable of nodes) to be inserted into the link
        - twoWay (=True): bool flag whether to also split the reverse link
        - onLink (=True): bool flag whether the new nodes should be adjusted to occur on the link.
        - coordFactor (=None): conversion between coordinate unit and link length
        - stopOnNewNodes (=False): flag to indicate if the new nodes should be used as transit stops.
    
    Returns: A list of all subsequently created links.
    '''
    if "__iter__" in dir(newNodes):
        nodeGeoms = [_geolib.nodeToShape(n) for n in newNodes]
        nodeList = newNodes
    else:
        nodeGeoms = [_geolib.nodeToShape(newNodes)]
        nodeList = [newNodes]
    linkGeom = _geolib.linkToShape(link)
    
    if not coordFactor:
        coordFactor = _MODELLER.emmebank.coord_unit_length
    
    # Set up insertion order of nodes & vertices
    order = [] 
    for i, point in enumerate(nodeGeoms):
        node = nodeList[i]
        dist = linkGeom.project(point)
        order.append((dist, node, True))
        if onLink:
            coord = linkGeom.interpolate(dist)
            node.x = coord.x
            node.y = coord.y
        
    for vertex in link.vertices:
        point = _geolib.Point(vertex)
        dist = linkGeom.project(point)
        order.append((dist, vertex, False))
    order.sort()
    
    def copyLinkAtts(fromLink, toLink, length, vertexBuffer):
        for attname in link.network.attributes('LINK'):
            if attname == 'vertices': continue
            toLink[attname] = fromLink[attname]
        toLink.length = length
        for vtx in vertexBuffer:
            toLink.vertices.append(vtx)
    
    # Insert new nodes
    newLines = []
    newLinksF = []
    newLinksR = []
    network = link.network
    prevDist = 0
    try:
        vertexBuffer = []
        prevNode = link.i_node
        newNode = None
        
        for dist, object, isNode in order:
            if not isNode:
                vertexBuffer.append(object) #object is a vertex
                continue
            
            segLength = (dist - prevDist) * coordFactor
            newNode = object #object is a node, so create the new link
            newLinkF = network.create_link(prevNode.number, newNode.number, link.modes)
            newLinksF.append(newLinkF)
            copyLinkAtts(link, newLinkF, segLength, vertexBuffer)
            
            if link.reverse_link != None and twoWay:
                newLinkR = network.create_link(newNode.number, prevNode.number, link.reverse_link.modes)
                vertexBuffer.reverse()
                copyLinkAtts(link.reverse_link, newLinkR, segLength, vertexBuffer)
                newLinksR.insert(0, newLinkR)
            prevNode = newNode
            prevDist = dist
            vertexBuffer = [] #Clear the buffer
        
        segLength = (linkGeom.length - prevDist) * coordFactor
        newNode = link.j_node #Create the last link
        newLinkF = network.create_link(prevNode.number, newNode.number, link.modes)
        newLinksF.append(newLinkF)
        copyLinkAtts(link, newLinkF, segLength, vertexBuffer)
        if link.reverse_link != None and twoWay:
            newLinkR = network.create_link(newNode.number, prevNode.number, link.reverse_link.modes)
            vertexBuffer.reverse()
            copyLinkAtts(link.reverse_link, newLinkR, segLength, vertexBuffer)
            newLinksR.insert(0, newLinkR)            
        
        # Handle transit lines
        for segment in link.segments():
            lineProxy = TransitLineProxy(segment.line)
            lineProxy.segments.pop(segment.number) #Cut this segment from the line's itinerary
            
            for i, newLink in enumerate(newLinksF):
                segmentProxy = TransitSegmentProxy(segment, newLink.i_node)
                segmentProxy.allowAlightings = stopOnNewNodes
                segmentProxy.allowBoardings = stopOnNewNodes
                lineProxy.segments.insert(segment.number + i, segmentProxy)
            
            lineProxy.id = TEMP_LINE_ID
            tempCopy = lineProxy.copyToNetwork(network) #Copy to temporary line
            #If an error were to occur, it would occur prior to reaching here
            network.delete_transit_line(TEMP_LINE_ID)
            lineProxy.id = segment.line.id
            network.delete_transit_line(lineProxy.id)
            newLines.append(lineProxy.copyToNetwork(network))
            
        if link.reverse_link != None and twoWay:
            for segment in  link.reverse_link.segments():
                lineProxy = TransitLineProxy(segment.line)
                lineProxy.segments.pop(segment.number) #Cut this segment from the line's itinerary
                
                for i, newLink in enumerate(newLinksR):
                    segmentProxy = TransitSegmentProxy(segment, newLink.i_node)
                    segmentProxy.allowAlightings = stopOnNewNodes
                    segmentProxy.allowBoardings = stopOnNewNodes
                    lineProxy.segments.insert(segment.number + i, segmentProxy)
                
                lineProxy.id = TEMP_LINE_ID
                tempCopy = lineProxy.copyToNetwork(network) #Copy to temporary line
                #If an error were to occur, it would occur prior to reaching here
                network.delete_transit_line(TEMP_LINE_ID)                
                lineProxy.id = segment.line.id
                network.delete_transit_line(lineProxy.id)
                newLines.append(lineProxy.copyToNetwork(network))
        
    except Exception, e:
        for newLink in (newLinksF + newLinksR):
            network.delete_link(newLink.j_node.number, newLink.i_node.number)
        for line in newLines:
            network.delete_transit_line(line.id)
        raise
    
    # All new items are created. Delete the old ones
    if link.reverse_link != None:
        network.delete_link(link.j_node.number, link.i_node.number)
    network.delete_link(link.i_node.number, link.j_node.number)
    
    return newLinksF + newLinksR

#-------------------------------------------------------------------------------------------

def addReverseLink(link):
    '''
    For a link without a reverse, this function creates a 
    parallel (e.g. vertices copied) reverse link.
    
    Args:
        - link= The link to copy
    
    Returns: The reverse link (whether it's new or not).
    '''
    if link.reverse_link != None:
        return link.reverse_link
    
    network = link.network
    reverse = network.create_link(link.j_node.id, link.i_node.id, link.modes)
    for att in link.network.attributes('LINK'):
        if att == "vertices":
            continue
        reverse[att] = link[att]
    for vertex in link.vertices:
        reverse.vertices.insert(0, vertex)
    
    return reverse

#-------------------------------------------------------------------------------------------

def changeTransitLineId(line, newId):
    '''
    Modifies an existing line's ID
    
    Args:
        - line= The transit line object to modify
        - newId= The transit line's new ID string. This new ID
            must be unique.
    
    Returns: the modified transit line object
    '''
    
    network = line.segment(0).link.network
    proxy = TransitLineProxy(line)
    proxy.id = newId
    
    newLine = proxy.copyToNetwork(network)
    network.delete_transit_line(line.id)
    
    return newLine

#-------------------------------------------------------------------------------------------

def renumberTransitVehicle(oldVehicle, newId):
    '''
    Changes the ID of a transit vehicle object, updating all dependent transit lines.
    The new ID must not be in use.
    
    Args:
        - oldVehicle: The transit vehicle object to re-number
        - newId: The new ID. Must not be in use
     
     Returns: The new Transit Vehicle object
    '''
    
    net = oldVehicle.network
    
    if net.transit_vehicle(newId) != None:
        raise Exception("Cannot change transit vehicle %s to %s as this ID already exists in the scenario" %(oldVehicle, newId))
    
    created = False
    changedLines = []
    try:
        newVehicle = net.create_transit_vehicle(newId, oldVehicle.mode.id)
        created = True
        for att in newVehicle.network.attributes('TRANSIT_VEHICLE'):
            newVehicle[att] = oldVehicle[att]        
        
        dependants = [line for line in net.transit_lines() if line.vehicle.number == oldVehicle.number]
        for line in dependants:
            line.vehicle = newVehicle
            changedLines.append(line)
        net.delete_transit_vehicle(oldVehicle.number)
    except Exception, e:
        if created:
            net.delete_transit_vehicle(newId)
        for line in changedLines:
            line.vehicle = oldVehicle
        raise
    
    return newVehicle
    
#-------------------------------------------------------------------------------------------

def mergeLinks(node, deleteStop=False, linkOverride={}, segmentOverride={}):
    '''
    Deletes a 2-degree node and merges its connected links. The merged link will 
    always permit the union of modes between its candidate links.
    
    Args:
        - node: A Node object to delete. This node must connect to exactly two
            other nodes. 
        - deleteStop (=False): Allows all incident transit stops to be deleted.
            Nodes at the end of lines CANNOT ever be deleted.
        - linkOverride (={}): Dictionary allows the user to specify a dict of
            [attribute_name: lambda(double => val1, val2)] to override the default
            operation for merging the two attributes (SUM for link length, AVG for
            everything else)
        - segmentOverride (={}): Dictionary is used the same as the linkOverride
            argument, except applied to all merging segments
        
    Returns: None
    '''
    
    neighbourSet = set([link.j_node for link in node.outgoing_links()])
    if len(neighbourSet) != 2:
        raise Exception("Can only delete nodes with a degree of 2 (found %s)" %len(neighbourSet))
    
    linkPairsToMerge = _getLinkPairs(node)
    if linkPairsToMerge == None:
        raise Exception("Impossible to merge configuration of inbound/outbound links")
    
    network = node.network
    newLinks = []
    newLines = []
    lineIdMapping = {}
    TEMP_LINE_ID = 'ZZZZ'
    
    try:
        for link1, link2 in linkPairsToMerge:
            #Merge the links themselves
            if network.link(link1.i_node.number, link2.j_node.number) != None:
                raise Exception("Merged link %s-%s already exists!" %(link1.i_node.number, link2.j_node.number))
            mergedModes = set([m for m in link1.modes] + [m for m in link2.modes])
            mergedLink = network.create_link(link1.i_node.number, link2.j_node.number, mergedModes)
            
            for att in mergedLink._atts:
                if att == 'vertices': continue
                
                if att in linkOverride:
                    mergedLink[att] = linkOverride[att](link1[att], link2[att])
                else:
                    if att == 'length':
                        mergedLink.length = link1.length + link2.length
                    elif att == 'volume_delay_func':
                        mergedLink.volume_delay_func = max(link1.volume_delay_func, link2.volume_delay_func)
                    else:
                        mergedLink[att] = (link1[att] + link2[att]) * 0.5
                        
            for vertex in link1.vertices: mergedLink.vertices.append(vertex)
            for vertex in link2.vertices: mergedLink.vertices.append(vertex)
            
            newLinks.append(mergedLink)
            
            for segment in link1.segments():
                proxy = TransitLineProxy(segment.line)
                proxySegment1 = proxy.segments[segment.number] #This will become the merged segment
                proxySegment2 = proxy.segments.pop(segment.number + 1) #Remove the following segment from the proxy
                
                proxySegment1 = TransitSegmentProxy()
                proxySegment2 = TransitSegmentProxy()
                
                #Merge attributes slaved to a sub function because oh god it's messy
                _mergeSegments(segmentOverride, proxySegment1, proxySegment2)
                
           
    except Exception, e:
        for link in newLinks:
            network.delete_link(link.i_node.number, link.j_node.number)
        for line in newLines:
            network.delete_transit_line(line.id)
        raise

def _getLinkPairs(node):
    oLinks = [link for link in node.outgoing_links()]
    iLinks = [link for link in node.incoming_links()]
    
    if len(oLinks) == 1 and len(iLinks) == 1:
        return [(iLinks[0], oLinks[0])]
    elif len(oLinks) == 2 and len(iLinks) == 2:
        pair1 = (iLinks[0], iLinks[1].reverse_link)
        pair2 = (iLinks[1], iLinks[0].reverse_link)
        return [pair1, pair2]
    else:
        return None

def _canDeleteStop(node, deleteStop):
    for link in node.incoming_links():
        for segment in link.segments():
            index = segment.number
            nextSegment = segment.line.segment(index + 1) #Guaranteed to exist, because of the hidden segment
            if nextSegment.link == None: return False #Cannot delete the last node in an itinerary
            
            if nextSegment.allow_boardings or nextSegment.allow_alightings:
                return deleteStop
    for link in node.outgoing_links():
        for segment in link.segments():
            if segment.number == 0: return False #Cannot delete the first node in an itinerary
            
            if segment.allow_boardings or segment.allow_alightings:
                return deleteStop
    return True

def _mergeSegments(segmentOverride, proxySegment1, proxySegment2):
    if 'transit_time_func' in segmentOverride:
        proxySegment1.ttf = segmentOverride['transit_time_func'](proxySegment1.ttf, proxySegment2.ttf)
    else:
        proxySegment1.ttf = max(proxySegment1.ttf, proxySegment2.ttf)
        
    if 'dwell_time' in segmentOverride:
        proxySegment1.dwellTime = segmentOverride['dwell_time'](proxySegment1.dwellTime, proxySegment2.dwellTime)
    else:
        proxySegment1.dwellTime += proxySegment2.dwellTime
    
    if 'factor_dwell_time_by_length' in segmentOverride:
        proxySegment1.factorFlag = segmentOverride['factor_dwell_time_by_length'](proxySegment1.factorFlag, proxySegment2.factorFlag)
    else:
        proxySegment1.factorFlag = proxySegment1.factorFlag and proxySegment2.factorFlag
    
    if 'data1' in segmentOverride:
        proxySegment1.data1 = segmentOverride['data1'](proxySegment1.data1, proxySegment2.data1)
    else:
        proxySegment1.data1 = (proxySegment1.data1 + proxySegment2.data1) * 0.5
    
    if 'data2' in segmentOverride:
        proxySegment1.data2 = segmentOverride['data2'](proxySegment1.data2, proxySegment2.data2)
    else:
        proxySegment1.data2 = (proxySegment1.data2 + proxySegment2.data2) * 0.5
    
    if 'data3' in segmentOverride:
        proxySegment1.data3 = segmentOverride['data3'](proxySegment1.data3, proxySegment2.data3)
    else:
        proxySegment1.data3 = (proxySegment1.data3 + proxySegment2.data3) * 0.5
    
    for att in proxySegment1.exatts.iterkeys():
        if att in segmentOverride:
            proxySegment1.exatts[att] = segmentOverride[att](proxySegment1.exatts[att], proxySegment2.exatts[att])
        else:
            try:
                proxySegment1.exatts[att] = (proxySegment1.exatts[att] + proxySegment2.exatts[att]) * 0.5
            except Exception, e:
                pass

#-------------------------------------------------------------------------------------------

class TransitLineProxy():
    '''
    Data container for copying transit line data. For easy line itinerary modification,
    the line's segments are stored in a simple list made up of TransitSegmentProxy
    objects. This class's copyToNetwork method can then be used to 'save' the changes
    to the network. If errors are encountered, this class will safely roll back all
    saved changes.
    '''
    
    DEFAULT_ATTS = set(['description', 'layover_time', 'speed', 'headway', 'data1', 'data2', 'data3'])
    
    def __init__(self, line):
        self.id = line.id
        self.vehicle = line.vehicle.number
        self.description = line.description
        self.headway = line.headway
        self.speed = line.speed
        self.layover = line.layover_time
        self.data1 = line.data1
        self.data2 = line.data2
        self.data3 = line.data3
        
        self.exatts = {}
        for attId in line.network.attributes('TRANSIT_LINE'):
            if not attId in self.DEFAULT_ATTS:
                self.exatts[attId] = line[attId]
        
        self.segments = [TransitSegmentProxy(segment) for segment in line.segments(True)]
    
    def copyToNetwork(self, network):
        itinerary = [segment.iNode.number for segment in self.segments]
        
        copy = network.create_transit_line(self.id, self.vehicle, itinerary)
        copy.description = self.description
        copy.headway = self.headway
        copy.speed = self.speed
        copy.layover_time = self.layover
        copy.data1 = self.data1
        copy.data2 = self.data2
        copy.data3 = self.data3
        
        for key, val in self.exatts.iteritems():
            copy[key] = val
        
        try:
            for i, segment in enumerate(copy.segments(True)):
                self.segments[i].copyToSegment(segment)
        except Exception, e:
            network.delete_transit_line(self.id)
            raise
        
        return copy

class TransitSegmentProxy():
    '''
    Data container for copying & modifying transit segment data
    '''
    
    DEFAULT_ATTS = set(['allow_boardings', 'allow_alightings', 'transit_time', 'dwell_time',
                        'transit_volume', 'transit_boardings', 'factor_dwell_time_by_length',
                        'transit_time_func', 'data1', 'data2', 'data3'])
    
    def __init__(self, segment, iNode=None):
        '''
        By default, a new segment takes the iNode of the segment to copy,
        but this can be set manually for transit line itinerary modifications.
        '''
        self.iNode = segment.i_node
        if iNode != None:
            self.iNode = iNode
            
        self.allowBoardings = segment.allow_boardings
        self.allowAlightings = segment.allow_alightings
        self.dwellTime = segment.dwell_time
        self.ttf = segment.transit_time_func
        self.factorFlag = segment.factor_dwell_time_by_length
        self.data1 = segment.data1
        self.data2 = segment.data2
        self.data3 = segment.data3
        
        self.exatts = {}
        for attId in segment.network.attributes('TRANSIT_SEGMENT'):
            if not attId in self.DEFAULT_ATTS:
                self.exatts[attId] = segment[attId]
    
    def copyToSegment(self, segment):
        segment.allow_boardings = self.allowBoardings
        segment.allow_alightings = self.allowAlightings
        segment.dwell_time = self.dwellTime
        segment.transit_time_func = self.ttf
        segment.factor_dwell_time_by_length = self.factorFlag
        segment.data1 = self.data1
        segment.data2 = self.data2
        segment.data3 = self.data3
        
        for key, val in self.exatts.iteritems():
            segment[key] = val
        

############################################################################################

class _DestinationLink():
    def __init__(self, jNode):
        self.pendingCost = float('inf')
        self.previousLink = None
        self.degree = -1
        self.j_node = jNode
        self.isQueued = False

class _ModeFilter():
    def __init__(self, mode):
        self.__mode = mode
    
    def __call__(self, link):
        return self.__mode in link.modes

class AStarLinks():
    '''
    Implementation of the A-Star (A*) shortest-path algorithm, using links
    to store pending costs. This is a SLOW implementation because I don't
    have access to a good priority queue implementation, which means the 
    list of pending links needs to be sorted every time. This algorithm
    is intended for short requests (under 50 links), which can be controlled
    through the 'max_degrees' property of this class. This algorithm
    includes turning penalties (& restrictions).
    
    USAGE:
    - Instantiate this class: algo = AStarLinks(...). The constructor takes
        the following arguments:
         - network: A valid Emme Network object
         - link_speed_func (optional): A Python function which takes a link
                     object and returns that link's speed. The default function
                     returns UL2.
         - link_penalty_func (optional(: A Python function which takes a link 
                     object and returns an additive penalty (e.g., toll cost)
                     based on that link. The default function return 0.0
         - link_speed_unit (optional): A factor to convert units between the link
                     time & the link penalty. 1.0 is the default
         - turn_penalty_func (optional): A Python function which takes a turn object
                     argument and returns an additive penalty. The default
                     function returns 0.0
                     
    - To make a routing request, call algo.calcPath(...). This method takes
        the following arguments:
         - start: An Emme node object to start from.
         - end: An Emme node object to end at.
         - mode (optional): An Emme mode object to filter links (see note
                     on link_filter below)
        This function returns a list of links making up the shortest path
        between the start and end nodes. If no valid path is found, this
        function returns an empty list [].
        
    - Three additional class properties are available:
        - max_degrees: The (integer) maximum number of 'jumps' this algorithm
                will explore before returning the null path. The corollary
                to this is that this algorithm cannot find paths longer
                than this property.
        - link_filter: A Python function which takes in a link object and
                returns a Boolean indicating if the link is valid. If the
                option keyword argument 'mode' is specified during the
                routing request, this property gets changed to a function
                which filters links by mode.
        - coord_factor: Factor to convert coordinate units into link length
                units. By default, the coordinate factor from Modeller's
                emmebank is used. This can be overwritten for cross-database
                manipulations.
    
    - This class is also a context manager (e.g., can be used in a 'with'
        statement). This is done because the algorithm creates several
        extra network attributes which cannot be published to a scenario.
        Using the 'with' statement clears the network of these temporary
        attributes; returning the network to a publishable state.
    
    - The equations used to calculate link & turn costs are as follows:
        link_cost(link) = link.length / speed(link) * link_speed_unit 
                            + link_penalty_func(link)
        
        turn_cost(turn) = turn_penalty_func(turn)
        
        heuristic(node) = dist(node, end) / max(speed(link)) 
    '''
    
    
    __attribute_defaults = [('LINK', 'pendingCost', float('inf')),
                          ('NODE', 'estimate', None),
                          ('LINK', 'previousLink', None),
                          ('LINK', 'degree', -1),
                          ('NODE', 'isClosed', False),
                          ('LINK', 'isQueued', False),
                          ('LINK', 'isEgressLink', False)]
    
    def __init__(self, network,
                 link_speed_unit=1.0, 
                 link_speed_func=None,
                 link_penalty_func=None,
                 turn_penalty_func=None):
        
        #Private variables
        self.__speedFactor = link_speed_unit
        
        self.__getLinkSpeed = link_speed_func
        if link_speed_func == None:
            self.__getLinkSpeed = self.__speedInUl2
        
        self.__calcTurnCost = turn_penalty_func
        if turn_penalty_func == None:
            self.__calcTurnCost = self.__zeroTurnPenalty
        
        self.__calcLinkPenalty = link_penalty_func
        if link_penalty_func == None:
            self.__calcLinkPenalty = self.__zeroLinkPenalty
        
        self.__network = network
        self.__maxSpeed = 0.0
        self.__debug = False
        
        #Public variables
        self.coord_factor = _MODELLER.emmebank.coord_unit_length
        self.max_degrees = 20
        self.link_filter = self.__nullFilter
        
        for domain, att, val in self.__attribute_defaults:
            self.__network.create_attribute(domain, att, val)        
    
    def calcPath(self, start, end, mode=None, reset_max_speed=True, prior_link=None):
        
        if start.network != self.__network:
            raise Exception("Start node does not belong to prepared network or is not a node")
        if end.network != self.__network:
            raise Exception("End node does not belong to prepared network or is not a node")
        
        #---Init
        if mode:
            self.link_filter = _ModeFilter(mode)
        self.__resetNetwork()
        if reset_max_speed or not self.__maxSpeed:
            self.__calcMaxSpeed()
        self.__end = end
        
        pq = [] #Main priority queue
        
        #---Visit the starting node
        start.isClosed = True
        count = 0
        for link in start.outgoing_links():
            if self.link_filter(link):
                link.degree = 0
                link.pendingCost = 0.0
                pq.append(link)
                link.isQueued = True
                link.j_node.estimate = self.__calcHeuristic(link.j_node)
                count += 1
        if count == 0:
            _warn("Start node has no valid outgoing links")
            return []
        
        #---Flag egress links
        end.estimate = 0.0
        count = 0
        for link in end.incoming_links():
            if self.link_filter(link):
                link.isEgressLink = True
                count += 1
        if count == 0:
            _warn("End node has no valid incoming links")
            return []
        
        destinationLink = _DestinationLink(end)
        
        #---MAIN LOOP
        while len(pq) > 0:
            link = pq.pop()
            if self.__debug:
                print link.j_node
            
            #---Check for completion
            if link == destinationLink:
                return self.__constructPath(destinationLink)
            
            if link.degree > self.max_degrees:
                continue #Link is too many jumps from start
            
            linkCost = self.__calcLinkCost(link)
            if linkCost < 0:
                raise Exception("Cost for link %s was negative" %link)
            
            #---Update subsequent links
            #Link is connected to the end-node
            #(This needs special handling because we don't have control over outgoing links)
            if link.isEgressLink: 
                updatedCost = link.pendingCost + linkCost
                if updatedCost < destinationLink.pendingCost:
                    destinationLink.pendingCost = updatedCost
                    destinationLink.previousLink = link
                    destinationLink.degree = link.degree + 1
                    if not destinationLink.isQueued:
                        pq.append(destinationLink)
                        destinationLink.isQueued = True    
            #Link is part of a turn
            elif link.j_node.is_intersection:
                for turn in link.outgoing_turns():
                    if turn.penalty_func == 0: continue #Skip prohibited turns
                    toLink = turn.to_link
                    if not self.link_filter(toLink): continue #Skip invalid links
                    
                    turnCost = self.__calcTurnCost(turn)
                    updatedCost = link.pendingCost + linkCost + turnCost
                    if updatedCost < toLink.pendingCost:
                        toLink.pendingCost = updatedCost
                        toLink.previousLink = link
                        toLink.degree = link.degree + 1
                        if not toLink.isQueued: #Only add to queue if not already in queue.
                            pq.append(toLink)
                            toLink.isQueued = True
                            toLink.j_node.estimate = self.__calcHeuristic(toLink.j_node)
            #Regular link
            else:
                for toLink in link.j_node.outgoing_links():
                    if toLink.j_node.isClosed: continue #Skip closed nodes
                    if toLink.j_node.is_intersection and toLink.j_node == link.i_node:
                        continue #Skip u-turns connected to an intersection nodes (which don't get closed)
                    if not self.link_filter(toLink): continue #Skip invalid links
                    
                    updatedCost = link.pendingCost + linkCost
                    if updatedCost < toLink.pendingCost:
                        toLink.pendingCost = updatedCost
                        toLink.previousLink = link
                        toLink.degree = link.degree + 1
                        if not toLink.isQueued:
                            pq.append(toLink)
                            toLink.isQueued = True
                            toLink.j_node.estimate = self.__calcHeuristic(toLink.j_node)
                link.j_node.isClosed = True #Only close nodes which are not intersections
            
            pq.sort(cmp=self.__comparator, reverse=True)
        return [] #Priority queue is empty, shortest-path not found     
    
    ##############################################################
    #---HELPER METHODS        
            
    def __calcLinkCost(self, link):
        speed = self.__getLinkSpeed(link) * self.__speedFactor
        
        if speed <= 0:
            return float('inf')
        
        return link.length / speed + self.__calcLinkPenalty(link)
    
    def __constructPath(self, destinationLink):
        if destinationLink.pendingCost == float('inf'):
            return [] #Start & end nodes are connected but path cost is infeasible
        
        path = []
        prevLink = destinationLink.previousLink
        while prevLink != None:
            path.append(prevLink)
            prevLink = prevLink.previousLink
        path.reverse()
        return path
    
    def __calcMaxSpeed(self):
        self.__maxSpeed = 0.0
        count = 0
        for link in self.__network.links():
            if not self.link_filter(link):
                continue
            speed = self.__getLinkSpeed(link) * self.__speedFactor
            if speed > self.__maxSpeed:
                self.__maxSpeed = speed
            count += 1
        if count == 0:
            _warn("Filter function returns no valid links")
    
    def __comparator(self, a, b):    
        aj = a.j_node
        bj = b.j_node
            
        estimate_a = a.pendingCost + aj.estimate
        estimate_b = b.pendingCost + bj.estimate
        if estimate_a > estimate_b:
            return 1
        if estimate_a < estimate_b:
            return -1
        if estimate_a == estimate_b:
            return 0
    
    def __calcHeuristic(self, node):
        end = self.__end
        dist = _math.sqrt((node.x - end.x)*(node.x - end.x) + (node.y - end.y)*(node.y - end.y)) * self.coord_factor
        return dist / self.__maxSpeed
    
    def __resetNetwork(self):
        for domain, att, val in self.__attribute_defaults:
            self.__network.delete_attribute(domain, att)
            self.__network.create_attribute(domain, att, val)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args, **kwargs):
        for domain, att, val in self.__attribute_defaults:
            self.__network.delete_attribute(domain, att)
    
    #####################################################
    #---DEFAULT LAMBDAS
        
    def __speedInUl2(self, link):
        return link.data2
    
    def __zeroTurnPenalty(self, turn):
        return 0.0
    
    def __nullFilter(self, link):
        return True
    
    def __zeroLinkPenalty(self, link):
        return 0.0

###############################################################################################


    