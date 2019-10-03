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

import csv
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
from pyproj import Proj
from osgeo import ogr
import osgeo.ogr
import shapely
import glob
import os
import inro.modeller as _m

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geo = _MODELLER.module('tmg.common.geometry')
_spindex = _MODELLER.module('tmg.common.spatial_index')
networkExportTool = _MODELLER.tool('inro.emme.data.network.export_network_as_shapefile')
gtfsExportTool = _MODELLER.tool('tmg.network_editing.GTFS_utilities.export_GTFS_stops_as_shapefile')
gtfsEmmeMap = _MODELLER.tool('tmg.network_editing.GTFS_utilities.GTFS_EMME_node_map')
shpEmmeMap = _MODELLER.tool('tmg.network_editing.GTFS_utilities.shp_emme_map')

class NodeEMMEmap(_m.Tool()):
    version = '0.0.1'
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
        
        pb.add_select_file(tool_attribute_name="MappingFileName",
                           window_type='save_file',
                           title="Map file to export in csv format")

        '''pb.add_select_file(tool_attribute_name="MappingfileName",
                           window_type='save_file',
                           title="Map file to export")'''
        return pb.render()

    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done")

    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if self.FileName[-3:].lower == "txt":
                gtfsEmmeMap(self.FileName, self.MappingFileName)
            if self.FileName[-3:].lower == "shp":
                shpEmmeMap(self.FileName, self.MappingFileName)

            '''#load stops
            stops = self._LoadStops()
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
            self._FindNearest(extents,convertedStops,nodes)'''

    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
