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

from inro.emme.network import Network
import inro.modeller as _m
import math as _math
from warnings import warn as _warn
import traceback as _traceback
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_geolib = _MODELLER.module('tmg.common.geometry')
COORD_FACTOR = _MODELLER.emmebank.coord_unit_length
EMME_VERSION = _util.getEmmeVersion(tuple) 


class Face(_m.Tool()):
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Network Utilities", branding_text="- TMG Toolbox",
                                description="Collection of small functions (including \
                                a shortest-path calculator) for network editing")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        return pb.render()

#===========================================================================================
#---Exceptions

class ForceError(Exception):
    '''
    Thrown when user forces an error to be raised
    '''
    pass

class InvalidNetworkOperationError(Exception):
    '''
    Thrown when an invalid network operation is attempted.
    '''
    pass

#===========================================================================================

def calcShapeLength(link, coordFactor= COORD_FACTOR):
    '''
    Calculates the shape length of a link (i.e., including
    shape vertices). Applies the coordinate factor of the
    current emmebank, unless otherwise specified.
    
    Args:
        - link: An Emme Link object
        - coordFactor (=COORD_FACTOR): A factor applied
                to the returned length. By default set to
                the coordinate factor of the current 
                emmebank.
    '''
    shapeLength = 0
    i = link.i_node
    j = link.j_node
    points = [(i.x, i.y)] + link.vertices + [(j.x, j.y)]
    
    for p1, p2 in _util.iterpairs(points):
        x1, y1 = p1
        x2, y2 = p2
        dx = x2-x1
        dy = y2-y1
        shapeLength += _math.sqrt(dx*dx + dy*dy)
    return shapeLength * coordFactor

#===========================================================================================

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
                a = prevVolume + float(segment.transit_boardings) - float(segment.transit_volume)
                if a < 0: a = 0.0 #Alightings can be negative due to rounding error
                segment.transit_alightings = a
            prevVolume = float(segment.transit_volume) 

#===========================================================================================

def isLinkParallel(link):
    '''
    Tests if a link is parallel with its reverse, based on vertices.
    
    Args:
        - link: The link to test
        
    Returns: True if link's reverse exists and is parallel, False otherwise.
    '''
    
    reverse = link.reverse_link
    if reverse is None:
        return False
    revertices = [vtx for vtx in reverse.vertices]
    revertices.reverse()
    
    return revertices == link.vertices

#===========================================================================================

TEMP_LINE_ID = '999999'

