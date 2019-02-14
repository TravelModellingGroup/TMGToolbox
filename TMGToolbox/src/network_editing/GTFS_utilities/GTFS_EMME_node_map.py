'''
    Copyright 2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
import csv
from math import sqrt as sqrt
from math import pow as pow
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
from pyproj import Proj
from osgeo import ogr
import osgeo.ogr

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')
_spindex = _MODELLER.module('tmg.common.spatial_index')
networkExportTool = _MODELLER.tool('inro.emme.data.network.export_network_as_shapefile')
gtfsExportTool = _MODELLER.tool('tmg.network_editing.GTFS_utilities.export_GTFS_stops_as_shapefile')
EMME_VERSION = _util.getEmmeVersion(tuple)

class GTFStoEmmeMap(_m.Tool()):
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 

    #Tool Parameters
    FileName = _m.Attribute(str)
    MappingFileName = _m.Attribute(str)
    NodeRangeSet = _m.Attribute(str)
    scenarioId = _m.Attribute(str)


    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker

    
    def page(self):

        pb = _tmgTPB.TmgToolPageBuilder(self, title = "GTFS Stops to Emme Node File v%s" %self.version,
                     description = "Takes the <b>stops.txt</b> file and creates a mapping file that shows \
                             the node in the EMME network which it corresponds to.",
                     branding_text = "- TMG Toolbox")
                
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_file(tool_attribute_name="FileName",
                           window_type='file',
                           file_filter="*.txt *.shp",
                           title="The shp or stops.txt file that contains the stops information. Please note that the stops.txt file format should \
                           follow GTFS rules. The shp files also needs to contain the DBF field 'StopID'")

        pb.add_text_box(tool_attribute_name='NodeRangeSet',
                        size=200, title="Node Range",
                        note="Comma-separated list of allowed node number ranges to map to. Input 'all' to map to any node. Example '1-5,10-15'",
                        multi_line=True)
        
        pb.add_select_file(tool_attribute_name="MappingFileName",
                           window_type='save_file',
                           file_filter='*.csv',
                           title="Map file to export")

        pb.add_text_box(tool_attribute_name='scenarioId',
                        size=4, title="scenarioId",
                        note="Id for the scenario")


        return pb.render()

    def __call__(self, StopFileName, NodeRangeSet, MappingFileName, scenarioId):
        self.FileName = StopFileName
        self.MappingFileName = MappingFileName
        self.tool_run_msg = ""
        self.TRACKER.reset()
        self.scenarioId = int(scenarioId)
        if NodeRangeSet.lower() == 'all':
            self.FullRange = 'all'
        else:
            NodeRangeSet = NodeRangeSet.strip().split(',')
            self.FullRange = []
            for ranges in NodeRangeSet:
                r = ranges.split('-')
                self.FullRange = self.FullRange + (range(int(r[0]),int(r[1])+1))


        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
            
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        if self.NodeRangeSet.lower() == 'all':
            self.FullRange = 'all'
        else:
            self.RangeSets = self.NodeRangeSet.split(',')
            self.FullRange = []
            for ranges in self.RangeSets:
                r = ranges.split('-')
                self.FullRange = self.FullRange + (range(int(r[0]),int(r[1])+1))
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done")

    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            #def file type
            if self.FileName[-3:].lower() == "txt":
                stops = self._LoadStopsTxt()
            elif self.FileName[-3:].lower() == "shp":
                stops = self._LoadStopsShp()
            else:
                raise Exception("Not a correct format")
            #need to convert stops from lat lon to UTM
            convertedStops = self._ConvertStops(stops)
            #load nodes from network
            self.network =  _MODELLER.emmebank.scenario(int(self.scenarioId)).get_network()
            allnodes = self.network.regular_nodes()
            #create node dictionary like converted stops?
            nodes = {}
            for n in allnodes:
                if self.FullRange == 'all':
                    nodes[int(n.id)] = (float(n.x),float(n.y))
                else:
                    if int(n.id) in self.FullRange:
                        nodes[int(n.id)] = (float(n.x),float(n.y))
            #find extents
            extents = self._FindExtents(convertedStops,nodes)
            #load and find nearest point
            self._FindNearest(extents,convertedStops,nodes)


    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                }
            
        return atts 


    
    def _LoadStopsTxt(self):
        stops = {}
        self.fullStops = {}
        with open(self.FileName) as reader:
            stopsfile = csv.reader(reader)
            header = stopsfile.next()
            #stop_lat,zone_id,stop_lon,stop_id,stop_desc,stop_name,location_type
            #header = reader.readline().strip().split(',')
            latCol = header.index('stop_lat')
            lonCol = header.index('stop_lon')
            idCol = header.index('stop_id')
            nameCol = header.index('stop_name')
            if 'stop_desc' in header:
                descCol = header.index('stop_desc')
            else:
                descCol = None
            for row in stopsfile:
                id = row[idCol]
                if descCol != None:
                    desc = row[descCol]
                else:
                    desc = None
                stop = GtfsStop(id,
                                row[lonCol],
                                row[latCol],
                                row[nameCol],
                                desc)
                stops[id] = [float(row[lonCol]),float(row[latCol])]
                self.fullStops[stop.id] = stop
            '''for line in reader.readlines():
                cells = line.strip().split(',')
                id = cells[idCol]
                if descCol != None:
                    desc = cells[descCol]
                else:
                    desc = None
                stop = GtfsStop(id,
                                cells[lonCol],
                                cells[latCol],
                                cells[nameCol],
                                desc)
                stops[id] = [float(cells[lonCol]),float(cells[latCol])]
                self.fullStops[stop.id] = stop'''
        return stops

    def _LoadStopsShp(self):
        stops = {}
        shp = ogr.Open(self.ShpFileName)
        layer = shp.GetLayer(0)
        if layer.GetGeomType() == 1:
            for feat in layer:
                index1 = feat.GetFieldIndex("StopID")
                id = feat.GetField(index1)
                geom  = feat.GetGeometryRef()
                points = geom.GetPointCount()
                for point in xrange(points):
                    lon, lat, z = geom.GetPoint(point)
                    stops[id] = [float(lon),float(lat)]
        return stops 

    def _ConvertStops(self, stops):
        convertedStops = {}
        # find what zone system the file is using
        fullzonestring = _m.Modeller().desktop.project.spatial_reference_file
        if EMME_VERSION >= (4,3,0):
            with open(fullzonestring, 'r') as zoneFile:
                zoneString = zoneFile.read()
                hemisphere = zoneString[28:29]
                prjzone = int(zoneString[26:28])
        else:
            hemisphere = fullzonestring[-5:-4]
            prjzone = int(fullzonestring[-7:-5])
        # put try and exception statements here?
        if hemisphere.lower() == 's':
            p = Proj("+proj=utm +ellps=WGS84 +zone=%d +south" %prjzone)
        else:
            p = Proj("+proj=utm +ellps=WGS84 +zone=%d" %prjzone)
        stoplons = ()
        stoplats = ()
        for stop in stops.keys():
            templons = (float(stops[stop][0]),)
            templats = (float(stops[stop][1]),)
            x, y = p(templons, templats)
            convertedStops[stop] = x+y
            convertedStops[stop] = (float(convertedStops[stop][0]),float(convertedStops[stop][1]))
            self.fullStops[stop].x = convertedStops[stop][0]
            self.fullStops[stop].y = convertedStops[stop][1]
        return convertedStops


    def _FindExtents(self, convertedStops, nodes):
        #find extents
        maxExtentx = float("-inf")
        minExtentx =  float("inf")
        maxExtenty = float("-inf")
        minExtenty =  float("inf")
        for key in convertedStops:
            if convertedStops[key][0] < minExtentx:
                minExtentx = float(convertedStops[key][0])
            if convertedStops[key][0] > maxExtentx:
                maxExtentx = float(convertedStops[key][0])
            if convertedStops[key][1] < minExtenty:
                minExtenty = float(convertedStops[key][1])
            if convertedStops[key][1] > maxExtenty:
                maxExtenty = float(convertedStops[key][1])
        for node in nodes:
            if nodes[node][0] < minExtentx:
                minExtentx = float(nodes[node][0])
            if nodes[node][0] > maxExtentx:
                maxExtentx = float(nodes[node][0])
            if nodes[node][1] < minExtenty:
                minExtenty = float(nodes[node][1])
            if nodes[node][1] > maxExtenty:
                maxExtenty = float(nodes[node][1])
        extents = (minExtentx-1,minExtenty-1,maxExtentx+1,maxExtenty+1)
        return extents

    def _FindNearest(self, extents, convertedStops, nodes):
        map = []
        spatialIndex = _spindex.GridIndex(extents, 500, 500)
        for node in self.network.regular_nodes():
            if self.FullRange == 'all':
                spatialIndex.insertPoint(node)
            else:
                if int(node.id) in self.FullRange:
                    spatialIndex.insertPoint(node)

        for stop in convertedStops:
            nearestNode = spatialIndex.nearestToPoint(convertedStops[stop][0], convertedStops[stop][1])
            if nearestNode[0] == "Nothing Found":
                map.append([stop, nearestNode[0],convertedStops[stop][0],convertedStops[stop][1],-1,-1, self.fullStops[stop].name])
            elif nearestNode[0] == None:
                map.append([stop, nearestNode[0],convertedStops[stop][0],convertedStops[stop][1],0,0, self.fullStops[stop].name])
            else:
                cleanedNumber = int(nearestNode[0])
                map.append([stop, cleanedNumber,convertedStops[stop][0],convertedStops[stop][1],nodes[cleanedNumber][0],nodes[cleanedNumber][1], \
                            self.fullStops[stop].name])
        with open(self.MappingFileName, 'wb') as csvfile:
            mapFile = csv.writer(csvfile, delimiter=',')
            header = ["stopID","emmeID","stop x", "stop y", "node x", "node y", "distance", "stop_name"]
            mapFile.writerow(header)
            for row in map:
                distanceToNode = sqrt(abs(float(row[2])-float(row[4]))**2 + abs(float(row[3])-float(row[5]))**2)
                mapFile.writerow([row[0],row[1], row[2], row[3], row[4], row[5], distanceToNode, row[6]])


        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
class GtfsStop():
    
    def __init__(self, id, lon, lat, name, description, x = 0, y = 0):
        self.id = id
        self.lat = float(lat)
        self.lon = float(lon)
        self.name= name
        self.description = description
        self.modes = set()
        self.x = float(x)
        self.y = float(y)

'''x = GTFStoEmmeMap()
#self, StopFileName, NodeRangeSet, MappingFileName, scenarioId
x("C:\Users\Bilal Yusuf\Documents\TMG\TTC\gtfs-ttc-18oct\cleaned bus\stops.txt", "10000-90000",\
  "C:\Users\Bilal Yusuf\Documents\TMG\TTC\gtfs-ttc-18oct\cleaned bus\m3 100x100.csv", 5)
print "done"'''