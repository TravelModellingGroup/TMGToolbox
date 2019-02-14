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
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import os
from copy import deepcopy
import csv
from math import sqrt as sqrt
from math import pow as pow
from pyproj import Proj
from osgeo import ogr
import osgeo.ogr
import shutil


_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')
_spindex = _MODELLER.module('tmg.common.spatial_index')
networkExportTool = _MODELLER.tool('inro.emme.data.network.export_network_as_shapefile')
gtfsExportTool = _MODELLER.tool('tmg.network_editing.GTFS_utilities.export_GTFS_stops_as_shapefile')
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

class CleanGTFS(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    GTFSFolderName = _m.Attribute(str)
    ServiceIdSet = _m.Attribute(str)
    UpdatedRoutesFile = _m.Attribute(str)
    MappingFileName = _m.Attribute(str)
    StopDistance = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        self._warning = ""
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Clean GTFS Folder v%s" %self.version,
                     description="Cleans a set of GTFS files by service ID. Filters all \
                         GTFS files except for routes, calendar, and shapes. Creates a new folder in the GTFS folder called 'cleaned'.\
                         This folder then contains all the cleaned GTFS files",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_file(tool_attribute_name='GTFSFolderName', 
                           window_type='directory', title="GTFS Folder")
        
        pb.add_text_box(tool_attribute_name='ServiceIdSet',
                        size=200, title="Service Id(s)",
                        note="Comma-separated list of service IDs from the calendar.txt file",
                        multi_line=True)
        
        pb.add_select_file(tool_attribute_name='UpdatedRoutesFile', 
                           window_type='file', title="Optional Filtered Routes")

        
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
        
        msg = "Tool complete."
        if not not self._warning:
            msg += "<br>" + self._warning 
        
        self.tool_run_msg = _m.PageBuilder.format_info(msg)
    
    ##########################################################################################################
    
    def __call__(self, GTFSFolderName, ServiceIdSet, UpdatedRoutesFile, MappingFileName, StopDistance):
        self.GTFSFolderName = GTFSFolderName
        '''self.MappingFileName = MappingFileName
        if StopDistance.lower() == 'none':
            self.StopDistance = 'none'
        else:
            self.StopDistance = float(StopDistance)'''
        
        self.tool_run_msg = ""
        self.TRACKER.reset()

        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        msg = "Tool complete."
        if not not self._warning:
            msg += "<br>" + self._warning 
        
        self.tool_run_msg = _m.PageBuilder.format_info(msg)   

    ##########################################################################################################    
    
    def _Execute(self):
        cells = self.ServiceIdSet.split(",")
        serviceIdSet = set(cells)

        self.cleanedFolderPath = self.GTFSFolderName+"/cleaned"
        if not os.path.exists(self.cleanedFolderPath):
            os.makedirs(self.cleanedFolderPath)
        self._TransferFiles(self.cleanedFolderPath)
        routesFile = ""
        if not self.UpdatedRoutesFile:
            routesFile = self.GTFSFolderName + "/routes.txt"
        else:
            routesFile = self.UpdatedRoutesFile
        routeIdSet = self._GetRouteIdSet(routesFile)
        self.TRACKER.completeTask()
        
        tripIdSet = self._FilterTripsFile(routeIdSet, serviceIdSet)
        self._GetNewRoutesFile(routesFile)
        if len(tripIdSet) == 0:
            self._warning = "Warning: No trips were selected."
        self.TRACKER.completeTask()
        
        servicedStopsSet = self._FilterStopTimesFile(tripIdSet)
        self.TRACKER.completeTask()
        
        self._FilterStopsFile(servicedStopsSet)
        self.TRACKER.completeTask()

    ##########################################################################################################
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    def _TransferFiles(self, cleanedFolderPath):
        gtfsFilesStatic = ["/agency.txt","/calendar.txt","/calendar_dates.txt","/fare_attributes.txt","/fare_rules.txt","/frequencies.txt","/transfers.txt","/feed_info.txt"]
        for file in gtfsFilesStatic:
            if os.path.isfile(self.GTFSFolderName + file) == True:
                shutil.copy2(self.GTFSFolderName + file, cleanedFolderPath + file)

    def _GetRouteIdSet(self, routesFile):
        idSet = set()
        with open(routesFile) as reader:
            header = reader.readline().split(",")
            print header
            idCol = header.index("route_id")
            
            for line in reader.readlines():
                cells = line.split(",")
                idSet.add(cells[idCol])
        return idSet
    
    def _FilterTripsFile(self, routeIdSet, serviceIdSet):
        exists = os.path.isfile(self.GTFSFolderName + "/shapes.txt")
        shapeIdSet = set()
        tripIdSet = set()
        self.routes = set()
        with nested(open(self.GTFSFolderName + "/trips.txt"), 
                    open(self.cleanedFolderPath + "/trips.txt", 'w')) as (reader, writer):
            header = reader.readline().strip()
            cells = header.split(",")
            writer.write(header)
            routeIdCol = cells.index("route_id")
            serviceIdCol = cells.index("service_id")
            tripIdCol = cells.index("trip_id")
            if exists == True:
                shapeIdCol = cells.index("shape_id")
            
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(",")
                if not cells[routeIdCol] in routeIdSet:
                    continue
                if not cells[serviceIdCol] in serviceIdSet:
                    continue
                tripIdSet.add(cells[tripIdCol])
                self.routes.add(cells[routeIdCol])
                if exists == True:
                    shapeIdSet.add(cells[shapeIdCol])
                writer.write("\n %s" %line)
        
        if exists == True:
            cleanedShapes = self._FilterShapesFile(shapeIdSet)
        return tripIdSet
    
    def _GetNewRoutesFile(self, routesFile):
        with nested(open(routesFile), 
                    open(self.cleanedFolderPath + "/routes.txt", 'w')) as (reader, writer):
            header = reader.readline().strip()
            cells = header.split(",")
            writer.write(header)
            routeIdCol = cells.index("route_id")
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(",")
                if not cells[routeIdCol] in self.routes:
                    continue
                writer.write("\n %s" %line)


    def _FilterShapesFile(self, shapeIdSet):
        with nested(open(self.GTFSFolderName + "/shapes.txt"),
                    open(self.cleanedFolderPath + "/shapes.txt", 'w')) as (reader, writer):
            header = reader.readline().strip()
            cells = header.split(",")
            writer.write(header)
            shapeIdCol = cells.index("shape_id")
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(",")
                if not cells[shapeIdCol] in shapeIdSet:
                    continue
                writer.write("\n %s" %line)


    def _FilterStopTimesFile(self, tripIdSet):
        servicedStopsSet = set()
        with nested(open(self.GTFSFolderName + "/stop_times.txt"),
                    open(self.cleanedFolderPath + "/stop_times.txt", 'w')) as (reader, writer):
            header = reader.readline().strip()
            writer.write(header)
            cells = header.split(",")
            tripIdCol = cells.index("trip_id")
            stopIdCol = cells.index("stop_id")
            
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(',')
                if not cells[tripIdCol] in tripIdSet:
                    continue
                servicedStopsSet.add(cells[stopIdCol])
                writer.write("\n%s" %line)
        return servicedStopsSet

    def _FilterStopsFile(self, servicedStopsSet):
        with nested(open(self.GTFSFolderName + "/stops.txt"),
                    open(self.cleanedFolderPath + "/stops.txt", 'w')) as (reader, writer):
            header = reader.readline().strip()
            writer.write(header)
            cells = header.split(",")
            stopIdCol = cells.index("stop_id")
            
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(",")
                if not cells[stopIdCol] in servicedStopsSet:
                    continue
                writer.write("\n%s" %line)

    
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