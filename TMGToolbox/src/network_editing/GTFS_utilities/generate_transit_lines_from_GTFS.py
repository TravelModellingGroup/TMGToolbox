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
Generate Transit Lines from GTFS

    Authors: Peter Kucirek

    Latest revision by: pkucirek
    
    
    Generates transit line ITINERARIES ONLY from GTFS data. Assumes that most GTFS
    stop are matched to a group ID (GID) and each GID is matched to a network node.
    Both tables are inputs for this tool.
    
    Additionally, the 'routes' file of the GTFS feed must define two additional
    columns: 'emme_id' (defining up to the first 5 characters of the Emme transit
    line id), and 'emme_vehicle' (defining the Emme vehicle number used by the line).
    For convenience, if both 'routes.txt' and 'routes.csv' are defined, the CSV 
    file will be used (since this is likely to be edited using Excel).
    
    During the map-matching process, this tool will attempt to find the shortest
    path between two nodes in an itinerary, up to a maximum of 10 links. Any line
    requiring a path of more than 5 links will be flagged for review. Lines requiring
    longer paths will not be added at all (but will be reported in the logbook).
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
    0.0.2 Added feature to take line names from routes file. Also added the feature to flag lines
        with short itineraries for checking. Also fixed a minor bug where the scenario title wasn't
        being applied
    
    0.0.3 Added feature to select a link attribute for prioritized links. Prioritized links are assumed
        to have triple the speed.
    
    0.0.4 Modified the tool to calculate shortest-paths including turn penalties (& restrictions). This runs a bit
        slower.
    
    0.0.5 Fixed a bug where the optional 'direction_id' in the trips file causes the tool to crash if omitted.
    
    0.0.6 Upgraded to using a better, turn-restricted shortest-path algorithm. 
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_editing = _MODELLER.module('tmg.common.network_editing')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

GtfsModeMap = {'s' : '0',
               'l' : '0',
               'm' : '1',
               'r' : '2',
               'b' : '3',
               'q' : '3',
               'g' : '3'}

def last(list):
    if len(list) == 0:
        return None
    return list[len(list) - 1]

