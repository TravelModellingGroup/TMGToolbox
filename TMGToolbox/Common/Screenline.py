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

'''
SCREENLINE LIBRARY

A library for working with screenline analyses.

@author: pkucirek 

'''

import inro.modeller as _m
import inro.emme as _me
import inro.director as _d
from datetime import datetime as dt
from contextlib import contextmanager
_g = _m.Modeller().module('TMG2.Common.Geometry')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')
_util = _m.Modeller().module('TMG2.Common.Utilities')

class Face(_m.Tool()):
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, runnable=False, title="Screenline",
                                description="Internal object for screenline operations. A screenline \
                                    has an internal geometry (polyline) and knows which links cross it, \
                                    in which direction (positive is right-to-left, negative is left-to-\
                                    right). It can also automatically lookup results from \
                                    an assigned scenario.",
                                branding_text="- TMG Toolbox")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        pb.add_header("STATIC METHODS")
        
        pb.add_method_description("openShp", description="Loads Screenlines from a shapefile. \
                                The shapefile's attribute table must contain fields labelled 'Id', \
                                'Descr', 'PosDirName', and 'NegDirName'.",
                                  args={"shapefileName" : "Filename of the shapefile to be loaded. Do not \
                                      use '\\' as a separator.",
                                      "network=None" : "Optional network argument for allowing screenlines \
                                      to be loaded right away."},
                                  return_string="Dict{id : Screenline object}")
                
        pb.add_header("SCREENLINE CLASS")
        
        pb.add_method_description("__init__", description="Constructor. To set variable 'x' to a new Screenline, \
                                call 'x = Screenline(geom, id, plusName, minusName, name)'",
                                  args={"geom" : "The polyline geometry defining the screenline.",
                                        'id' : 'The id of the screenline.',
                                        'plusName' : 'The name of the positive direction.',
                                        'minusName': 'The name of the negative direction.',
                                         'name': "The screenline's name."},
                                  return_string="Screenline object")
        
        pb.add_method_description("loadLinksFromNetwork", description="Loads or reloads links from the network.",
                                  args={'network' : 'A Network to load links from.',
                                        'initialize=True' : 'Optional. If true, this will clear any stored link ids.',
                                        'ignore_centroids=True' : 'Optional. If true, centroid connectors will be ignored.'})
        
        pb.add_method_description("saveFlaggedLinksToAttribute",
                                  description="Exports screenline internal link flag to a specified link \
                                  extra attribute. Positive links will be flagged a '1', negative links \
                                  will be flagged as '-1'.",
                                  args={'scenario' : 'A Scenario with links to flag.',
                                        'extraAttribute' : "An Extra Attribute to store this screenline's\
                                        internal links into."})
        
        pb.add_method_description("getPositiveVolume",
                                  description="Gets the mode-specific volume for all links crossing this \
                                  screenline in the positive direction.",
                                  args={"network" : "A Network with auto or transit assignment results.",
                                        'mode' : 'A Mode to extract results for.'},
                                  return_string="float")
        
        pb.add_method_description("getNegativeVolume",
                                  description="Gets the mode-specific volume for all links crossing this \
                                  screenline in the negative direction.",
                                  args={"network" : "A Network with auto or transit assignment results.",
                                        'mode' : 'A Mode to extract results for.'},
                                  return_string="float")
        
        return pb.render()

#-------------------------------------------------------------------------------------------------

#Static load method
def openShp(shapefileName, network=None):
    result = {}
    
    with _g.Shapely2ESRI(shapefileName) as reader:
        fields = reader.getFieldNames()
        idKey = 'Id'
        nameKey = 'Descr'
        posNameKey = 'PosDirName'
        negNameKey = 'NegDirName'  
        
        if not idKey in fields:
            raise IOError("Shapefile must have a field labeled '%s'." %idKey)  
        if not nameKey in fields:
            raise IOError("Shapefile must have a field labeled '%s'." %nameKey)
        if not posNameKey in fields:
            raise IOError("Shapefile must have a field labeled '%s'." %posNameKey)
        if not negNameKey in fields:
            raise IOError("Shapefile must have a field labeled '%s'." %negNameKey)
        
        for shape in reader.readThrough():
            sl = Screenline(shape, 
                            shape[idKey], 
                            shape[nameKey],
                            shape[posNameKey],
                            shape[negNameKey])
            
            if network != None:
                sl.loadLinksFromNetwork(network)
            
            result[shape[idKey]] = sl
    
    return result
    
    '''
    shapefile = _g.openShapefileAsGeometry(shapefileName)
    
    result = {}
    idKey = 'Id'
    nameKey = 'Descr'
    posNameKey = 'PosDirName'
    negNameKey = 'NegDirName'
    
    for line in shapefile.itervalues():
        atts = line.Attributes
        id = atts[idKey]
        name = atts[nameKey]
        posName = atts[posNameKey]
        negName = atts[negNameKey]
        
        sl = Screenline(line, id, posName, negName, name)
        
        if network != None:
            sl.loadLinksFromNetwork(network)
        
        result[id] = sl
    
    return result
    '''

