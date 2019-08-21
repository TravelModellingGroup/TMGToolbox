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
Export Gtfs Stops as Shapefile

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')

##########################################################################################################

class ExportGtfsStopsAsShapefile(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    GtfsFolderName = _m.Attribute(str)
    ShapefileName = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export GTFS Stops As Shapefile v%s" %self.version,
                     description="Converts the <b>stops.txt</b> file to a shapefile, flagging which \
                             modes it serves as well.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_file(tool_attribute_name="GtfsFolderName",
                           window_type='directory',
                           title="GTFS Folder Directory")
        
        pb.add_select_file(tool_attribute_name="ShapefileName",
                           window_type='save_file',
                           title="Shapefile Name for Export")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            
            routeModes = self._LoadRoutes()
            print "Routes Loaded."
            tripModes = self._LoadTrips(routeModes)
            print "Trips loaded."
            stops = self._LoadStops()
            print "Stops loaded."
            self._LoadStopTimes(stops, tripModes)
            print "Stop times loaded."
            self._WriteStopsToShapefile(stops)
            self._WriteProjectionFile()
            print "Shapefile written."

    ##########################################################################################################    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _LoadRoutes(self):
        output = {}
        with open(self.GtfsFolderName + "/routes.txt") as reader:
            header = reader.readline().strip().split(',')
            routeIdCol = header.index('route_id')
            modeCol = header.index('route_type')
            
            for line in reader.readlines():
                cells = line.strip().split(',')
                output[cells[routeIdCol]] = int(cells[modeCol])
        return output #RouteID -> mode
    
    def _LoadTrips(self, routeModes):
        output = {}
        with open(self.GtfsFolderName + "/trips.txt") as reader:
            header = reader.readline().strip().split(',')
            routeIdCol = header.index('route_id')
            tripIdCol = header.index('trip_id')
            
            for line in reader.readlines():
                cells = line.strip().split(',')
                output[cells[tripIdCol]] = routeModes[cells[routeIdCol]]
        return output #TripID -> mode
    
    def _LoadStops(self):
        stops = {}
        with open(self.GtfsFolderName + "/stops.txt") as reader:
            #stop_lat,zone_id,stop_lon,stop_id,stop_desc,stop_name,location_type
            header = reader.readline().strip().split(',')
            latCol = header.index('stop_lat')
            lonCol = header.index('stop_lon')
            idCol = header.index('stop_id')
            nameCol = header.index('stop_name')
            if 'stop_desc' in header:
                descCol = header.index('stop_desc')
            else:
                descCol = header.index('stop_name')
            
            for line in reader.readlines():
                cells = line.strip().split(',')
                id = cells[idCol]
                stop = GtfsStop(id,
                                cells[lonCol],
                                cells[latCol],
                                cells[nameCol],
                                cells[descCol])
                stops[id] = stop
        return stops #StopID -> stop
    
    def _LoadStopTimes(self, stops, tripModes):
        
        modeCharacterMap = {0: 's',
                            1: 'm',
                            2: 'r',
                            3: 'b',
                            4: 'f',
                            5: 'c',
                            6: 'g',
                            7: 'x'}
        
        with open(self.GtfsFolderName + "/stop_times.txt") as reader:
            #trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled
            header = reader.readline().strip().split(',')
            tripIdCol = header.index('trip_id')
            stopIdCol = header.index('stop_id')
            
            for line in reader.readlines():
                cells = line.strip().split(',')
                if not cells[stopIdCol] in stops: 
                    print "Could not find stop '%s'" %cells[stopIdCol]
                    continue
                stop = stops[cells[stopIdCol]]                    
                
                if not cells[tripIdCol] in tripModes:
                    print "Could not find trip '%s'" %cells[tripIdCol]
                    continue
                mode = tripModes[cells[tripIdCol]]
                
                stop.modes.add(modeCharacterMap[mode])
    
    def _WriteStopsToShapefile(self, stops):
        
        with _geo.Shapely2ESRI(self.ShapefileName, 'w',
                               'POINT') as writer:
            
            maxDescription = 10
            maxName = 10
            for stop in stops.itervalues():
                nameLen = len(stop.name)
                desLen= len(stop.description)
                
                if nameLen > maxName:
                    maxName = nameLen
                if desLen > maxDescription:
                    maxDescription = desLen
            
            print maxDescription
            print maxName
            
            writer.addField("StopID")
            writer.addField("Name", length=maxName)
            writer.addField("Description", length=maxDescription)
            writer.addField("Modes", length=8)
            
            def modeSetToString(modeSet):
                s = ""
                for c in modeSet:
                    s += c
                return s
            
            for stop in stops.itervalues():
                point = _geo.Point(stop.lon, stop.lat)
                point["StopID"] = stop.id
                point["Name"] = stop.name
                point["Description"] = stop.description
                point["Modes"] = modeSetToString(stop.modes)
                
                writer.writeNext(point)
    
    def _WriteProjectionFile(self):
        wkt = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
        with open(_path.splitext(self.ShapefileName)[0] + ".prj", 'w') as writer:
            writer.write(wkt)
        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
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
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    