class GenerateTransitLinesFromGTFS(_m.Tool()):
    
    version = '0.0.6'
    tool_run_msg = ""
    number_of_tasks = 8 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    NewScenarioId = _m.Attribute(str)
    NewScenarioTitle = _m.Attribute(str)
    MaxNonStopNodes = _m.Attribute(int)
    LinkPriorityAttributeId = _m.Attribute(unicode)
    
    GtfsFolder = _m.Attribute(str)
    Stop2NodeFile = _m.Attribute(str)
    
    LineServiceTableFile = _m.Attribute(str)
    PublishFlag = _m.Attribute(bool)
    
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.MaxNonStopNodes = 15
        self.PublishFlag = True
        self.NewScenarioTitle = self.Scenario.title
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Generate Transit Line Itineraries from GTFS v%s" %self.version,
                     description="<p class='tmg_left'>Generates transit line ITINERARIES ONLY from GTFS data. \
                        Assumes that most GTFS are matched to a network node. Unmatched stops are 'invisible'.\
                        <br><br>Additionally, the 'routes' file of the GTFS feed must define two additional\
                        columns: 'emme_id' (defining up to the first 5 characters of the Emme transit\
                        line id), and 'emme_vehicle' (defining the Emme vehicle number used by the line).\
                        For convenience, if both 'routes.txt' and 'routes.csv' are defined, the CSV \
                        file will be used (since this is likely to be edited using Excel) \
                        An optional column 'emme_descr' can also be provided to define lines' descriptions.\
                        <br><br>During the map-matching process, this tool will attempt to find the shortest\
                        path between two nodes in an itinerary, up to a specified maximum. Any line\
                        with a path having more than 5 links between any two stops will be flagged for review. \
                        Lines requiring paths longer than the maximum will not be added at all (but will be \
                        reported in the logbook). \
                        Lines which result in a repeated node (looped lines) will also be flagged for review.\
                        <br><br><b>Tip: </b>Press CTRL+K to bring up the Python Console to view tool progress.</p>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Base Scenario',
                               allow_none=False)
    
        pb.add_text_box(tool_attribute_name='MaxNonStopNodes',
                        size=3,
                        title="Maximum Inter-stop Links")

        keyvals = dict([(att.id, "{id} - LINK - {desc}".format(id=att.id, desc=att.description))
                        for att in self.Scenario.extra_attributes() if att.type == 'LINK'])
        pb.add_select(tool_attribute_name='LinkPriorityAttributeId',
                      keyvalues=keyvals,
                      title="Link Priority Attribute",
                      note="A factor applied to link speeds.\
                      <br><font color='red'><b>Warning: </b></font>\
                      It is recommended to use an attribute with \
                      a default value of 1.0.")
        
        pb.add_header("GTFS INPUTS")
        
        pb.add_select_file(tool_attribute_name='GtfsFolder',
                           window_type='directory',
                           title="GTFS Folder")

        pb.add_select_file(tool_attribute_name='Stop2NodeFile',
                           window_type='file',
                           file_filter='*.csv',
                           title="Stop-to-Node File",
                           note="<b>First Column</b>: Stop ID\
                           <br><b>Second Column</b>: Node ID")
        
        pb.add_header("TOOL OUTPUTS")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_new_scenario_select(tool_attribute_name='NewScenarioId',
                                   title="New Scenario",
                                   note="The id of the copied scenario")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='NewScenarioTitle',
                                size=60, multi_line=True,
                                title="New Scenario Title")
        
        pb.add_select_file(tool_attribute_name='LineServiceTableFile',
                           window_type='save_file',
                           file_filter='*.csv',
                           title="Transit Service Table")
        
        pb.add_checkbox(tool_attribute_name='PublishFlag',
                        label="Publish network? Leave unchecked for debugging.")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        $("#LinkPriorityAttributeId")
             .prepend(0,"<option value='-1' selected='selected'>None</option>")
             .prop("selectedIndex", 0)
             .trigger('change')
        //alert($("#LinkPriorityAttributeId").selectedIndex);
        
        var tool = new inro.modeller.util.Proxy(%s) ;
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            var options = tool.getExtraAttributes();
            
            $("#LinkPriorityAttributeId")
                .empty()
                .append("<option value='-1' selected='selected'>None</option>")
                .append(options)
                //.data("combobox")._refresh_width();
            inro.modeller.page.preload("#LinkPriorityAttributeId");
            $("#LinkPriorityAttributeId").trigger('change');
        });
        
        $("#PublishFlag").bind('change', function()
        {
            $(this).commit();
            if ($(this).is(":checked")) {
                $("#NewScenarioId").prop("disabled", false);
                $("#NewScenarioTitle").prop("disabled", false);
            } else {
                $("#NewScenarioId").prop("disabled", true);
                $("#NewScenarioTitle").prop("disabled", true);
            }
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        
        
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
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            routes = self._LoadCheckGtfsRoutesFile()
            self.TRACKER.completeTask()
            
            network = self.Scenario.get_network()
            print "Loaded network"
            self.TRACKER.completeTask()
            
            stops2nodes = self._LoadStopNodeMapFile(network)
            
            trips = self._LoadTrips(routes)
            
            self._LoadPrintStopTimes(trips, stops2nodes)
            
            with open(self.LineServiceTableFile, 'w') as writer:
                self._GenerateLines(routes, stops2nodes, network, writer)
            
            if self.PublishFlag:
                copy = _MODELLER.emmebank.copy_scenario(self.Scenario.id, self.NewScenarioId)
                copy.title = self.NewScenarioTitle
                copy.publish_network(network, True)
            self.TRACKER.completeTask()

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _LoadCheckGtfsRoutesFile(self):
        routesPath = self.GtfsFolder + "/routes.csv"
        if not _path.exists(routesPath):
            routesPath = self.GtfsFolder + "/routes.txt"
            if not _path.exists(routesPath):
                raise IOError("Folder does not contain a routes file")
        
        with _util.CSVReader(routesPath) as reader:
            for label in ['emme_id', 'emme_vehicle', 'route_id', 'route_long_name']:
                if label not in reader.header:
                    raise IOError("Routes file does not define column '%s'" %label)
            
            useLineNames = False
            if 'emme_descr' in reader.header:
                useLineNames = True
            
            emIdSet = set()
            routes = {}
            
            for record in reader.readlines():
                emmeId = record['emme_id'][:5]
                if emmeId in emIdSet:
                    raise IOError("Route file contains duplicate id '%s'" %emmeId)
                
                emIdSet.add(emmeId)
                if useLineNames:
                    descr = record['emme_descr']
                    route = Route(record, description= descr[:17])
                else:
                    route = Route(record)
                routes[route.route_id] = route      
        msg = "%s routes loaded from transit feed" %len(routes)
        print msg
        _m.logbook_write(msg)
        return routes
    
    def _LoadStopNodeMapFile(self, network):
        stops2nodes = {}
        with open(self.Stop2NodeFile) as reader:
            reader.readline() #Toss the header
            
            for line in reader.readlines():
                line = line.strip()
                cells = line.split(',')
                if cells[1] == '0':
                    self.TRACKER.completeSubtask()
                    continue #Assume no mapping exists for this stop
                if network.node(cells[1]) == None:
                    raise IOError("Mapping error: Node %s does not exist" %cells[1])
                stops2nodes[cells[0]] = cells[1]
            self.TRACKER.completeTask()
        msg = "%s stop-node pairs loaded." %len(stops2nodes)
        print msg
        _m.logbook_write(msg)
        return stops2nodes
    
    def _LoadTrips(self, routes):
        trips = {}
        with _util.CSVReader(self.GtfsFolder + "/trips.txt") as reader:
            self.TRACKER.startProcess(len(reader))
            directionGiven = 'direction_id' in reader.header
            for record in reader.readlines():
                route = routes[record['route_id']] #Assume the GTFS feed is well-formatted & contains all routes
                if directionGiven:
                    direction = record['direction_id']
                else:
                    direction = None
                trip = Trip(record['trip_id'], route, direction)
                route.trips[trip.id] = trip
                trips[trip.id] = trip
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
        msg = "%s trips loaded." %len(trips)
        print msg
        _m.logbook_write(msg)
        
        return trips
    
    def _LoadPrintStopTimes(self, trips, stops2nodes):
        count = 0
        with nested(_util.CSVReader(self.GtfsFolder + "/stop_times.txt"),
                    open(self.GtfsFolder + "/stop_times_emme_nodes.txt", 'w'))\
                     as (reader, writer):
            
            s = reader.header[0]
            for i in range(1, len(reader.header)):
                s += "," + reader.header[i]
            writer.write(s)
            writer.write(",emme_node")
            
            self.TRACKER.startProcess(len(reader))
            for record in reader.readlines():
                try:
                    trip = trips[record['trip_id']]
                except KeyError, ke:
                    continue
                index = int(record['stop_sequence'])
                stopId = record['stop_id']
                stopTime = StopTime(stopId, record['departure_time'], record['arrival_time'])
                trip.stopTimes.append((index, stopTime))
                
                if stopId in stops2nodes:
                    node = stops2nodes[stopId]
                else:
                    node = None
                writer.write("\n%s,%s" %(record, node))
                count += 1
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
                
        msg = "%s stop times loaded" %count
        print msg
        _m.logbook_write(msg)
        print "Stop times file updated with emme node mapping."
        pb = _m.PageBuilder(title="Link to updated stop times file")
        pb.add_link(self.GtfsFolder + "/stop_times_emme_nodes.txt")
        _m.logbook_write("Link to updated stop times file",
                         value=pb.render())
    
    def _GenerateLines(self, routes, stops2nodes, network, writer):
        #This is the main method
        linesToCheck = []
        failedSequences = []
        skippedStopIds = {}
        
        writer.write("emme_id,trip_depart,trip_arrive")
        
        # Setup the shortest-path algorithm
        if self.LinkPriorityAttributeId != None:
            def speed(link):
                factor = link[self.LinkPriorityAttributeId]
                if factor == 0:
                    return 0
                if link.data2 == 0:
                    return 30.0 * factor
                return link.data2 * factor
        else:
            def speed(link):
                if link.data2 == 0:
                    return 30.0 * factor
                return link.data2 * factor
        algo = _editing.AStarLinks(network, link_speed_func=speed)
        algo.max_degrees = self.MaxNonStopNodes
        functionBank = self._GetModeFilterMap(network)
        
        self.TRACKER.startProcess(len(routes))
        lineCount = 0
        print "Starting line itinerary generation"
        for route in routes.itervalues():
            baseEmmeId = route.emme_id
            vehicle = network.transit_vehicle(route.emme_vehicle)
            if vehicle == None:
                raise Exception("Cannot find a vehicle with id=%s" %route.emme_vehicle)
            if GtfsModeMap[vehicle.mode.id] != route.route_type:
                print "Warning: Vehicle mode of route {0} ({1}) does not match suggested route type ({2})".\
                    format(route.route_id, vehicle.mode.id, route.route_type)
            filter = functionBank[vehicle.mode]
            algo.link_filter = filter
            
            #Collect all trips with the same stop sequence
            tripSet = self._GetOrganizedTrips(route)         
            
            #Create route profile
            branchNumber = 0
            seqCount = 1
            for seq, trips in tripSet.iteritems():
                stop_itin = seq.split(';')
                
                #Get node itinerary
                node_itin = self._GetNodeItinerary(stop_itin, stops2nodes, network, skippedStopIds)
            
                if len(node_itin) < 2: #Must have at least two nodes to build a route
                    #routeId, branchNum, error, seq
                    failedSequences.append((baseEmmeId, seqCount, "too few nodes", seq))
                    seqCount += 1
                    continue
                
                #Generate full, mode-constrained path
                iter = node_itin.__iter__()
                prevNode = iter.next()
                full_itin = [prevNode]
                seg_stops = []
                breakFlag = False
                longRoute = False
                for node in iter:
                    path = algo.calcPath(prevNode, node)
                    #path = _editing.calcShortestPath2(prevNode, node, filter, self.MaxNonStopNodes, calc)
                    #path = _util.calcShortestPath(network, vehicle.mode, prevNode, node, self.MaxNonStopNodes, calc=calc)
                    if not path:
                        #routeId, branchNum, error, seq
                        msg = "no path between %s and %s by mode %s" %(prevNode, node, vehicle.mode)
                        failedSequences.append((baseEmmeId, seqCount, msg, seq))
                        breakFlag = True
                        seqCount += 1
                        break
                    flag = True
                    if len(path) > 5:
                        longRoute = True
                    for link in path:
                        full_itin.append(link.j_node)
                        seg_stops.append(flag)
                        flag = False
                    prevNode = node
                
                seg_stops.append(True) #Last segment should always be a stop.
                if breakFlag:
                    seqCount += 1
                    continue
                
                
                #Try to create the line
                id = baseEmmeId + chr(branchNumber + 65)
                if trips[0].direction == '0':
                    id += 'a'
                elif trips[0].direction == '1':
                    id += 'b'
                
                d = ""
                if route.description:
                    d = "%s %s" %(route.description, chr(branchNumber + 65))
                
                try:
                    line = network.create_transit_line(id, vehicle, full_itin)
                    line.description = d
                    #Ensure that nodes which aren't stops are flagged as such.
                    for i, stopFlag in enumerate(seg_stops):
                        seg = line.segment(i)
                        seg.allow_alightings = stopFlag
                        seg.allow_boardings = stopFlag
                        seg.dwell_time = 0.01 * float(stopFlag) # No dwell time if there is no stop, 0.01 minutes if there is a stop
                    branchNumber += 1
                    lineCount += 1
                except Exception, e:
                    print "Exception for line %s: %s" %(id, e)
                    #routeId, branchNum, error, seq
                    failedSequences.append((baseEmmeId, seqCount, str(e), seq))
                    seqCount += 1
                    continue
                seqCount += 1
                
                if longRoute:
                    linesToCheck.append((id, "Possible express route: more than 5 links in-between one or more stops."))
                
                #Check for looped routes
                nodeSet = set(full_itin)
                for node in nodeSet:
                    count = full_itin.count(node)
                    if count > 1:
                        linesToCheck.append((id, "Loop detected. Possible map matching error."))
                        break
                
                if len(node_itin) <5:
                    linesToCheck.append((id, "Short route: less than 4 total links in path"))
                
                #Write to service table
                for trip in trips:
                    writer.write("\n%s,%s,%s" %(id, trip.stopTimes[0][1].departure_time, trip.lastStopTime()[1].arrival_time))
            print "Added route %s" %route.emme_id
                
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        
        msg = "Done. %s lines were successfully created." %lineCount
        print msg
        _m.logbook_write(msg)
        
        _m.logbook_write("Skipped stops report", value = self._WriteSkippedStopsReport(skippedStopIds))
        print "%s stops skipped" %len(skippedStopIds)
        _m.logbook_write("Failed sequences report", value = self._WriteFailedSequencesReport(failedSequences))
        print "%s sequences failed" %len(failedSequences)
        
        if self.PublishFlag:
            _m.logbook_write("Lines to check report", value = self._WriteLinesToCheckReport(linesToCheck))
            print "%s lines were logged for review." %len(linesToCheck)
    
    def _GetOrganizedTrips(self, route):
        tripSet = {}
        for trip in route.trips.itervalues():
            trip.stopTimes.sort()
            
            seq = [st[1].stop_id for st in trip.stopTimes]
            
            seqs = seq[0]
            for i in range(1, len(seq)):
                seqs += ";" + seq[i]
            
            if seqs in tripSet:
                tripSet[seqs].append(trip)
            else:
                tripSet[seqs] = [trip]
        return tripSet
    
    def _GetModeFilterMap(self, network):
        map = {}
        
        modes = [mode for mode in network.modes() if mode.type == 'TRANSIT']
        
        for mode in modes:
            if self.LinkPriorityAttributeId == None:
                func = ModeOnlyFilter(mode)
                map[mode] = func
            else:
                func = ModeAndAttributeFilter(mode, self.LinkPriorityAttributeId)
                map[mode] = func
        return map 
    
    def _GetNodeItinerary(self, stop_itin, stops2nodes, network, skippedStopIds):
        node_itin = []
        for stopId in stop_itin:
            if not stopId in stops2nodes:
                if stopId in skippedStopIds:
                    skippedStopIds[stopId] += 1
                else:
                    skippedStopIds[stopId] = 1 
                continue #skip this stop
            nodeId = stops2nodes[stopId]
            node = network.node(nodeId)
            if node == None:
                if stopId in skippedStopIds:
                    skippedStopIds[stopId] += 1
                else:
                    skippedStopIds[stopId] = 1
                print "Could not find node %s" %nodeId
                continue #Could not find the node for this stop
            if last(node_itin) == node:
                continue #Immediate duplicates might occur due to stop grouping process
            node_itin.append(node)
        return node_itin
    
    def _WriteSkippedStopsReport(self, skippedStopIds):
        pb = _m.PageBuilder()
        stopData = []
        countData = []
        for x, item in enumerate(skippedStopIds.iteritems()):
            stop, count = item
            stopData.append((x, stop))
            countData.append((x, count))
        cds = [{'title': "Stop ID", 'data': stopData},
               {'title': "Count", 'data': countData}]
        opt = {'table': True, 'graph': False}
        pb.add_chart_widget(cds, options=opt, title="Skipped Stops Table", note="'Count' is the number of times skipped.")
        return pb.render()
            
    def _WriteFailedSequencesReport(self, failedSequences):
        pb = _m.PageBuilder()
        idData = []
        branchData = []
        errorData = []
        seqData = []
        for x, item in enumerate(failedSequences): #Not a map
            routeId, branchNum, error, seq = item
            idData.append((x, routeId))
            branchData.append((x, branchNum))
            errorData.append((x, error))
            seqData.append((x, seq))
        cds = [{'title': "Route ID", 'data': idData},
               {'title': "Branch #", 'data': branchData},
               {'title': "Error", 'data': errorData},
               {'title': "Stop Sequence", 'data': seqData}]
        opt = {'table': True, 'graph': False}
        pb.add_chart_widget(cds, options=opt, title="Failed Sequences Table", note="Stop sequence refers to GTFS stop ids.")
        return pb.render()
    
    def _WriteLinesToCheckReport(self, linesToCheck):
        pb = _m.PageBuilder()
        idData = []
        checkData = []
        for x, item in enumerate(linesToCheck):
            id, reason = item
            idData.append((x, id))
            checkData.append((x, reason))
        cds = [{'title': "Line ID", 'data': idData},
               {'title': "Check Reason", 'data': checkData}]
        opt = {'table': True, 'graph': False}
        pb.add_chart_widget(cds, options=opt, title="Emme Lines to Check")
        return pb.render()
            
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def getExtraAttributes(self):
        keyvals = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'LINK':
                continue
            descr = "{id} - LINK - {desc}".format(id=att.id, desc=att.description)
            keyvals[att.id] = descr
        
        options = []
        for tuple in keyvals.iteritems():
            html = '<option value="%s">%s</option>' %tuple
            options.append(html)
            
        return "\n".join(options)
        
### PRIVATE CLASSES ########################################################

class Trip():
    def __init__(self, id, route, directionId):
        self.id = id
        self.route = route #backwards pointer to the route object
        self.direction = directionId
        
        self.stopTimes = []
    
    def lastStopTime(self):
        return self.stopTimes[len(self.stopTimes) - 1]
    
class Route():
    def __init__(self, record, description=""):
        self.route_id = record['route_id']
        self.emme_id = record['emme_id']
        self.emme_vehicle = record['emme_vehicle']
        self.route_type = record['route_type']
        self.trips = {}
        self.description = description

class StopTime():
    def __init__(self, stop, depart, arrive):
        self.stop_id = stop
        self.departure_time = depart
        self.arrival_time = arrive

class ModeOnlyFilter():
    def __init__(self, mode):
        self.__mode = mode
    
    def __call__(self, link):
        return self.__mode in link.modes

class ModeAndAttributeFilter():
    def __init__(self, mode, attribute):
        self.__mode = mode
        self.__att = attribute
    
    def __call__(self, link):
        return self.__mode in link.modes and link[self.__att] != 0
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    