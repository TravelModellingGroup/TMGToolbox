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
Kucirek-Vaughan Automated Centroid Connector Generator (CCGen)

    Authors:  Peter Kucirek, James Vaughan

    Latest revision by: pkucirek
        
    Advanced centroid connector generation tool. Documentation for this tool
    is available on the TMG website (http://tmg.utoronto.ca); TMG member agencies only.
'''

#---VERSION HISTORY
'''
    0.1.0 Created March 28,2013
    
    0.2.0 Revamped the utility function to use different terms. Added the ability to specify a node
        mass attribute. Added better reporting to the logbook.
    
    0.2.1 Added better reporting. Also cleaned up error handling during loading of zones.
    
    0.2.2 Re-introduced gravity term.
    
    0.2.3 Major improvements:
        - Using the new Shapely library, added the ability to search for candidate nodes falling
            within a set distance of the zone polygon.
        - Changed 'candidateNodes' from a list to a dict (node -> distance).
        - Attached candidate nodes to the zone as a temporary attribute.
        - Also attached to the zone is the zone geometry.
        
    0.3.0 Changes:
        - Adjusted the radial distribution term by removing the subtraction from maximum,
            meaning that its coefficient should be negative, not positive.
        - Adjusted the gravity term to no longer be normalized.
        - Adjusted the gravity term to not use node mass (i.e., all nodes are equally weighted = 1.0)
    
    0.3.1 Improved speed by replacing the 'pow' function by a multiplication
    
    0.3.2 Added the option to export the full report to a text file
    
    0.3.3 Added progress reporting to the tool, as well as variable defaults.
    
    1.0.0 Upgraded UI + usability for release version. Major improvements:
        - Using Utilities.tempExtraAttributeMANAGER to get the temporary flag attibute
        - Using SpatialIndex.GridIndex for indexing boundary geometries
        - Using SpatialIndex.GridIndex for indexing network nodes
        
    1.0.1 Fixed a minor bug in the UI where the zone field selector combobox wasn't
        loading properly after a run. Also fixed a bug where the tool would crash if
        no zones were selected to be connected.  
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path
from itertools import combinations
import math
import inspect
import numpy
_MODELLER = _m.Modeller()
_g = _MODELLER.module('tmg.common.geometry')
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_spindex = _MODELLER.module('tmg.common.spatial_index')

def _straightLineDist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)*(x1 - x2) + (y1 - y2)*(y1 - y2))

def _manhattanDist(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)

##########################################################################################################

