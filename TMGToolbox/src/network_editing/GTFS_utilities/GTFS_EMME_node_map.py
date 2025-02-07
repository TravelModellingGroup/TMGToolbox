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
import traceback as _traceback
from pyproj import Proj

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')
_spindex = _MODELLER.module('tmg.common.spatial_index')
networkExportTool = _MODELLER.tool('inro.emme.data.network.export_network_as_shapefile')
gtfsExportTool = _MODELLER.tool('tmg.network_editing.GTFS_utilities.export_GTFS_stops_as_shapefile')
EMME_VERSION = _util.getEmmeVersion(tuple)
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)
import re

class GTFStoEmmeMap(_m.Tool()):
    version = '0.0.2'
    tool_run_msg = ""
    number_of_tasks = 1 

    #Tool Parameters
    FileName = _m.Attribute(str)
    MappingFileName = _m.Attribute(str)

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker

    
    def page(self):

        pb = _tmgTPB.TmgToolPageBuilder(self, title = "GTFS Stops to Emme Node File v%s" %self.version,
                     description = "Takes the <b>stops.txt</b> file or a <b>shapefile</b> to create a mapping file that shows \
                             the node in the EMME network which it corresponds to.",
                     branding_text = "- TMG Toolbox")
                
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_file(tool_attribute_name="FileName",
                           window_type='file',
                           file_filter="*.txt *.shp",
                           title="stops.txt file from the GTFS folder or stops file in *.shp format")
        
        pb.add_select_file(tool_attribute_name="MappingFileName",
                           window_type='save_file',
                           file_filter='*.csv',
                           title="Map file to export")

        return pb.render()

    def __call__(self, StopFileName, MappingFileName):
        self.FileName = StopFileName
        self.MappingFileName = MappingFileName
        self.scenarioNumber = ScenarioNumber
        
        self.tool_run_msg = ""
        self.TRACKER.reset()

        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
            
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
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
            allnodes = _MODELLER.scenario.get_network().regular_nodes()
            #create node dictionary like converted stops?
            nodes = {}
            for n in allnodes:
                nodes[int(n.id)] = (float(n.x),float(n.y))
            #find extents
            extents = self._FindExtents(convertedStops,nodes)
            #load and find nearest point
            self._FindNearest(extents,convertedStops,nodes)


    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 


    
    def _LoadStopsTxt(self):
        stops = {}
        with open(self.FileName) as reader:
            #stop_lat,zone_id,stop_lon,stop_id,stop_desc,stop_name,location_type
            header = reader.readline().strip().split(',')
            latCol = header.index('stop_lat')
            lonCol = header.index('stop_lon')
            idCol = header.index('stop_id')
            nameCol = header.index('stop_name')
            descCol = header.index('stop_desc')
            
            for line in reader.readlines():
                cells = line.strip().split(',')
                id = cells[idCol]
                stop = GtfsStop(id,
                                cells[lonCol],
                                cells[latCol],
                                cells[nameCol],
                                cells[descCol])
                stops[id] = [float(cells[lonCol]),float(cells[latCol])]
        return stops 

    def _LoadStopsShp(self):
        stops = {}
        with _geo.Shapely2ESRI(self.FileName, 'r') as reader:
            loaded = 0
            for point in reader.readThrough():
                properties = reader.get_properties_by_fid(loaded)
                id = str(properties['stop_id'])
                lat = float(properties['stop_lat'])
                lon = float(properties['stop_lon'])

                stops[id] = [lon,lat]
                loaded += 1

        return stops

    def _ConvertStops(self, stops):
        convertedStops = {}
        # find what zone system the file is using
        fullzonestring = _m.Modeller().desktop.project.spatial_reference_file
        if EMME_VERSION >= (4,3,0):
            with open(fullzonestring, 'r') as zoneFile:
                zoneString = zoneFile.read()
                # parse for the first set of words between quotation "" marks
                # this is where the hemisphere and zone projection data is located
                # using the group() to extract the string
                zoneregex = re.search('"(.*?)"', zoneString)
                # determine which hemisphere the data exists and use appropiate marker
                if 'Northern Hemisphere' in zoneregex.group(0):
                    hemisphere = 'N'
                else: 
                    hemisphere = 'S'
                # split the word on spaces into a list of strings
                zonelist = zoneregex.group(0).split(' ')
                # remove the trailing comma at the end of the number the number is 17,
                # convert the number into an integer
                prjzone = int(zonelist[2].replace(',',''))
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
        spatialIndex = _spindex.GridIndex(extents, 1000, 1000)
        network = _MODELLER.scenario.get_network()
        for node in network.regular_nodes():
            spatialIndex.insertPoint(node)
        for stop in convertedStops:
            nearestNode = spatialIndex.nearestToPoint(convertedStops[stop][0], convertedStops[stop][1])
            if nearestNode[0] == "Nothing Found":
                map.append([stop, nearestNode[0],convertedStops[stop][0],convertedStops[stop][1],-1,-1])
            elif nearestNode[0] is None:
                map.append([stop, nearestNode[0],convertedStops[stop][0],convertedStops[stop][1],0,0])
            else:
                cleanedNumber = int(nearestNode[0])
                map.append([stop, cleanedNumber,convertedStops[stop][0],convertedStops[stop][1],nodes[cleanedNumber][0],nodes[cleanedNumber][1]])

        with _util.open_csv_writer(self.MappingFileName) as mapFile:
            header = ["stopID","emmeID","stop x", "stop y", "node x", "node y"]
            mapFile.writerow(header)
            for row in map:
                mapFile.writerow([row[0],row[1], row[2], row[3], row[4], row[5]])

        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
class GtfsStop():
    
    def __init__(self, id, lon, lat, name, description):
        self.id = id
        self.lat = float(lat)
        self.lon = float(lon)
        self.name= name
        self.description = description
        self.modes = set()
    