def splitLink(newNodes, link, twoWay=True, onLink=True, coordFactor= COORD_FACTOR, stopOnNewNodes=False):
    '''
    Splits a link at a given node (or nodes). Uses geometry to determine which vertices
    get assigned to which subsequently-created new link (and in what order).
    
    Args:
        - newNodes: A new node (or iterable of nodes) to be inserted into the link
        - twoWay (=True): bool flag whether to also split the reverse link
        - onLink (=True): bool flag whether the new nodes should be adjusted to occur on 
                the link (if they do not project onto the link).
        - coordFactor: Conversion between coordinate unit and link length. By
                default, the coordinate factor of the Emme Project is used.
        - stopOnNewNodes (=False): flag to indicate if the new nodes should be used as 
                transit stops.
    
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
            
            if link.reverse_link is not None and twoWay:
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
        if link.reverse_link is not None and twoWay:
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
            
        if link.reverse_link is not None and twoWay:
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
    
    #All new links are created. Copy the turn attributes
    turnAtts = [att for att in network.attributes('TURN')]
    firstForwardLink = newLinksF[0]
    for turn in link.incoming_turns():
        newTurn = network.turn(turn.i_node.number, turn.j_node.number, firstForwardLink.j_node.number)
        for att in turnAtts: newTurn[att] = turn[att]
    lastForwardLink = newLinksF[-1]
    for turn in link.outgoing_turns():
        newTurn = network.turn(lastForwardLink.i_node.number, turn.j_node.number, turn.k_node.number)
        for att in turnAtts: newTurn[att] = turn[att]
    if link.reverse_link is not None and twoWay:
        firstRevrseLink = newLinksR[0]
        for turn in link.reverse_link.incoming_turns():
            newTurn = network.turn(turn.i_node.number, turn.j_node.number, firstRevrseLink.j_node.number)
            for att in turnAtts: newTurn[att] = turn[att]
        lastReverseLink = newLinksR[-1]
        for turn in link.reverse_link.outgoing_turns():
            newTurn = network.turn(lastReverseLink.i_node.number, turn.j_node.number, turn.k_node.number)
            for att in turnAtts: newTurn[att] = turn[att]
            
    #Delete the original links
    if link.reverse_link is not None:
        network.delete_link(link.j_node.number, link.i_node.number)
    network.delete_link(link.i_node.number, link.j_node.number)
    
    return newLinksF + newLinksR

#===========================================================================================

def addReverseLink(link):
    '''
    For a link without a reverse, this function creates a 
    parallel (e.g. vertices copied) reverse link.
    
    Args:
        - link= The link to copy
    
    Returns: The reverse link (whether it's new or not).
    '''
    if link.reverse_link is not None:
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

#===========================================================================================

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
    
    #This will crash before deleting the old transit line to preserve the
    #network state
    newLine = proxy.copyToNetwork(network) 
    
    network.delete_transit_line(line.id)
    
    return newLine

#===========================================================================================

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
    
    if net.transit_vehicle(newId) is not None:
        raise InvalidNetworkOperationError("Cannot change transit vehicle %s to %s as this ID already exists in the scenario" %(oldVehicle, newId))
    
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

#===========================================================================================

def lineConcatenator(network, lineSet, newId):

    if len(lineSet) <= 1:
        raise Exception("Need at least two lines")
    
    lines = []
    for lineId in lineSet:
        lines.append(network.transit_line(lineId))
    itineraries = []
    for line in lines:
        itineraries.append([node.number for node in line.itinerary()])
    
    #Check if end points match and combine itineraries
    combinedItinerary = itineraries[0]
    for num, item in enumerate(itineraries):
        if num == (len(itineraries) - 1):
            combinedItinerary += item[1:]
            break #don't test the final line
        
        nextItem = itineraries[num + 1]

        if item[-1] != nextItem[0]: #compare final stop of current line to first stop of next line
            raise Exception("Lines don't connect!")
        elif num == 0: #don't need to add the first line's itinerary
            continue
        else:
            combinedItinerary += item[1:] #combine stop lists, removing the redundant start node
                      
    attNames = network.attributes('TRANSIT_SEGMENT')
    lineAttNames = network.attributes('TRANSIT_LINE') 
    #Grabbing segment attributes. 
    combinedSegmentAttributes = []
    for line in lines:
        segmentAttributes = []
        for segment in line.segments(False):
            d = {}
            for attName in attNames:
                d[attName] = segment[attName]
            segmentAttributes.append(d) 
        combinedSegmentAttributes += segmentAttributes  

    #Allow the recreated line to take on the attributes of the first line in the list
    newVehicleId = lines[0].vehicle.id
    lineAttributes = {}
    for attName in lineAttNames:
        lineAttributes[attName] = lines[0][attName]
                
    newLine = network.create_transit_line(newId, newVehicleId, combinedItinerary)
        
    for num, segment in enumerate(newLine.segments(False)):
        d = combinedSegmentAttributes[num] 
        for attName, value in d.iteritems():
            segment[attName] = value
        
    for attName, value in lineAttributes.iteritems():
        newLine[attName] = value

#===========================================================================================

def copyNetwork(network_to_copy):
    '''
    Makes a deep copy of a Network object
    '''

    new_network = Network()

    #1. Copy all the attributes across
    element_types = ['MODE', 'TRANSIT_VEHICLE', 'NODE', 'LINK', 'TURN', 'TRANSIT_LINE', 'TRANSIT_SEGMENT']
    for etype in element_types:
        standard_atts = set(new_network.attributes(etype))
        new_atts = set(network_to_copy.attributes(etype))

        for attname in (new_atts - standard_atts): new_network.create_attribute(etype, attname)

    #2. Copy the modes
    for mode_to_copy in network_to_copy.modes():
        new_mode = new_network.create_mode(mode_to_copy.type, mode_to_copy.id)
        for attname in new_network.attributes('MODE'): new_mode[attname] = mode_to_copy[attname]

    #3. Copy the transit vehicles
    for vehicle_to_copy in network_to_copy.transit_vehicles():
        new_vehicle = new_network.create_transit_vehicle(vehicle_to_copy.id, vehicle_to_copy.mode.id)
        for attname in new_network.attributes('TRANSIT_VEHICLE'): new_vehicle[attname] = vehicle_to_copy[attname]

    #4. Copy the nodes
    for node_to_copy in network_to_copy.nodes():
        new_node = new_network.create_node(node_to_copy.id, node_to_copy.is_centroid)
        for attname in new_network.attributes('NODE'): new_node[attname] = node_to_copy[attname]

    #5. Copy the links
    for link_to_copy in network_to_copy.links():
        modes = [mode.id for mode in link_to_copy.modes]
        new_link = new_network.create_link(link_to_copy.i_node.id, link_to_copy.j_node.id, modes)
        for attname in new_network.attributes('LINK'): new_link[attname] = link_to_copy[attname]
        new_link.vertices = [vtx for vtx in link_to_copy.vertices] #Copy the link vertices properly

    #6. Copy the turns
    for intersection_to_copy in network_to_copy.intersections(): new_network.create_intersection(intersection_to_copy.id)
    for turn_to_copy in network_to_copy.turns():
        new_turn = new_network.turn(turn_to_copy.i_node.id, turn_to_copy.j_node.id, turn_to_copy.k_node.id)
        for attname in new_network.attributes('TURN'): new_turn[attname] = turn_to_copy[attname]

    #7. Copy the transit lines and segments
    for transit_line_to_copy in network_to_copy.transit_lines():
        itinerary = [node.number for node in transit_line_to_copy.itinerary()]
        new_transit_line = new_network.create_transit_line(transit_line_to_copy.id,
                                                           transit_line_to_copy.vehicle.id,
                                                           itinerary)
        for attname in new_network.attributes('TRANSIT_LINE'): new_transit_line[attname] = transit_line_to_copy[attname]

        for segment_to_copy, new_segment in _util.itersync(transit_line_to_copy.segments(True), new_transit_line.segments(True)):
            for attname in new_network.attributes('TRANSIT_SEGMENT'): new_segment[attname] = segment_to_copy[attname]

    return new_network

#===========================================================================================

#===========================================================================================

#---
#---LINK MERGING

__AVG = lambda attName, item1, item2: (item1[attName] + item2[attName]) * 0.5
__FIRST = lambda attName, item1, item2: item1[attName]
__LAST = lambda attName, item1, item2: item2[attName]
__MIN = lambda attName, item1, item2: min(item1[attName], item2[attName])
__MAX = lambda attName, item1, item2: max(item1[attName], item2[attName])
__SUM = lambda attName, item1, item2: item1[attName] + item2[attName]
__ZERO = lambda attName, item1, item2: 0.0
__AND = lambda attName, item1, item2: item1[attName] and item2[attName]
__OR = lambda attName, item1, item2: item1[attName] or item2[attName]

def __FORCE(attName, item1, item2):
    if item1[attName] != item2[attName]:
        raise ForceError(attName)
    return item1[attName]

NAMED_AGGREGATORS = {'sum': __SUM,
                     'avg': __AVG,
                     'first': __FIRST,
                     'last': __LAST,
                     'min': __MIN,
                     'max': __MAX,
                     'zero': __ZERO,
                     'and': __AND,
                     'or': __OR,
                     'force': __FORCE}

__LINK_ATTRIBUTE_AGGREGATORS = {'vertices': __SUM,
                                'length': __SUM,
                                'num_lanes': __MAX,
                                'type': __MIN,
                                'volume_delay_func': __FORCE}

__SEGMENT_ATTRIBUTE_AGGREGATORS = {'dwell_time': __SUM,
                                   'transit_time_func': __FORCE,
                                   'factor_dwell_time_by_length': __OR,
                                   'allow_alightings': __FIRST,
                                   'allow_boardings': __FIRST}

__ATTRIBUTE_CASTS = {'num_lanes': int,
                     'type': int,
                     'volume_delay_func': int,
                     'factor_dwell_time_by_length': bool,
                     'transit_time_func': int,
                     'vertices': lambda v: v, #Do not cast the vertices
                     'allow_alightings': bool,
                     'allow_boardings': bool} 

def mergeLinks(node, deleteStop= False, vertex= True, linkAggregators= {}, segmentAggregators= {}):
    '''
    Deletes a node and merges its links. This only works for nodes connected to exactly
    2 other nodes with either two or four links. The node can be a transit stop but cannot
    be the first or last stop in a transit line's itinerary.
    
    Args:
        - node: The Emme node object to remove.
        - deleteStop (=False): Flag to remove incident stops (or not). If False, this
                function will raise an error if any transit line stops at the given node.
        - vertex (=True): Flag to insert the deleted node as a vertex in the merged link(s).
        - linkAggregators (={}): A dictionary. The keys are the names of link standard
                or extra attributes, the values are aggregator functions (see
                static dictionary 'NAMED_AGGREGATORS').If not specified, the default 
                aggregators will be used:
                    SUM for length
                    MIN for type
                    FORCE for VDF
                    MAX for lanes
                    AVG for everything else
        - segmentAggregators (={}): Similar to linkAggregators, but applied to segment
                attributes. If not specified, the default aggregators will be used:
                    SUM for dwell time
                    FORCE for TTF
                    OR for factor dwell time by length flag
                    AVG for everything else
        
    Note about creating custom aggregator functions: The expected signature for aggregator
    functions is: 
        (attribute_name, item1, item2)
    where item1 and item2 are either Link or Transit Segment objects, and attribute_name is
    the string name of one of the network attributes.
    
    
    Returns:
        A list of created links.
    '''
    
    #TODO: Setup override for attribute casts for nonstandard, attributes that do not start with '@'
    
    network = node.network
    
    incomingLinks, outgoingLinks, lineQueue = _preProcessNodeForMerging(node, deleteStop)
    
    pairsToMerge = _getLinkPairs(incomingLinks, outgoingLinks)
    
    #Setup the aggregator functions. 
    for key, val in __LINK_ATTRIBUTE_AGGREGATORS.iteritems():
        if not key in linkAggregators: linkAggregators[key] = val
    
    for key, val in __SEGMENT_ATTRIBUTE_AGGREGATORS.iteritems():
        if not key in segmentAggregators: segmentAggregators[key] = val
    
    createdLinks = []
    lineRenamingMap = []
    try:
        #Merge the links first
        for link1, link2 in pairsToMerge:
            newLink = _mergeLinkPair(network, link1, link2, linkAggregators, createdLinks)
            
            #Optionally insert the deleted node as a vertex in the merged link
            if vertex == True:
                verticesList = newLink.vertices
                verticesList1 = link1.vertices
                verticesList.insert(len(verticesList1), (node.x, node.y))
                newLink.vertices = verticesList
                    #newLink.vertices.insert(len(link1.vertices), (node.x, node.y))
        
        for line, segmentNumbersToRemove in lineQueue.iteritems():
            _mergeLineSegments(network, line, segmentNumbersToRemove, segmentAggregators, lineRenamingMap)
            
    except:
        for i, j in [(link.i_node.number, link.j_node.number) for link in createdLinks]:
            network.delete_link(i, j, cascade= True) 
            #Do not need to delete any created transit lines, since the cascade delete takes care
            #of that. This SHOULD also remove the original transit lines
        raise
    
    #Delete the actual node
    network.delete_node(node.id, cascade= True)
    
    #Revert the original transit line IDs
    for line, originalId in lineRenamingMap:
        changeTransitLineId(line, originalId)
    
    return createdLinks
    
def _preProcessNodeForMerging(node, deleteStop):
    neighbourSet = set()
    nIncomingLinks = 0
    nOutgoingLinks = 0
    
    incomingLinks = []
    outgoingLinks = []
    lineQueue = {}
    
    for link in node.incoming_links():
        neighbourSet.add(link.i_node.number)
        nIncomingLinks += 1
        incomingLinks.append(link)
        
        #Check for invalid transit topologies
        for segment in link.segments():
            if segment.line.segment(-2).number == segment.number:
                raise InvalidNetworkOperationError("Cannot delete node %s: it is the final stop of transit line %s." %(node, segment.line))
            else:
                nextSegment = segment.line.segment(segment.number + 1)
                if nextSegment.link.reverse_link == link:
                    raise InvalidNetworkOperationError("Cannot delete node %s: It is used as a u-turn point for transit line %s." %(node, segment.line))
                
    for link in node.outgoing_links():
        neighbourSet.add(link.j_node.number)
        nOutgoingLinks += 1
        outgoingLinks.append(link)
        
        #Check for invalid transit topologies
        for segment in link.segments():
            if segment.number == 0:
                raise InvalidNetworkOperationError("Cannot delete node %s: it is the first stop of transit line %s." %(node, segment.line))
            if not deleteStop:
                if segment.allow_alightings or segment.allow_boardings:
                    raise InvalidNetworkOperationError("Cannot delete node%s: it is being used as a transit stop for line %s" %(node, segment.line))
            
            if segment.line in lineQueue:
                lineQueue[segment.line].append(segment.number)
            else:
                lineQueue[segment.line] = [segment.number]
    
    if len(neighbourSet) != 2:
        raise InvalidNetworkOperationError("Cannot delete node %s: can only merge nodes with a degree of 2." %node)
    
    if nIncomingLinks != nOutgoingLinks:
        raise InvalidNetworkOperationError("Cannot delete node %s: can only delete nodes with the same number of incoming and outgoing links." %node)
    
    return incomingLinks, outgoingLinks, lineQueue
    
def _getLinkPairs(incomingLinks, outgoingLinks):
    #Get the link pair(s) to merge
    if len(incomingLinks) == 1:
        return [(incomingLinks[0], outgoingLinks[0])]
    elif len(incomingLinks) == 2:
        pair1 = (incomingLinks[0], incomingLinks[1].reverse_link)
        pair2 = (incomingLinks[1], incomingLinks[0].reverse_link)
        return [pair1, pair2]

def _getTempLineId(network):
    n = 1
    tl = network.transit_line(n)
    while tl is not None:
        n += 1
        tl = network.transit_line(n)
    return str(n) 

def _mergeLinkPair(network, link1, link2, linkAggregators, createdLinks):
    #Check if the merged link already exists
    if network.link(link1.i_node.number, link2.j_node.number) is not None:
        raise InvalidNetworkOperationError("Merged link %s-%s already exists!" %(link1.i_node.number, link2.j_node.number))
    
    newModes = link1.modes | link2.modes #Always permit the union of the set of modes
    newLink = network.create_link(link1.i_node.number, link2.j_node.number, newModes)
    createdLinks.append(newLink)
    
    #Aggregate link attributes
    for attName in network.attributes('LINK'):
        if not attName in linkAggregators:
            func = __AVG
        else:
            func = linkAggregators[attName]
        
        if attName in __ATTRIBUTE_CASTS:
            cast = __ATTRIBUTE_CASTS[attName]
        else:
            cast = float
        
        newVal = func(attName, link1, link2)
        newLink[attName] = cast(newVal)

    #create link vertices
    vertices_list_link1 = link1.vertices
    vertices_list_link2 = link2.vertices
    vertices_list_newLink = []
    for vertex in vertices_list_link1:
        vertices_list_newLink.append(vertex)
    for vertex in vertices_list_link2:
        vertices_list_newLink.append(vertex)
    newLink.vertices = vertices_list_newLink
    return newLink

def _mergeLineSegments(network, line, segmentNumbersToRemove, segmentAggregators, lineRenamingMap):
    
    proxy = TransitLineProxy(line)
    
    #Go through backwards from the highest-numbered segment (99% of the time
    #only one segent will be remove from a line at a given time. This is
    #just to catch looped lines).
    segmentNumbersToRemove.sort(reverse= True)
    for index2 in segmentNumbersToRemove:
        baseSegment1 = line.segment(index2 - 1)
        baseSegment2 = line.segment(index2)
        
        proxy.segments.pop(index2)
        proxySegment = proxy.segments[index2 - 1]
        
        for attName in network.attributes('TRANSIT_SEGMENT'):
            if not attName in segmentAggregators:
                func = __AVG
            else:
                func = segmentAggregators[attName]
            
            if attName in __ATTRIBUTE_CASTS:
                cast = __ATTRIBUTE_CASTS[attName]
            else:
                cast = float
            
            newVal = func(attName, baseSegment1, baseSegment2)
            proxySegment[attName] = cast(newVal)
    
    #Need a temporary ID to allow the two lines to exist at the same time on the network.
    #This way, if an error occurs, only the modified copies will get deleted.
    proxy.id = _getTempLineId(network)
    copy = proxy.copyToNetwork(network)
    lineRenamingMap.append((copy, line.id))
    
#===========================================================================================

#---
#---PROXY CLASSES

class TransitLineProxy():
    '''
    Data container for copying transit line data. For easy line itinerary modification,
    the line's segments are stored in a simple list made up of TransitSegmentProxy
    objects. This class's copyToNetwork method can then be used to 'save' the changes
    to the network. If errors are encountered, this class will safely roll back all
    saved changes.
    '''
    
    DEFAULT_ATTS = set(['description', 'layover_time', 'speed', 'headway', 'data1', 'data2', 'data3'])
    
    __MAP = {'layover_time': 'layover'}
    
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
    
    def __getitem__(self, key):
        if type(key) != str and type(key) != unicode: raise TypeError("Attribute must be a string")
        
        if key in self.__MAP: key = self.__MAP[key]
        if key in self.exatts:
            return self.exatts[key]
        return self.__dict__[key]
    
    def __setitem__(self, key, value):
        if type(key) != str and type(key) != unicode: raise TypeError("Attribute must be a string")
        
        if key in self.__MAP: key = self.__MAP[key]
        if key in self.exatts:
            self.exatts = value
        else:
            self.__dict__[key] = value        
    
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
        except:
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
    
    __MAP = {'allow_boardings': 'allowBoardings',
             'allow_alightings':'allowAlightings',
             'dwell_time':'dwellTime',
             'transit_time_func':'ttf',
             'factor_dwell_time_by_length':'factorFlag'}
    
    def __init__(self, segment, iNode=None):
        '''
        By default, a new segment takes the iNode of the segment to copy,
        but this can be set manually for transit line itinerary modifications.
        '''
        self.iNode = segment.i_node
        if iNode is not None:
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
        for attId in segment.line.mode.network.attributes('TRANSIT_SEGMENT'):
            if not attId in self.DEFAULT_ATTS:
                self.exatts[attId] = segment[attId]
    
    def __getitem__(self, key):
        if type(key) != str and type(key) != unicode: raise TypeError("Attribute must be a string")
        
        if key in self.__MAP: key = self.__MAP[key]
        if key in self.exatts:
            return self.exatts[key]
        return self.__dict__[key]
    
    def __setitem__(self, key, value):
        if type(key) != str and type(key) != unicode: raise TypeError("Attribute must be a string")
        
        if key in self.__MAP: key = self.__MAP[key]
        if key in self.exatts:
            self.exatts[key] = value
        else:
            self.__dict__[key] = value 
    
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

#---
#---SHORTEST PATH CALCULATOR

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
        if link_speed_func is None:
            self.__getLinkSpeed = self.__speedInUl2
        
        self.__calcTurnCost = turn_penalty_func
        if turn_penalty_func is None:
            self.__calcTurnCost = self.__zeroTurnPenalty
        
        self.__calcLinkPenalty = link_penalty_func
        if link_penalty_func is None:
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
        while prevLink is not None:
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


    