def _timedLoadTest(shapefileName, network=None):
    print dt.now()
    for i in range(0,50):
        openShp(shapefileName, network=network)
    print dt.now()

class Screenline():
    
    def __init__(self, geom, id, plusName, minusName, name):
        self.geom = geom
        self.id = id
        self.plusName = plusName
        self.minusName = minusName
        self.name = name
        
        self.plusLinks = set() #Stores links ids
        self.minusLinks = set() #Stores link ids
        
        self.modes = set()
        
        #Static switch for loading volumes
        self._modeSwitch = {'AUTO' : self._getAutoVol,
              'TRANSIT' : self._getTransitVol,
              'AUX_TRANSIT' : self._getAuxTransitVol,
              'AUX_AUTO': self._getAuxAutoVol}
        
    def loadLinksFromNetwork(self, network, initialize=True, ignore_centroids=True):
        '''if type(network) != _me.network.Network:
            raise TypeError("Arg 'network' must be of type 'inro.emme.network.Network', was of tpye %s." %type(network))'''
        
        if initialize: #Clear the internal links
            self.plusLinks.clear()
            self.minusLinks.clear()
        
        #Pythonic switch statement
        switch = {-1: self._addMinusLink,
                  0: self._addParallelLink,
                  1: self._addPlusLink}
        
        for link in network.links():
            if ignore_centroids and (link.i_node.is_centroid or link.j_node.is_centroid):
                continue
            switch[self._checkLink1(link)](link)

        
        '''
        with self._tempDataMANAGER():
            for link in network.links():
                if ignore_centroids and (link.i_node.is_centroid or link.j_node.is_centroid):
                    continue
                switch[self._checkLink2(link)](link)
        '''

    
    def _addPlusLink(self, link):
        self.plusLinks.add(((link.i_node.id, link.j_node.id)))
    
    def _addMinusLink(self, link):
        self.minusLinks.add(((link.i_node.id, link.j_node.id)))
        
    def _addParallelLink(self, link):
        pass
    
    @contextmanager
    def _tempDataMANAGER(self):
        self._segments = []
        pc = None
        for coord in list(self.geom.coords):
            if not pc:
                pc = coord
                continue
            self._segments.append(_g.LineString([pc, coord]))
            pc = coord
        
        self._linkCache = {}
        
        try:
            yield
        finally:
            del self._segments #Dereference
            del self._linkCache
    
    def _checkLink2(self, link):
        #glink = _g.linkToShape(link)
        glink = None
        
        try:
            glink = self._linkCache[link]
        except KeyError, ke:
            glink = _g.linkToShape(link)
            self._linkCache[link] = glink
        
        if not self.geom.intersects(glink):
            return 0
        
        for segment in self._segments:
            if segment.intersects(glink):
                scoords = list(segment.coords)
                lcoords = list(glink.coords)
                cp = _g.crossProduct(scoords[0], scoords[1], lcoords[0], lcoords[1])
                
                if cp < 0: return -1
                elif cp > 0: return 1
                else: return 0
        
        return 0
        
    def _checkLink1(self, link):        
        
        iPoint = (link.i_node.x, link.i_node.y)
        jPoint = (link.j_node.x, link.j_node.y)
        
        '''
        Testing (with Toronto Screenlines, single load)

        WITH BOUNDING BOX CHECK:
        2013-02-19 10:39:07.923000
        2013-02-19 10:39:17.880000
        Delta = ~10 sec
        
        WITHOUT BOUNDING BOX CHECK:
        2013-02-19 10:41:17.004000
        2013-02-19 10:41:37.636000
        Delta = ~20 sec
        '''
        
        #---Check bounding box intersection
        sBox = None
        try:
            sBox = self._g_env
        except AttributeError, e:
            self._g_env = self.geom.bounds
            #self._g_env = self.geom.GetEnvelope()
            sBox = self._g_env
        
        slRangeX = _util.FloatRange(sBox[0], sBox[1])
        slRangeY = _util.FloatRange(sBox[2], sBox[3])
        
        lBox = (min(link.i_node.x, link.j_node.x), max(link.i_node.x, link.j_node.x),
                min(link.i_node.y, link.j_node.y), max(link.i_node.y, link.j_node.y))
        #lBox = _g.getLinkBoundingBox(link)
        
        lkRangeX = _util.FloatRange(lBox[0], lBox[1])
        lkRangeY = _util.FloatRange(lBox[2], lBox[3])
        
        if not (slRangeX.overlaps(lkRangeX) and slRangeY.overlaps(lkRangeY)):
            return 0
        
        '''
        point1 = (lBox[0], lBox[2])
        point2 = (lBox[0], lBox[3])
        point3 = (lBox[1], lBox[2])
        point4 = (lBox[1], lBox[3])
        
        c1 = (point1[0] >= sBox[0] and point1[0] <= sBox[1]) and (point1[1] >= sBox[2] and point1[1] <= sBox[3])
        c2 = (point2[0] >= sBox[0] and point2[0] <= sBox[1]) and (point2[1] >= sBox[2] and point2[1] <= sBox[3])
        c3 = (point3[0] >= sBox[0] and point3[0] <= sBox[1]) and (point3[1] >= sBox[2] and point3[1] <= sBox[3])
        c4 = (point4[0] >= sBox[0] and point4[0] <= sBox[1]) and (point4[1] >= sBox[2] and point4[1] <= sBox[3])
        
        point1 = (sBox[0], sBox[2])
        point2 = (sBox[0], sBox[3])
        point3 = (sBox[1], sBox[2])
        point4 = (sBox[1], sBox[3])
        
        c5 = (point1[0] >= lBox[0] and point1[0] <= lBox[1]) and (point1[1] >= lBox[2] and point1[1] <= lBox[3])
        c6 = (point2[0] >= lBox[0] and point2[0] <= lBox[1]) and (point2[1] >= lBox[2] and point2[1] <= lBox[3])
        c7 = (point3[0] >= lBox[0] and point3[0] <= lBox[1]) and (point3[1] >= lBox[2] and point3[1] <= lBox[3])
        c8 = (point4[0] >= lBox[0] and point4[0] <= lBox[1]) and (point4[1] >= lBox[2] and point4[1] <= lBox[3])
        
        if not (c1 or c2 or c3 or c4 or c5 or c6 or c7 or c8):
            return 0
        '''
        
        #---Check segment intersection
        prevCoord = None
        #prevPoint = self.geom.GetPoint_2D(0)
        for coord in list(self.geom.coords):
            if prevCoord == None:
                prevCoord = coord
                continue
            if _g.checkSegmentIntersection(prevCoord, coord, iPoint, jPoint):
                cp = _g.crossProduct(prevCoord, coord, iPoint, jPoint)
                
                for m in link.modes:
                    self.modes.add(m)
                    
                if cp < 0:
                    return -1
                    #self.minusLinks.add((link.i_node.id, link.j_node.id))
                elif cp > 0:
                    return 1
                    #self.plusLinks.add((link.i_node.id, link.j_node.id))
                else:
                    return 0
                    #pass # Do nothing with links exactly parallel to the screenline
                #return #Once an intersection has been found, kill the loop
            
            
            prevCoord = coord
        
        '''
        for i in range (1, (self.geom.GetPointCount())):
            point = self.geom.GetPoint_2D(i)
            if _g.checkSegmentIntersection(prevPoint, point, iPoint, jPoint):
                cp = _g.crossProduct(prevPoint, point, iPoint, jPoint)
                
                for m in link.modes:
                    self.modes.add(m)
                    
                if cp < 0:
                    return -1
                    #self.minusLinks.add((link.i_node.id, link.j_node.id))
                elif cp > 0:
                    return 1
                    #self.plusLinks.add((link.i_node.id, link.j_node.id))
                else:
                    return 0
                    #pass # Do nothing with links exactly parallel to the screenline
                #return #Once an intersection has been found, kill the loop
            prevPoint = point
        '''
        
        return 0
    
    def saveFlaggedLinksToAttribute(self, network, extraAttribute):        
        if extraAttribute.type != 'LINK':
            raise TypeError("Extra attribute must be a link type!")
        
        for id in self.plusLinks:
            link = network.link(id[0], id[1])
            link[extraAttribute.id] = 1
        
        for id in self.minusLinks:
            link = network.link(id[0], id[1])
            link[extraAttribute.id] = -1
        
        return network
    
    def getPositiveVolume(self, network, mode):
        return self._getVol(network, mode, self.plusLinks)
    
    def getNegativeVolume(self, network, mode):
        return self._getVol(network, mode, self.minusLinks)
    
    #---Internal functions---------------------------------------------------------------
    
    def _getVol(self, network, mode, linkIds):
        '''if type(network) != _me.network.Network:
            raise TypeError("Arg 'network' must be of type 'inro.emme.network.Network', was of type %s" %type(network))
        if not isinstance(mode, _me.network.mode.Mode):
            raise TypeError("Arg 'mode' must be of type 'inro.emme.network.mode.Mode', was of type %s." %type(mode))'''
        
        func = self._modeSwitch[mode.type]
        
        vol = 0.0
        for id in linkIds:
            vol += func(network.link(id[0], id[1]), mode)
        
        return vol
    
    def _getAutoVol(self, link, mode):
        try:
            return link.auto_volume
        except AttributeError, e:
            raise Exception("Cannot get auto volumes. You need to run an auto assignment first.")
    
    def _getTransitVol(self, link, mode):
        try:
            t = 0
            for segment in link.segments():
                if segment.line.mode.id == mode.id:
                    t += segment.transit_volume
            return t
        except AttributeError, e:
            raise Exception("Cannot get transit volumes. You need to run a transit assignment first.")
    
    def _getAuxTransitVol(self, link, mode):
        try:
            return link.aux_transit_volume
        except AttributeError, e:
            raise Exception("Cannot get auxiliary transit volumes. You need to run a transit assignment first.")
    
    def _getAuxAutoVol(self, link, mode):
        raise Exception("Cannot get volumes for auxiliary auto mode!")
    