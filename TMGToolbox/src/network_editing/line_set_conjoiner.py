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
Line Set Conjoiner

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    This tool takes in a set of transit lines that are to be
    combined into one single, "looped" line. EMME no longer 
    restricts such loops, so for the purpose of cleaning
    networks, this is a useful tool.
    
    It will allow for the combination of trips within a Combined
    Service Table, as well, so that the Create Transit Time
    Period tool will still be viable after a cleaning overhaul of 
    a base network.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-01-29 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import csv
from operator import itemgetter
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class LineSetConjoiner(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
                
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    BaseScenario = _m.Attribute(_m.InstanceType)
    
    TransitServiceTableFile = _m.Attribute(str)
    NewServiceTableFile = _m.Attribute(str)
    LineSetFile = _m.Attribute(str)
    #UnusedTripTableFile = _m.Attribute(str)

    GlobalBuffer = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        self.FailureFlag = False
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        self.GlobalBuffer = 5

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Line Set Conjoiner v%s" %self.version,
                     description="Takes a set of transit lines and combines them \
                         into single, looped lines. Also adjusts the Combined Service\
                         Table accordingly so that accurate headways can be generated \
                         later using the Create Transit Time Period tool.\
                         Each line in the input file must be an sequential list of \
                         transit line IDs. \
                         <br><b>This tool is irreversible. Make sure to copy your \
                         scenarios prior to running!</b>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)

        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='TransitServiceTableFile',
                           window_type='file', file_filter='*.csv',
                           title="Transit service table",
                           note="Requires three columns:\
                               <ul><li>emme_id</li>\
                               <li>trip_depart</li>\
                               <li>trip_arrive</li></ul>")

        pb.add_select_file(tool_attribute_name='LineSetFile',
                           window_type='file', file_filter='*.csv',
                           title="Line sets",
                           note="Input line IDs must be ordered")

        pb.add_select_file(tool_attribute_name='NewServiceTableFile',
                           window_type='save_file', file_filter='*.csv',
                           title="New output service table")

        #pb.add_select_file(tool_attribute_name='UnusedTripTableFile',
        #                   window_type='save_file', file_filter='*.csv',
        #                   title="Trips not used in any conjoined trip")

        pb.add_header("TOOL INPUTS")

        pb.add_text_box(tool_attribute_name='GlobalBuffer',
                        size=7,
                        title='Allowable layover buffer (in minutes)')

        return pb.render()

    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
            if self.FailureFlag:
                msg = "Tool complete with errors. Please see logbook for details."
            else:
                msg = "Done."
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise        
        
        self.tool_run_msg = _m.PageBuilder.format_info(msg)

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            network = self.BaseScenario.get_network()
            print "Loaded network"

            lineIds, lineList = self._ReadSetFile()
            print "Loaded lines"

            unchangedSched, changedSched = self._LoadServiceTable(lineList)
            print "Loaded service table"

            #newLineIds = self._ConcatenateLines(network, lineIds)
            #print "Lines concatenated"    
                                
            moddedSched, removedSched, leftoverSched = self._ModifySched(network, lineIds, changedSched)
            self._WriteNewServiceTable(unchangedSched, moddedSched, removedSched, leftoverSched)
            print "Created modified service table"
            
            #self._WriteUnusedTrips()
            #print "Created unused trip table"

            print "Publishing network"
            self.BaseScenario.publish_network(network)
            self.TRACKER.completeTask()



    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    
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

    def _RevertToString(self, f):
        try:
            hourRemain = f % 3600
            hoursNum = (f - hourRemain) / 3600
            minuteRemain = hourRemain % 60
            minutesNum = (hourRemain - minuteRemain) / 60
            secondsNum = minuteRemain

            return "{:.0f}".format(hoursNum) + self.COLON + "{:0>2,.0f}".format(minutesNum) + self.COLON + "{:0>2,.0f}".format(secondsNum)
        except Exception, e:
            raise IOError("Error parsing time %s: %s" %(f, e)) 
        
    def _ReadSetFile(self):
        with open(self.LineSetFile) as reader:
            lines = []
            fullLines = []
            for num, line in enumerate(reader):
                set = []
                cells = line.strip().split(self.COMMA)
                for item in cells:
                    if item:
                        set.append(item)
                lines.append(set)
                fullLines.extend(set)

        return lines, fullLines

    # From the first line in a set, create a suitable id for the full, concatenated line
    def _GetNewId(self, originalId, network):
        if ord('0') <= ord(originalId[-1]) <= ord('9'): # eg like some Durham lines (D100, etc.)
            newId = originalId + 'c'
            if network.transit_line(newId) == None:                
                return newId
            else:
                raise Exception("Could not create a valid ID")
        elif ord('a') <= ord(originalId[-1]) <= ord('z'):
            if ord('A') <= ord(originalId[-2]) <= ord('Z'): # eg like TTC lines (T005Ab, etc.)
                for count in range(1,80): #allows for a full dual alphabet cycle
                    if ord(originalId[-2]) + count > ord('Z'):
                        if ord(originalId[-2]) + count > ord('z'):
                            raise Exception("Could not create a valid ID") #fails if it needs to pass z
                        elif ord(originalId[-2]) + count < ord('a'): #skip over the symbols between Z and a 
                            continue
                    newId = originalId[:-2] + unichr(ord(originalId[-2]) + count) + 'c'
                    newIdA = originalId[:-2] + unichr(ord(originalId[-2]) + count) + 'a' #need to make sure there is not a similarly named line
                    newIdB = originalId[:-2] + unichr(ord(originalId[-2]) + count) + 'b'
                    if network.transit_line(newId) == None and network.transit_line(newIdA) == None and network.transit_line(newIdB) == None:
                        return newId #if it's valid, use the name. Otherwise, keep advancing throught the alphabet
            else: # eg like some Durham lines (D100w, etc.)
                newId = originalId[:-1] + 'c'
                if network.transit_line(newId) == None:                
                    return newId
        elif ord('A') <= ord(originalId[-1]) <= ord('Z'): # eg like Brampton (B001B, etc.)
            for count in range(1,26): #allows for a full alphabet cycle
                    if ord(originalId[-1]) + count > ord('Z'):
                        raise Exception("Could not create a valid ID") #fails if it needs to pass Z
                    newId = originalId[:-1] + unichr(ord(originalId[-1]) + count)
                    if network.transit_line(newId) == None:                
                        return newId
        else:
            raise Exception("Could not create a valid ID")

    def _ConcatenateLines(self, network, lineSet):
        try:
            newId = self._GetNewId(lineSet[0], network)
            _util.lineConcatenator(network, lineSet, newId)
            _m.logbook_write("Line set %s concatenated" %(lineSet))
        except Exception:
            self.FailureFlag = True
            _m.logbook_write("This line set is not valid: %s" %(lineSet))
            return None
        return newId      
            
    def _LoadServiceTable(self, lineList):                      
        with open(self.TransitServiceTableFile) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)
            
            emmeIdCol = cells.index('emme_id')
            departureCol = cells.index('trip_depart')
            arrivalCol = cells.index('trip_arrive')

            unchangedSched = {}
            changedSched = {}

            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                id = cells[emmeIdCol]
                departure = cells[departureCol]
                arrival = cells[arrivalCol]                                
                trip = (self._ParseStringTime(departure), self._ParseStringTime(arrival))

                if id in lineList:
                    if id in changedSched:
                        changedSched[id].append(trip)
                    else:
                        changedSched[id] = [trip]
                else:
                    if id in unchangedSched:
                        unchangedSched[id].append(trip)
                    else:
                        unchangedSched[id] = [trip]

            for id, tripList in changedSched.iteritems(): #ordering the trips so that we can run through them sequentially later
                tripList.sort()

            for id, tripList in unchangedSched.iteritems():
                tripList.sort()
                                
        return unchangedSched, changedSched

    def _ModifySched(self, network, lineIds, changedSched):
        '''
        This function allows us to chain together acceptable trips.
        These are returned in the modSched dictionary, which is carried forward
        to the new Service Table. Trips used to make the modSched are removed
        from changedSched, which is essentially the choice set. removedSched
        allows easy reporting later of those trips not chosen for use.
        In one type of case (an unsuccessful attempt to create a modified trip,
        followed by no more successful trips in that lineset), skipped trips
        cannot be added to removedSched. Therefore, the full list of trips
        not utilized in the modified schedule is the combination of removedSched
        and changedSched.
        '''
        with _m.logbook_trace("Attempting to modify schedule and concatenate lines"):
            modSched = {}
            removedSched = {}
            for lineSet in lineIds:
                newId = self._ConcatenateLines(network, lineSet)
                if not newId:
                    continue # if the concatenation fails, skip schedule modification for that line set
                modSched[newId] = []
                for tripNum, trips in enumerate(changedSched[lineSet[0]]):#loop through trips of first line        
                    for num, line in enumerate(lineSet):
                        if num == 0:
                            currentArrival = trips[1] #set first arrival to check
                        elif num == (len(lineSet) - 1):
                            # when we get to the final line in the set, set new trip in the modded schedule
                            # that corresponds to the departure of the first line and the final value
                            # for arrival (ie. the last line's arrival time)
                            modSched[newId].append((trips[0], newArrival))
                            break 
                        nextLine = lineSet[num + 1]
                        check = self._CheckSched(currentArrival, changedSched[nextLine])
                        if check:
                            newArrival = check
                            # looping through trips in the next line
                            # removes the trip with the newArrival
                            # and removes all trips up to that
                            toDelete = []
                            for items in changedSched[nextLine]:
                                if items[1] == newArrival:
                                    toDelete.append(items)
                                    break
                                else:
                                    # keep track of all ignored trips
                                    if nextLine in removedSched:
                                        removedSched[nextLine].append(items)
                                    else:
                                        removedSched[nextLine] = [items]
                                    toDelete.append(items)
                            for m in toDelete:
                                # remove ignored and chosen trips from choice set
                                changedSched[nextLine].remove(m)
                            currentArrival = newArrival # move the current arrival forward in time

                        else:
                            _m.logbook_write("In line set %s, departure %s not valid" %(lineSet, self._RevertToString(trips[0])))
                            # keep track of the removed invalid trip
                            if lineSet[0] in removedSched:
                                removedSched[lineSet[0]].append(trips)
                            else:
                                removedSched[lineSet[0]] = [trips]                            
                            break
                del changedSched[lineSet[0]] #remove trips from choice set

        return modSched, removedSched, changedSched
            
    def _CheckSched(self, arrival, sched):
        newArrival = ''
        buffer = 60 * self.GlobalBuffer
        for items in sched: # loop through schedule for next line in set
            # check if arrival of line n is within buffer for departures of line n+1
            if 0 <= items[0] - arrival <= buffer:
                newArrival = items[1] # if successfully finds a departure, sets next arrival to use
                break
            elif items[0] - arrival >= buffer:
                # doesn't cause a failure, but does report the issue in _ModifySched
                break
        return newArrival #will return an empty string if it completes the loop or exits due to exceeding buffer


    def _WriteNewServiceTable(self, unchangedSched, modSched, sched, leftover):
        f = ['emme_id', 'trip_depart', 'trip_arrive']
        with open(self.NewServiceTableFile, 'wb') as csvfile:
            tableWrite = csv.writer(csvfile, delimiter = ',')
            tableWrite.writerow(['emme_id', 'trip_depart', 'trip_arrive'])
            fullSched = unchangedSched.copy()
            fullSched.update(modSched)
            for schedKey in sorted(fullSched):
                for item in fullSched[schedKey]: 
                    value = [schedKey]
                    value.extend([self._RevertToString(item[0]),self._RevertToString(item[1])])
                    tableWrite.writerow(value)
            # can't use update() to combine the two dictionaries, since we may have overlapping keys
            for schedKey in sorted(sched):
                for item in sorted(sched[schedKey]): 
                    value = [schedKey, self._RevertToString(item[0]),self._RevertToString(item[1])]
                    tableWrite.writerow(value)
            for schedKey in sorted(leftover):
                for item in sorted(leftover[schedKey]): 
                    value = [schedKey, self._RevertToString(item[0]),self._RevertToString(item[1])]
                    tableWrite.writerow(value)

    #def _WriteUnusedTrips(self, sched, leftover):
    #    f = ['emme_id', 'trip_depart', 'trip_arrive']
    #    with open(self.UnusedTripTableFile, 'wb') as csvfile:
    #        tableWrite = csv.writer(csvfile, delimiter = ',')
    #        tableWrite.writerow(['emme_id', 'trip_depart', 'trip_arrive'])
    #        # can't use update() to combine the two dictionaries, since we may have overlapping keys
    #        for schedKey in sorted(sched):
    #            for item in sorted(sched[schedKey]): 
    #                value = [schedKey, self._RevertToString(item[0]),self._RevertToString(item[1])]
    #                tableWrite.writerow(value)
    #        for schedKey in sorted(leftover):
    #            for item in sorted(leftover[schedKey]): 
    #                value = [schedKey, self._RevertToString(item[0]),self._RevertToString(item[1])]
    #                tableWrite.writerow(value)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg