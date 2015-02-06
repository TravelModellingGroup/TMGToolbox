'''
    Copyright 2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Create Time Period Networks

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    0.1.1 Created on 2015-01-19 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

def naiveAggregation(departures, start, end):
    deltaTime = end - start
    
    numDep = len(departures)
    
    return deltaTime / numDep

def averageAggregation(departures, start, end):
    
    sum = 0
    counter = 0
    
    if len(departures) == 1:
        return end - start
    
    iter = departures.__iter__()
    prevDep = iter.next()
    for dep in iter:
        headway = dep - prevDep
        counter += 1
        sum += headway
        prevDep = dep
    
    return sum / counter

class CreateTimePeriodNetworks(_m.Tool()):
    
    version = '0.1.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    BaseScenario = _m.Attribute(_m.InstanceType)
    NewScenarioNumber = _m.Attribute(int)
    NewScenarioDescription = _m.Attribute(str)
    
    TransitServiceTableFile = _m.Attribute(str)
    AggTypeSelectionFile = _m.Attribute(str)
    
    TimePeriodStart = _m.Attribute(int)
    TimePeriodEnd = _m.Attribute(int)

    DefaultAgg = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        self.DefaultAgg = 'n'
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Time Period Network v%s" %self.version,
                     description="Creates a network for use in a given time period, from a \
                         24-hour base network and corresponding transit service table. \
                         Line speeds and headways are calculated from the service table.\
                         Transit lines with no service in the time period are removed.\
                         Headway calculations are performed based on a choice of\
                         aggregation type. Agg type by line is loaded in from a file\
                         which can be generated using the Create Aggregation\
                         Selection File tool.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)
        
        with pb.add_table(False) as t:
        
            with t.table_cell():
                pb.add_new_scenario_select(tool_attribute_name='NewScenarioNumber',
                                           title="New scenario to create")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='NewScenarioDescription',
                                title="Description",
                                size=40)
        
        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='TransitServiceTableFile',
                           window_type='file', file_filter='*.csv',
                           title="Transit service table",
                           note="Requires three columns:\
                               <ul><li>emme_id</li>\
                               <li>trip_depart</li>\
                               <li>trip_arrive</li></ul>")
        
        pb.add_select_file(tool_attribute_name='AggTypeSelectionFile',
                           window_type='file', file_filter='*.csv',
                           title="Aggregation Type Selection",
                           note="Requires two columns:\
                               <ul><li>emme_id</li>\
                               <li>agg_type</li></ul>")

        pb.add_header("TOOL INPUTS")
        
        keyval1 = {'n':'Naive', 'a':'Average'}
        pb.add_radio_group(tool_attribute_name='DefaultAgg', 
                           keyvalues= keyval1,
                           title= "Default Aggregation Type",
                           note="Used if line not in\
                               agg selection file")

        with pb.add_table(False) as t:
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='TimePeriodStart',
                                size=4,
                                title="Time period start",
                                note="In integer hours e.g. 2:30 PM = 1430")
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='TimePeriodEnd',
                                size=4,
                                title="Time period end",
                                note="In integer hours e.g. 2:30 PM = 1430")
                
        return pb.render()
    
    ##########################################################################################################
    # allows for the tool to be called from another tool    
    def __call__(self, baseScen, newScenNum, newScenDescrip, serviceFile, aggFile, defAgg, start, end):
        self.tool_run_msg = ""
        self.TRACKER.reset()

        self.BaseScenario = baseScen
        self.NewScenarioNumber = newScenNum
        self.NewScenarioDescription = newScenDescrip
        self.TransitServiceTableFile = serviceFile
        self.AggTypeSelectionFile = aggFile
        self.DefaultAgg = defAgg
        self.TimePeriodStart = start
        self.TimePeriodEnd = end
        
        try:            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")

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
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            network = self.BaseScenario.get_network()
            self.TRACKER.completeTask()
            print "Loaded network"
            
            start = self._ParseIntTime(self.TimePeriodStart)
            end = self._ParseIntTime(self.TimePeriodEnd)
            
            badIdSet = self._LoadServiceTable(network, start, end).union(self._LoadAggTypeSelect(network))
            self.TRACKER.completeTask()
            print "Loaded service table"
            if len(badIdSet) > 0:
                print "%s transit line IDs were not found in the network and were skipped." %len(badIdSet)
                pb = _m.PageBuilder("Transit line IDs not in network")
                
                pb.add_text_element("<b>The following line IDs were not found in the network:</b>")
                
                for id in badIdSet:
                    pb.add_text_element(id)
                
                _m.logbook_write("Some IDs were not found in the network. Click for details.",
                                 value=pb.render())
            
            self._ProcessTransitLines(network, start, end)
            print "Done processing transit lines"
            
            newScenario = _MODELLER.emmebank.copy_scenario(self.BaseScenario.id, self.NewScenarioNumber)
            newScenario.title = self.NewScenarioDescription
            
            print "Publishing network"
            network.delete_attribute('TRANSIT_LINE', 'trips')
            network.delete_attribute('TRANSIT_LINE', 'aggtype')
            newScenario.publish_network(network)
            

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _ParseIntTime(self, i):
        try:
            hours = i / 100
            minutes = i % 100
        
            return hours * 3600.0 + minutes * 60.0
        except Exception, e:
            raise IOError("Error parsing time %s: %s" %(i, e)) 
    
    def _ParseStringTime(self, s):
        try:
            hms = s.split(self.COLON)
            if len(hms) != 3: raise IOError()
            
            hours = int(hms[0])
            minutes = int(hms[1])
            seconds = int(hms[2])
            
            return hours * 3600.0 + minutes * 60.0 + float(seconds)
        except Exception, e:
            raise IOError("Error parsing time %s: %s" %(s, e)) 

    def _ParseAggType(self, a):
        choiceSet = ('n', 'a')
        try:
            agg = a[0].lower()
            if agg not in choiceSet: raise IOError()
            else : return agg
        except Exception, e:
            raise IOError("You must select either naive or average as an aggregation type %s: %s" %(a, e))                    
            
    def _LoadServiceTable(self, network, start, end):
        network.create_attribute('TRANSIT_LINE', 'trips', None)
        
        bounds = _util.FloatRange(start, end)
        badIds = set()
        
        with open(self.TransitServiceTableFile) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)
            
            emmeIdCol = cells.index('emme_id')
            departureCol = cells.index('trip_depart')
            arrivalCol = cells.index('trip_arrive')
            
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                id = cells[emmeIdCol]
                transitLine = network.transit_line(id)
                
                if transitLine == None:
                    badIds.add(id)
                    continue #Skip and report
                
                try:
                    departure = self._ParseStringTime(cells[departureCol])
                    arrival = self._ParseStringTime(cells[arrivalCol])
                except Exception, e:
                    print "Line " + num + " skipped: " + str(e)
                    continue
                
                if not departure in bounds: continue #Skip departures not in the time period
                
                trip = (departure, arrival)
                if transitLine.trips == None: transitLine.trips = [trip]
                else: transitLine.trips.append(trip)
        
        return badIds

    def _LoadAggTypeSelect(self, network):
        network.create_attribute('TRANSIT_LINE', 'aggtype', None)
        
        badIds = set()
        
        with open(self.AggTypeSelectionFile) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)
            
            emmeIdCol = cells.index('emme_id')
            aggCol = cells.index('agg_type')
            
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                id = cells[emmeIdCol]
                transitLine = network.transit_line(id)
                
                if transitLine == None:
                    badIds.add(id)
                    continue #Skip and report
                
                try:
                    aggregation = self._ParseAggType(cells[aggCol])
                except Exception, e:
                    print "Line " + num + " skipped: " + str(e)
                    continue
                                
                if transitLine.aggtype == None: transitLine.aggtype = aggregation
        
        return badIds
        
    def _ProcessTransitLines(self, network, start, end):              
        bounds = _util.FloatRange(0.01, 1000.0)
        
        toDelete = set()
        self.TRACKER.startProcess(network.element_totals['transit_lines'])
        for line in network.transit_lines():
            #Pick aggregation type for given line
            if line.aggtype == 'n':
                aggregator = naiveAggregation
            elif line.aggtype == 'a':
                aggregator = averageAggregation
            elif self.DefaultAgg == 'n':
                aggregator = naiveAggregation
                _m.logbook_write("Default aggregation was used for line %s" %(line.id))
            else:
                aggregator = averageAggregation
                _m.logbook_write("Default aggregation was used for line %s" %(line.id))

            if not line.trips: #Line trips list is empty or None
                toDelete.add(line.id)
                self.TRACKER.completeSubtask()
                continue
            
            #Calc line headway
            departures = [dep for dep, arr in line.trips]
            departures.sort()
            headway = aggregator(departures, start, end) / 60.0 #Convert from seconds to minutes
            
            if not headway in bounds: print "%s: %s" %(line.id, headway)
            line.headway = headway
            
            #Calc line speed
            sumTimes = 0
            for dep, arr in line.trips: sumTimes += arr - dep
            avgTime = sumTimes / len(line.trips) / 3600.0 #Convert from seconds to hours
            length = sum([seg.link.length for seg in line.segments()]) #Given in km
            speed = length / avgTime #km/hr
            if not speed in bounds: print "%s: %s" %(line.id, speed)
            line.speed = speed
            
            self.TRACKER.completeSubtask()
            
        for id in toDelete:
            network.delete_transit_line(id)
        self.TRACKER.completeTask()
        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    