class CCGEN(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    report_html = ""
    
    #---Variable definitions
    ZonesFile = _m.Attribute(str)
    ZoneShapeFile = _m.Attribute(str)
    ShapefileZoneAttributeId = _m.Attribute(str)
    
    BoundaryFile = _m.Attribute(str)
    InfeasibleLinkSelector = _m.Attribute(str)
    NodeExcluderOption = _m.Attribute(int) # 2: Greedy, 1: Reluctant
    
    MaxConnectors = _m.Attribute(int)
    MaxCandidates = _m.Attribute(int)
    SearchRadius = _m.Attribute(float)
    
    BetaRadialDist = _m.Attribute(float)
    BetaMassSum = _m.Attribute(float)
    BetaLengthStdDev = _m.Attribute(float)
    BetaGravity = _m.Attribute(float)
    
    ErrorHandlingOption = _m.Attribute(int) # 1: Crash and revert, 2: Catch and report.
    DoFullReport = _m.Attribute(bool)
    DoSummaryReport = _m.Attribute(bool)
    FullReportFile = _m.Attribute(str)
    
    Scenario = _m.Attribute(_m.InstanceType) #
    ConnectorModeIds = _m.Attribute(_m.ListType)
    MassAttribute = _m.Attribute(_m.InstanceType)
    
    def __init__(self):
        
        self.Scenario = _MODELLER.scenario
        self._tracker = _util.ProgressTracker(5)
        
        self.BetaMassSum = 0.0
        self.BetaRadialDist = 0.0
        self.BetaLengthStdDev = 0.0
        self.BetaGravity = 0.0
        self.InfeasibleLinkSelector = ""
        self.MaxCandidates = 10
        self.MaxConnectors = 4
        self.SearchRadius = 2.0
        self.DoFullReport = False
        self.DoSummaryReport = False
        self.FullReportFile = ""
        
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="CCGEN v%s" %self.version,
                                description="Advanced tool for adding centroid connectors to unconnected \
                                zones (or loading zones from a file). Uses a utility function to choose \
                                the best combination of candidate nodes for connections. Contact TMG \
                                for additional documentation.",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select Scenario",
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name="ZonesFile",
                            window_type="file",
                            file_filter="*.txt; *.csv; *.211",
                            title="File with zones to be added",
                            note="Accepts CSV, tab-delimited text, and Emme network batchout (*.211) formats.\
                                <br>If left blank, the tool will look for unconnected zones.")
        
        pb.add_select_file(tool_attribute_name="ZoneShapeFile",
                            window_type="file",
                            file_filter="*.shp",
                            title="Zone Shapefile",
                            note="<font color='green'><b>Optional:</b></font> \
                                Shapefile defining zone shapes. If selected, the \
                                algorithm will apply the search <br>radius as a buffer around each \
                                zone polygon and use only those nodes which fall inside.")
        
        pb.add_select(tool_attribute_name= 'ShapefileZoneAttributeId',
                      keyvalues= [],
                      title= "Zone ID Attribute",
                      note= "Shapefile field containing zone ID attribute (corresponds to network zone ID).")
        
        keyval = []
        for mode in self.Scenario.modes():
            text = " ".join([mode.id, mode.description, mode.type])
            keyval.append((mode.id, text))
        pb.add_select(tool_attribute_name="ConnectorModeIds",
                           title="Modes on new connectors",
                           keyvalues= keyval)
        
        pb.add_header("EXCLUSIONS")
        
        pb.add_select_file(tool_attribute_name="BoundaryFile",
                            window_type="file",
                            file_filter="*.shp",
                            title="Boundary shapefile",
                            note="<font color='green'><b>Optional.</b></font> Centroids are \
                            not permitted to cross any features in this shapefile.")
        
        pb.add_text_box(tool_attribute_name='InfeasibleLinkSelector',
                        size=300,
                        multi_line=True,
                        title='Infeasible link selector',
                        note="Formatted the same as for a network calculation.")
        
        pb.add_select(tool_attribute_name="NodeExcluderOption",
                           title="Node exclusion options:",
                           keyvalues={1 : "<b>Reluctant:</b> Nodes connected only to flagged links will be excluded.",
                            2 : "<b>Greedy:</b> Nodes connected to any flagged links will be excluded."})
        
        pb.add_header("SEARCH PARAMETERS")
        
        pb.add_text_box(tool_attribute_name='MaxConnectors',
                        size=2,
                        title='Maximum number of connectors')
        
        pb.add_text_box(tool_attribute_name='MaxCandidates',
                        size=2,
                        title='Maximum number of candidate nodes',
                        note="Fewer candidates improves computation time.")
        
        pb.add_text_box(tool_attribute_name='SearchRadius',
                        size=10,
                        title='Search radius',
                        note="In coordinate units.\
                        <br>If a zone shapefile is used, this will be the buffer distance around zone polygons.")
        
        pb.add_header("UTILITY FUNCTION")
        
        pb.add_select_attribute(tool_attribute_name="MassAttribute",
                                filter='NODE',
                                allow_none=True,
                                title="Node weight attribute",
                                note="Optional. If no attribute is specified, all nodes will have a weight of 1.\
                                <br>If an attribute is specified, ensure that the default value is 1.")
        
        with pb.add_table(visible_border=False, title="Parameters") as t:
            with t.table_cell():
                pb.add_html("<b>V = ")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='BetaMassSum',
                        size=7)
            with t.table_cell():
                pb.add_html("<b>x MassSum +")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='BetaRadialDist',
                        size=7)
            with t.table_cell():
                pb.add_html("<b>x RadDist +")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='BetaLengthStdDev',
                        size=7)
            with t.table_cell():
                pb.add_html("<b>x LenDev +</b>")
            
            t.new_row()
            
            with t.table_cell():
                pass
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='BetaGravity',
                        size=7)
            with t.table_cell():
                pb.add_html("<b>x Gravity</b>")

        pb.add_header("TOOL OPTIONS")
        
        pb.add_select(tool_attribute_name="ErrorHandlingOption",
                      title="Error handling option",
                      note="Only applies to non-fatal errors.",
                      keyvalues=[(1, "Crash and revert"),
                                 (2, "Skip and report")])
        
        pb.add_checkbox(tool_attribute_name="DoSummaryReport",
                                title="Summary report?",
                                note="Report will be written to the logbook.")
        
        pb.add_select_file(tool_attribute_name="FullReportFile",
                            window_type="save_file",
                            file_filter="*.txt",
                            title="Full Report File",
                            note="Optional text file to save detailed utility statistics for each zone.")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        if (tool.has_shapefile_loaded())
        {
            $("#ShapefileZoneAttributeId")
                .empty()
                .append(tool.preload_shapefile_fields())
            inro.modeller.page.preload("#ShapefileZoneAttributeId");
            $("#ShapefileZoneAttributeId").trigger('change');
            $("#ShapefileZoneAttributeId").prop('disabled', false);
        } else {
            $("#ShapefileZoneAttributeId").prop('disabled', true);
        }
        
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#ConnectorModeIds")
                .empty()
                .append(tool.preload_scenario_modes())
            //inro.modeller.page.preload("#ConnectorModeIds");
            $("#ConnectorModeIds").trigger('change');
        });
        
        $("#ZoneShapeFile").bind('change', function()
        {
            $(this).commit();
            $("#ShapefileZoneAttributeId")
                .empty()
                .append(tool.preload_shapefile_fields())
            inro.modeller.page.preload("#ShapefileZoneAttributeId");
            $("#ShapefileZoneAttributeId").trigger('change');
            $("#ShapefileZoneAttributeId").prop('disabled', false);
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    @_m.method(return_type= unicode)
    def preload_scenario_modes(self):
        print "bob"
        options = []
        for mode in self.Scenario.modes():
            text = "%s %s %s" %(mode.id, mode.description, mode.type)
            options.append("<option value='%s'>%s</option>" %(mode.id, text))
        return "\n".join(options)
    
    @_m.method(return_type= bool)
    def has_shapefile_loaded(self):
        return self.ZoneShapeFile != None
    
    @_m.method(return_type= unicode)
    def preload_shapefile_fields(self):
        with _g.Shapely2ESRI(self.ZoneShapeFile) as reader:
            options = []
            for fieldName in reader.getFieldNames():
                options.append("<option value='%s'>%s</option>" %(fieldName, fieldName))
            
            return "\n".join(options)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
                
        if self.FullReportFile != "":
            self.DoFullReport = True
        
        print self.MassAttribute
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    ##########################################################################################################    
    
    def _execute(self):
        self._tracker.reset()
        
        with _m.logbook_trace(name="{0} v{1}".format(self.__class__.__name__,self.version), attributes=self._getAtts()):          
            with _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK') as flagAttr:
                with _m.logbook_trace("Flagging infeasible links"):
                    self._applyInfeasibleLinkFilter(flagAttr.id)
                
                network = self.Scenario.get_network() # Get the network once.
                
                #---1. Load the zones file
                zonesToProcess = None
                if self.ZonesFile == None or self.ZonesFile == "":
                    zonesToProcess = self._getUnconnectedZones(network)
                    _m.logbook_write("Selected %s unconnected zones already in the network" %len(zonesToProcess))
                else:
                    zonesToProcess = self._loadZonesToBeAdded(self.ZonesFile, network)
                    _m.logbook_write("Loaded new zones from file '%s'" %self.ZonesFile)
                self._tracker.completeTask() # TASK 2
                
                if len(zonesToProcess) == 0:
                    self.tool_run_msg = _m.PageBuilder.format_info("No zones were selected for processing.")
                    return
                
                #---2. Create temporary zone attributes in the network
                network.create_attribute('NODE', '_geometry', None) # For zones, stores the boundaries. For nodes, stores the point geometry.
                network.create_attribute('NODE', '_candidateNodes', None) # Stores a mapping of candidateNode -> distance from centroid 
                
                #---2. Load the optional boundaries files
                self._tracker.startProcess(2)
                if self.BoundaryFile != None and self.BoundaryFile != "":
                    self._loadBoundaryFile(self.BoundaryFile)
                else:
                    self._Boundaries = None
                self._tracker.completeSubtask()
                
                if self.ZoneShapeFile != None and self.ZoneShapeFile != "":
                    self._loadZoneShape(self.ZoneShapeFile, network)
                self._tracker.completeSubtask()
                
                #---3. Get feasible nodes
                feasibleNodes = None
                with _m.logbook_trace("Getting set of feasible nodes"):
                    feasibleNodes, nFeasibleNodes = {2 : self._getFeasibleNodesGreedy,
                                     1 : self._getFeasibleNodesReluctant}[self.NodeExcluderOption](network, flagAttr.id)
                    _m.logbook_write("%s nodes were selected as feasible in the network." %nFeasibleNodes)
                    print "Filtered and indexed feasible nodes"
                self._tracker.completeTask() # TASK 4
                
                #---4. Process new zones
                '''
                TODO:
                - Generate full data for report (optional)
                - Modify tool to use a node attribute for feasibility exclusion?
                '''
                
                summaryReport = None
                fullReport = None
                if self.DoSummaryReport:
                    summaryReport = SummaryReport()
                    
                if self.DoFullReport:
                    fullReport = FullReport(self.FullReportFile)
                    
                zonesHandled = 0
                errors = 0
                self._tracker.startProcess(len(zonesToProcess)) # TASK 5
                print "Processing zones"
                for zone in zonesToProcess: #{1
                    try:
                        #{
                        atts = self._HANDLE_ZONE(zone, feasibleNodes, network)
                        zonesHandled += 1
                        
                        if self.DoSummaryReport:
                            summaryReport.addZoneData(atts)
                        
                        if self.DoFullReport:
                            fullReport.addZoneData(zone, atts)
                        #}
                    except ObjectProcessingError, ope:
                        if self.ErrorHandlingOption == 2:
                            errors += 1
                            if self.DoSummaryReport:
                                summaryReport.addError()
                            _m.logbook_write(name="Error processing zone %s" %ope.object,
                                         value=str(ope),
                                         attributes=ope.atts)
                        else:
                            raise
                    self._tracker.completeSubtask()
                print "Done connecting zones."
                #}1
                
                #---6. Report results
                if self.DoSummaryReport:
                    _m.logbook_write("Summary report", value=summaryReport.render())
                
                if self.DoFullReport:
                    fullReport.export()
                
                self.Scenario.publish_network(network, resolve_attributes=True) #Resolve the temporary attributes by ignoring them
                self.report_html = self.FullReportFile
                _m.Modeller().desktop.refresh_needed(True)
                self.tool_run_msg = _m.PageBuilder.format_info("Connector generation complete. {0} zones were connected, with {1} errors.".format(zonesHandled, errors))


    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version,
                "Infeasible Link Selector" : self.InfeasibleLinkSelector,
                "Max Connectors" : self.MaxConnectors,
                "Max Candidates" : self.MaxCandidates,
                "Search Radius" : self.SearchRadius,
                "Node Excluder Option" : {2 : "Greedy", 1 : "Reluctant"}[self.NodeExcluderOption],
                "Beta Mass" : self.BetaMassSum,
                "Beta Radial Dist" : self.BetaRadialDist,
                "Beta Length Dist" : self.BetaLengthStdDev,
                "Boundary File" : self.BoundaryFile,
                "Beta Gravity" : self.BetaGravity,
                "Zones File" : self.ZonesFile,
                "Mass Attribute" : str(self.MassAttribute),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    #-----Initialization Functions--------------------------------------------------------------------------
    
    def _loadBoundaryFile(self, filename):
        with _g.Shapely2ESRI(filename) as reader:
            minx = float('inf')
            miny = float('inf')
            maxx = float('-inf')
            maxy = float('-inf')
            
            boundaries = []
            for boundary in reader.readThrough():

                boundary_geometry = boundary.geom_type

                #if shape is polygon, must be converted to a linear ring
                if boundary_geometry == 'Polygon':
                    boundary = boundary.exterior


                bminx, bminy, bmaxx, bmaxy = boundary.bounds
                if bminx < minx: minx = bminx
                if bminy < miny: miny = bminy
                if bmaxx > maxx: maxx = bmaxx
                if bmaxy > maxy: maxy = bmaxy
                boundaries.append(boundary)
            
            extents = minx - 1.0, miny - 1.0, maxx + 1.0, maxy + 1.0
            spatialIndex = _spindex.GridIndex(extents, 200, 200)
            for ls in boundaries:
                spatialIndex.insertLineString(ls)
            
            self._Boundaries = spatialIndex
            
        print "Loaded and indexed boundaries."
        _m.logbook_write("Boundary file loaded: '%s'" %filename)
    
    def _loadZoneShape(self, filename, network):
        with _g.Shapely2ESRI(filename) as reader:
            idLabel = self.ShapefileZoneAttributeId
            
            for poly in reader.readThrough():
                zone = network.node(poly[idLabel])
                if zone != None:
                    if not zone.is_centroid:
                        _m.logbook_write("Corresponding network node for zone shape '%s' is not a zone!" %poly[idLabel])
                    else:
                        zone._geometry = poly
                '''
                else:
                    _m.logbook_write("Could not find corresponding network node for zone shape '%s'!" %poly[idLabel])
                '''
                
        _m.logbook_write("Zone shapefile loaded: '%s'" %filename)
    
    def _loadZonesToBeAdded(self, filename, network):
        
        opener = {'.txt' : self._openTabDelimitedFile,
               '.csv' : self._openCSV,
               '.211': self._load211File}
        
        ext = path.splitext(filename)[1]
        
        '''
        TODO:
        - Load other node attributes (ui1, ui2, ui3)
        '''
        
        try:
            return opener[ext](filename, network)
        except KeyError, ke:
            raise IOError("File format '*.%s' is unsupported!" %ext)
    
    def _openTabDelimitedFile(self, filename, network):
        return self._openDelimitedFile(filename, network,  "\t")
    
    def _openCSV(self, filename, network):
        return self._openDelimitedFile(filename, network, ",")
    
    def _load211File(self, filename, network):
        addedZones = []
        currentLine = 0
        
        with open(filename) as file:
            while True:
                line = file.readline()
                if line == '':
                    break
                
                currentLine += 1
                
                if line.startswith("a*"):
                    cells = line.split()
                    
                    if "=" in line:
                        i = None
                        x = None
                        y = None
                        lab = None
                        
                        for i in range(1, len(cells)):
                            sc = cells[i].split('=')
                            if sc[0] == 'i' or sc[0] == 'inode':
                                i = sc[1]
                            elif sc[0] == "xi":
                                x = sc[1]
                            elif sc[0] == "yi":
                                y = sc[1]
                            elif sc[0] == "lab" or sc[0] == "lbi" or sc[0] == "labi":
                                lab = sc[1]
                        
                        try:
                            zone = network.create_centroid(i)
                            zone.x = float(x)
                            zone.y = float(y)
                            zone.label = lab
                                
                            addedZones.append(zone)
                        except Exception, e:
                            if self.ErrorHandlingOption == 2:
                                _m.logbook_write("Error processing record {0}: {1}".format(currentLine, str(e)))
                            else:
                                raise
                    else:
                        try:
                            zone = network.create_centroid(cells[1])
                            zone.x = float(cells[2])
                            zone.y = float(cells[3])
                            if len(cells) >= 8:
                                zone.label = cells[7]
                            addedZones.append(zone)
                        except Exception, e:
                            if self.ErrorHandlingOption == 2:
                                _m.logbook_write("Error processing record {0}: {1}".format(currentLine, str(e)))
                            else:
                                raise
                          
        return addedZones
                   
    def _openDelimitedFile(self, filename, network, delimiter):        
        addedZones = []
        currentLine = 1
        
        with open(filename) as file:
            header = file.readline().lower()
            cells = header.split(delimiter)
            try:
                zi = cells.index('zone')
            except ValueError, ve:
                raise IOError("Delimited file must have a column labeled 'zone'")
            try:
                xi = cells.index('x')
            except ValueError, ve:
                raise IOError("Delimited file must have a column labeled 'x'")
            
            try:
                yi = cells.index('y')
            except ValueError, ve:
                raise IOError("Delimited file must have a column labeled 'y'")
            
            try:
                li = cells.index('label')
            except ValueError, ve:
                li = -1
            
            while True:
                line = file.readline()
                if line == '':
                    break
                
                currentLine += 1
                
                try:
                    cells = line.split(delimiter)
                    zone = network.create_centroid(cells[zi])
                    zone.x = float(cells[xi])
                    zone.y = float(cells[yi])
                    if li >= 0 :
                        zone.label = cells[li]
                    
                    addedZones.append(zone)
                except Exception, e:
                    if self.ErrorHandlingOption == 2:
                        _m.logbook_write("Error processing record {0}: {1}".format(currentLine, str(e)))
                    else:
                        raise
        
        return addedZones
    
    def _getUnconnectedZones(self, network):
        unconnectedZones = []
        
        for z in network.centroids():
            ol = 0
            il = 0
            
            for l in z.outgoing_links():
                ol += 1
            for l in z.incoming_links():
                il += 1
            
            if il == 0 and ol == 0:
                unconnectedZones.append(z)
        
        return unconnectedZones
    
    #####################################################################################################################
    
    def _HANDLE_ZONE(self, zone, feasibleNodes, network):
        
        '''
        First, get all of the nodes within the search radius of the zone.
        Then, remove all those nodes which create connectors that cross boundaries.
        Finally, truncate the size of the set of candidate nodes.
        '''
        
        self._getCandidateNodes(zone, feasibleNodes)
        searchSetSize = len(zone._candidateNodes)
        
        self._removeCrossBoundaryConnectors(zone)
        boundedSetSize = len(zone._candidateNodes)
        
        self._truncateCandidateSet(zone)
        finalSetSize = len(zone._candidateNodes)
        
        if len(zone._candidateNodes) < 1:
            raise ObjectProcessingError("No candidate nodes were selected for zone %s. \
                        This probably means that it is completely enclosed by the boundaries \
                        shapefile. Another possible problem is that no nodes were found \
                        within the specified distance of the zone shape (if being used)." %zone.id, object=zone)
        
        distanceMatrix = self._calculateDistanceMatrix(zone)
        
        maxUtil = - float('inf') #Negative infinity
        bestConfig = None
        utils = []
        maxComponents = {}
        
        #Special handling for the case of one connector
        for node in zone._candidateNodes:
            util = self.BetaMassSum * self._getNodeMass(node)
            if util > maxUtil:
                bestConfig = [node]
                maxUtil = util
            
        
        # The number of connectors goes from 2 to the lesser of the size of the set of
        #    candidates and the maximum number of connectors.
        for setSize in range(2, min(self.MaxConnectors, len(zone._candidateNodes)) + 1):
            for configuration in combinations(zone._candidateNodes, setSize):
                utilComponents = self._calculateUtility(zone, configuration, distanceMatrix)
                util = sum([beta * param for (beta, param) in utilComponents.itervalues()])
                utils.append(util)
                
                if util > maxUtil: #Pick the configuration with the highest utility
                    bestConfig = configuration
                    maxUtil = util
                    maxComponents = dict([(key, tuple[1]) for (key, tuple) in utilComponents.iteritems()])
        
        for node in bestConfig:
            '''
            TODO:
            - Generalize default attributes for link connectors (for other jurisdictions)
            - Get the link type dynamically based on the nodes it connects to.
            '''
            outConnector = network.create_link(zone.id, node.id, self.ConnectorModeIds)
            outConnector.length = self._measureDistance(zone, node)
            outConnector.num_lanes = 2.0
            outConnector.volume_delay_func = 90
            outConnector.data2 = 40.0
            outConnector.data3 = 9999
            
            inConnector = network.create_link(node.id, zone.id, self.ConnectorModeIds)
            inConnector.length = outConnector.length
            inConnector.num_lanes = 2.0
            inConnector.volume_delay_func = 90
            inConnector.data2 = 40.0
            inConnector.data3 = 9999
        
        if len(utils) == 0:
            utils = [- float('inf')]
        
        atts = {'connectors' : len(bestConfig),
                'maxUtil' : maxUtil,
                'initialSet': searchSetSize,
                'boundSet' : boundedSetSize,
                'finalSet': finalSetSize,
                'maxUtil' : maxUtil,
                'minUtil' : min(utils),
                'meanUtil' : numpy.mean(utils),
                'medianUtil' : numpy.median(utils),
                'sDevUtil' : numpy.std(utils)}
        
        for (key, value) in maxComponents.iteritems():
            atts[key] = value
        
        return atts  
            
    
    #####################################################################################################################
    
    #----Filters and Exclusions----------------------------------------------------------------------------

    def _applyInfeasibleLinkFilter(self, attributeId): #---TASK 1
        if self.InfeasibleLinkSelector == "" or self.InfeasibleLinkSelector == None:
            self._tracker.completeTask() 
            return
        else:
            spec = {
                    "result": attributeId,
                    "expression": "1",
                    "aggregation": None,
                    "selections": {
                                   "link": self.InfeasibleLinkSelector
                                   },
                    "type": "NETWORK_CALCULATION"
                    }
        tool = None
        try:
            tool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
        except Exception, e:
            tool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
        
        self._tracker.runTool(tool, spec, scenario=self.Scenario)
        #tool(spec, Scenario=self.Scenario)
    
    def _getFeasibleNodesGreedy(self, network, attributeId):
        '''
        Excludes nodes which are connected to at least one flagged link.
        '''
        
        minx = float('inf')
        miny = float('inf')
        maxx = float('-inf')
        maxy = float('-inf')
        
        feasibleNodes = []
        for node in network.regular_nodes():
            flagged = 0
            for link in node.incoming_links():
                flagged += link[attributeId]
            for link in node.outgoing_links():
                flagged += link[attributeId]
                
            if flagged == 0:
                feasibleNodes.append(node)
                x, y = node.x, node.y
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
        
        extents = minx - 1.0, miny - 1.0, maxx + 1.0, maxy + 1.0
        index = _spindex.GridIndex(extents)
        
        for node in feasibleNodes:
            p = _g.Point(node.x, node.y)
            node._geometry = p
            
            index.insertPoint(node)
        
        return index, len(feasibleNodes)
        
    def _getFeasibleNodesReluctant(self, network, attributeId):
        '''
        Excludes nodes which are only connected to flagged links
        '''
        minx = float('inf')
        miny = float('inf')
        maxx = float('-inf')
        maxy = float('-inf')
        
        feasibleNodes = []
        for node in network.regular_nodes():
            flagged = 0
            total = 0
            for link in node.incoming_links():
                flagged += link[attributeId]
                total += 1
            for link in node.outgoing_links():
                flagged += link[attributeId]
                total += 1
            if flagged < total:
                feasibleNodes.append(node)
                
                x, y = node.x, node.y
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
        
        extents = minx - 1.0, miny - 1.0, maxx + 1.0, maxy + 1.0
        index = _spindex.GridIndex(extents)
        
        for node in feasibleNodes:
            p = _g.Point(node.x, node.y)
            node._geometry = p
            
            index.insertPoint(node)
        
        return index, len(feasibleNodes)
    
    #----Candidate Node Functions--------------------------------------------------------------------
    
    def _getCandidateNodes(self, zone, feasibleNodes):
        if zone._geometry != None:
            self._searchByPoly(zone, feasibleNodes)
        else:
            self._searchByPoint(zone, feasibleNodes)
    
    def _searchByPoly(self, zone, feasibleNodes):
        '''
        Gets a list of all network nodes within the specified distance from the edge of
        the zone's boundary.
        '''
        buffer = zone._geometry.buffer(self.SearchRadius, resolution=2)
        
        candidateNodes = {}
        
        for node in feasibleNodes.queryPolygon(buffer):
            if not buffer.contains(node._geometry):
                continue #Skip over nodes indexed nearby but not contained within the polygon
            candidateNodes[node] = self._measureDistance(node, zone)
        
        zone._candidateNodes = candidateNodes #Attach candidate nodes to the zone
        
    def _searchByPoint(self, zone, feasibleNodes):
        '''
        Gets a list of all network nodes within the specified radius of the zone centroid,
        with at least one node in the list.
        '''
        
        minDistance = float('inf') #positive infinity
        closestNode = None
        candidateNodes = {}
        
        for node in feasibleNodes.queryCircle(zone.x, zone.y, self.SearchRadius):
            dist = self._measureDistance(node, zone)
            if dist < self.SearchRadius/1000: # compare distance (in km) to SearchRadius (in m)
                candidateNodes[node] = dist
        try:
            for node in feasibleNodes.nearestToPoint(zone.x, zone.y):
                dist = self._measureDistance(node, zone)
                if dist < minDistance: 
                    minDistance = dist
                    closestNode = node
        except IndexError: #Expected if the zone is outside the bounds of the feasible node set
            pass 
        
        #if no nodes are found within the search radius, select closest node
        if len(candidateNodes) == 0 and closestNode != None:
            candidateNodes[closestNode] = minDistance
        
        zone._candidateNodes = candidateNodes 
    
    def _removeCrossBoundaryConnectors(self, zone):
        '''
        Removes from the set of candidate nodes those which cross boundaries.
        '''
        
        if self._Boundaries == None: #If no boundaries have been loaded, skip this step.
            return 
        
        # Filters the zone's candidate nodes
        zone._candidateNodes = dict([(node, dist) for (node, dist) in zone._candidateNodes.items() if self._checkForCrossing(node, zone)])
        
    def _checkForCrossing(self, node, zone):
        geom = _g.LineString([(zone.x, zone.y),(node.x, node.y)])
        for boundary in self._Boundaries.queryLineString(geom):
            if geom.intersects(boundary): return False
        return True
    
    def _truncateCandidateSet(self, zone):
        '''
        Truncates the set of candidate nodes to the maximum set size by
        removing the farthest candidates.
        '''
        
        if len(zone._candidateNodes) <= self.MaxCandidates:
            return
        
        sorter = [(dist, node) for (node, dist) in zone._candidateNodes.items()]            
        sorter.sort() # List of tuples get sorted by their first element
        
        while len(sorter) > self.MaxCandidates:
            q = sorter.pop()
        
        zone._candidateNodes = dict((node, dist) for dist, node in sorter)
        
    
    #-----Utility Metric Functions--------------------------------------------------------------------------
        
    ####################################################################################################
        
    def _calculateUtility(self, zone, configuration, distanceMatrix):
        '''
        The main function for calculating the utility of a combination of candidate nodes.
        '''
        
        return {'mass' : (self.BetaMassSum, self._calculateMassSum(configuration)), 
                'radialDist' : (self.BetaRadialDist, self._calculateRadialDistribution(zone, configuration)), 
                'lengthSDev' : (self.BetaLengthStdDev, self._calculateLengthDistribution(zone, configuration)),
                'gravity' : (self.BetaGravity, self._calculateGravityTerm(distanceMatrix, configuration))}
        
        #return self.BetaMassSum * mass + self.BetaRadialDist * rd + self.BetaLengthStdDev * lnsd \
                #+ self.BetaGravity * grav
    
    ####################################################################################################
    
    def _calculateMassSum(self, configuration):
        sum = 0
        for node in configuration:
            sum += self._getNodeMass(node)
        
        return sum
    
    def _calculateRadialDistribution(self, zone, configuration):
        '''
        Measures the aggregated squared differences between the angles formed by the
        candidate connectors and that of the ideal. For example, a perfect distribution
        for four connectors would have all angles = 90 degrees, with a value of 0.
        '''
        bearings = []
        for node in configuration:
            bearings.append(self._getSegmentBearing(zone, node))
            
        bearings.sort()
        
        angleSum = 0
        total = 2
        idealAngle = 2 * math.pi / len(configuration)
        
        iter = bearings.__iter__()
        prevB = iter.next()
        for B in iter:
            a = B - prevB
            if a < 0:
                a += math.pi * 2
                
            angleSum += ((idealAngle - a) * (idealAngle - a))
            total += 1 
            prevB = B
        a = bearings[0] - prevB
        if a < 0:
            a += math.pi * 2
        angleSum += ((idealAngle - a) * (idealAngle - a))
        
        return (angleSum / total)
    
    def _calculateDistanceMatrix(self, zone):
        dm = {}
        for iNode in zone._candidateNodes.iterkeys():
            im = {}
            for jNode in zone._candidateNodes.iterkeys():
                if iNode == jNode:
                    continue
                
                d = self._measureDistance(iNode, jNode)
                if d == 0:
                    print "Zero distance found: %s -> %s" %(iNode, jNode)
                    d = 0.0001
                    
                im[jNode] = d
            dm[iNode] = im
        
        return dm
    
    def _calculateGravityTerm(self, distanceMatrix, configuration):
        sum = 0.0
        #count = 0
        
        #Iterate through the unique pairings of all nodes in the configuration.
        for pair in combinations(configuration, 2): 
            #m0 = self._getNodeMass(pair[0])
            #m1 = self._getNodeMass(pair[1])
            d = distanceMatrix[pair[0]][pair[1]]
            
            sum += 1 / (d*d)
            
            #count += 1
        
        return sum # Return the sum
        #return sum / count #Return the average 
    
    def _calculateLengthDistribution(self, zone, configuration):
        '''
        Gets the normalized standard deviation of connector lengths in
        the configuration. 
        '''
        lengths = []
        sum = 0
        for node in configuration:
            l = zone._candidateNodes[node]
            lengths.append(l)
            sum += l
        
        mean = sum / len(configuration)
        
        return numpy.std(lengths) / mean
    
    def _measureDistance(self, node1, node2):
        return _straightLineDist(node1.x, node1.y, node2.x, node2.y) / 1000.0
        
    def _getSegmentBearing(self, zone, node):
        rad = math.atan2(node.x - zone.x, node.y - zone.y)
        if rad < 0:
            return rad + math.pi * 2
        return rad
    
    def _calcMaxADist(self, n):
        ia = 2 * math.pi / n
        return (n * pow(ia,2) - 4 * math.pi * ia + pow(2 * math.pi, 2)) / n
    
    #----Miscellaneous Functions
    
    def _getNodeMass(self, node):
        if self.MassAttribute:# != None:
            return node[self.MassAttribute.name]
        else:
            return 1
    
#---------------------------------------------------------------------------------------------

class ObjectProcessingError(Exception):
    
    def __init__(self, message="", object=None, attributes={}):
        self.message = message
        self.object = object
        self.atts = attributes
    
    def __str__(self):
        return self.message

class SummaryReport():
    
    def __init__(self):
        self.connectorHistogramData = {}
        self.initSetHistogrmDara = {}
        self.boundSetHistogramData = {}
        self.finalSetHistogramData = {}
        self.zones = 0
        self.errors = 0
    
    def addZoneData(self, atts):
        self.zones += 1
        
        try:    
            self.connectorHistogramData[atts['connectors']] += 1
        except KeyError, ke:
            self.connectorHistogramData[atts['connectors']] = 1
            self.connectorHistogramData[atts['connectors'] + 1] = 0

        try:    
            self.initSetHistogrmDara[atts['initialSet']] += 1
        except KeyError, ke:
            self.initSetHistogrmDara[atts['initialSet']] = 1
            
        try:    
            self.boundSetHistogramData[atts['boundSet']] += 1
        except KeyError, ke:
            self.boundSetHistogramData[atts['boundSet']] = 1
            
        try:    
            self.finalSetHistogramData[atts['finalSet']] += 1
        except KeyError, ke:
            self.finalSetHistogramData[atts['finalSet']] = 1
    
    def addError(self):
        self.errors += 1
    
    def render(self):
        summaryReport = _m.PageBuilder(title="Summary Report")
        
        summaryReport.add_text_element("<b>Zones added : {0}\
                                    <br>Errors skipped: {1}".format(self.zones, self.errors))
        summaryReport.add_chart(chart_data_series=[{'title' : 'frequency',
                                                    'data' : self._convertMapToDataSeries(self.connectorHistogramData)}],
                                title="Histogram of Number of Connectors",
                                chart_type='bar',
                                x_label='number of connectors')
        summaryReport.add_chart(chart_data_series=[{'title' : "initial",
                                                    'data' : self._convertMapToDataSeries(self.initSetHistogrmDara)},
                                                   {'title' : 'bounded',
                                                    'data' : self._convertMapToDataSeries(self.boundSetHistogramData)},
                                                   {'title' : "final",
                                                    'data' : self._convertMapToDataSeries(self.finalSetHistogramData)}],
                                title="Histogram of Size of Set of Candidate Nodes",
                                x_label="set size",
                                chart_type='bar',
                                show_table=True)
        
        return summaryReport.render()
    
    def _convertMapToDataSeries(self, dataMap):
        dataSeries = []
        for tuple in dataMap.iteritems():
            dataSeries.append(tuple)
        return dataSeries

class FullReport():
    
    def __init__(self, filepath):
        self.path = filepath
        self.header = ["Zone"]
        self.lines = []
    
    def addZoneData(self, zoneId, atts):
        line = str(zoneId)
        for key in atts.iterkeys():
            if not key in self.header:
                self.header.append(key)
        for i in range(1, len(self.header)):
            field = self.header[i]
            if field not in atts: #for the case of one connector
                line += ",N/A"
            else:
                line += ",%s" %atts[field]
        self.lines.append(line)
    
    def export(self):      
        with open(self.path, 'w') as writer:
            # Write the header
            writer.write(self.header[0])
            for h in self.header:
                writer.write(",%s" %h)
                
            for line in self.lines:
                writer.write("\n%s" %line)
