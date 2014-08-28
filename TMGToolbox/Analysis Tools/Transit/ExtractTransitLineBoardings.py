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
Extract Transit Line Boardings

    Authors: Peter Kucirek

    Latest revision by:@pkucirek
    
    
    Exports various attributes (including boardings) for transit lines, permitting user-specified
    aggregation and filtering. Exports to the Commented CSV format
        
'''
#---VERSION HISTORY
'''
    0.1.0 Written by @pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
_util = _m.Modeller().module('TMG2.Common.Utilities')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class ExportTransitBoardings(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    document_link = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(str)
    OutputFile = _m.Attribute(str)
    LineSelectorExpression = _m.Attribute(str)
    AggregationFile = _m.Attribute(str)
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    
    #---Internal variables
    _lineFlagAttribute = "@flag9"
    
    def __init__(self):
        #ENTER IN THE NUMBER OF TASKS. THIS WILL CRASH OTHERWISE.
        self._tracker = _util.ProgressTracker(4)
        self.ScenarioString = ""
        self.LineSelectorExpression = "all"
        self._aggregation = {}
        self.scenario = _m.Modeller().scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Transit Line Results v%s" %self.version,
                     description="<p class='tmg_left'>Produces a report of various transit line attributes, \
                     saved to a \
                     comma-separated-values (CSV) table format. Transit line results can be optionally \
                     aggregated using a two-column correspondence table, with the first column \
                     referenced to Emme transit line IDs.\
                     <br><br>For each transit line (or line grouping), the following attributes are \
                     exported:<ul class='tmg_left'>\
                     <li>Number of Emme routes (branches) in the line (=1 if no aggregation)</li>\
                     <li>Total line boardings</li>\
                     <li>Line peak volume</li>\
                     <li>Line peak volume/capacity ratio</li>\
                     <li>Weighted average of volume/capacity ratio</ul></p>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        if self.document_link != "":
            pb.add_link(self.document_link, _path.basename(self.document_link))
            
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='LineSelectorExpression',
                        title="Line filter expression:",
                        size=100,
                        multi_line=True,
                        note="<font color='green'><b>Optional: \
                            </b></font>Enter an expression to filter lines.")
        
        pb.add_select_file(tool_attribute_name='AggregationFile',
                           title="Select aggregation file:",
                           window_type='file',
                           note="<font color='green'><b>Optional: \
                            </b></font>Aggregation file contains two columns with no headers, matching transit\
                            <br>line IDs to their aliases or groups in another data source (e.g., TTS line IDs). The\
                            <br>first column must be Emme transit line IDs. Any errors are skipped.")
        
        pb.add_select_file(tool_attribute_name='OutputFile',
                           title="Output file name:",
                           window_type='save_file')
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        try:
            if self.OutputFile == None: raise NullPointerException("Output file not specified")           
            
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
        self.document_link = self.OutputFile
    
    def __call__(self, ScenarioNumber, OutputFile, LineSelectorExpression, AggregationFile):
        
        #---Setup scenario
        scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if scenario == None:
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        if not scenario.has_transit_results:
            raise Exception("Scenario %s does not have transit assignment results" %xtmf_ScenarioNumber) 
        
        self.OutputFile = OutputFile
        self.LineSelectorExpression = LineSelectorExpression
        self.AggregationFile = AggregationFile
        
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            if not self.scenario.has_transit_results:
                raise Exception("Scenario %s has no transit assignment results!" %self.scenario.id)
            if not self.OutputFile:
                raise Exception("No output file was selected!")
            
            networkCalcTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
            
            with self._lineFlagMANAGER():
                #---1 Flag relevant transit lines
                with _m.logbook_trace("Flagging lines"):
                    self._tracker.runTool(networkCalcTool, self._getLineFlagSpec(), scenario=self.scenario) # TASK 1
                
                #---2 Load aggregation file
                if self.AggregationFile != None:
                    with _m.logbook_trace("Loading aggregation file %s" %self.AggregationFile):
                        self._loadAggregationFile()
                self._tracker.completeTask() # TASK 2
                
                #---3 Process Results
                lineGroups = None
                with _m.logbook_trace("Processing results"):
                    lineGroups = self._groupLines()
                    self._tracker.completeTask() # TASK 3
                
                #---4 Export results
                with nested(_m.logbook_trace("Exporting boarding results"), open(self.OutputFile, 'w')) \
                        as (null, file): #null is actually an object but we don't actually care about it    
                    file.write("//Scenario {0}: {1} (Assigned {2})".format(self.scenario.id, 
                                                                           self.scenario.title,
                                                                           str(self.scenario.transit_assignment_timestamp)))
                    file.write("\nLineId,Branches,TotalBoardings,PeakVolume,PeakVCR,WAvgVCR")
                    
                    self._tracker.startProcess(len(lineGroups))
                    keys = lineGroups.keys()
                    keys.sort()
                    for id in keys:
                        results = lineGroups[id].getResults()
                        file.write("\n%s,%s,%s,%s,%s,%s"
                                   %(id, results['branches'],
                                     results['boardings'], results['peakVolume'],
                                     results['peakVCR'], results['wsumVCR']))
                        
                        self._tracker.completeSubtask()
        self._tracker.reset()

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _lineFlagMANAGER(self):
        # Code here is executed upon entry {
        
        self.scenario.create_extra_attribute('TRANSIT_LINE', self._lineFlagAttribute)
        _m.logbook_write("Created temporary line flag attribute '@flag9'.")
        
        # }
        try:
            yield
        finally:
            # Code here is executed in all cases. {
            self.scenario.delete_extra_attribute(self._lineFlagAttribute)
            _m.logbook_write("Deleted temporary flag attribute '@flag9'.")
            # }
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" :self.scenario.id,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _getLineFlagSpec(self):
        return {
                "result": self._lineFlagAttribute,
                "expression": "1",
                "aggregation": None,
                "selections": {
                               "transit_line": self.LineSelectorExpression
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _loadAggregationFile(self):
        self._aggregation.clear()
        with open(self.AggregationFile) as file:
            for line in file.readlines():
                cells = line.split(',')
                self._aggregation[cells[0]] = cells[1].strip()
                
    def _groupLines(self):
        network = self.scenario.get_network()
        lineSet = set([line for line in network.transit_lines() if line[self._lineFlagAttribute] != 0])
        
        
        
        lineGroups = {}
        
        for (emId, oId) in self._aggregation.iteritems():
            line = network.transit_line(emId)
            if line == None:
                _m.logbook_write("Could not find a line in the network with id '%s'. It was skipped." %emId)
                continue
            
            if not oId in lineGroups:
                lineGroup = LineGroup(oId)
                lineGroup.transit_lines.add(line)
                lineGroups[oId] = lineGroup
            else:
                lineGroups[oId].transit_lines.add(line)
            
            lineSet.remove(line)
        
        for line in lineSet:
            if line.id in lineGroups:
                _m.logbook_write("Transit line ID collision: line group with id '%s' exists in both the network and aggregation file. It was skipped." %line.id)
                continue
            lineGroup = LineGroup(str(line))
            lineGroup.transit_lines.add(line)
            lineGroups[line.id] = lineGroup
        
        # lineGroups now contains the full enummerated set of groupings of transit lines
        return lineGroups
        
                
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self._tracker.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

class LineGroup():
    
    def __init__(self, id):
        self.id = id
        self.transit_lines = set()
        
    def getResults(self):
        boardings = 0.0
        peakVolume = 0.0
        peakVCR = 0.0
        weightedVCRSum = 0.0
        totalVol = 0.0
        branches = 0
        for line in self.transit_lines:
            capacity = line.vehicle.total_capacity
            branches += 1
            for segment in line.segments():
                boardings += segment.transit_boardings
                segvol = segment.transit_volume
                vcr = segvol / capacity # By definition, capacity is always guaranteed to be > 0. Emme doesn't permit anything else.
                
                if segvol > peakVolume:
                    peakVolume = segvol
                    
                if vcr > peakVCR:
                    peakVCR = vcr
                
                weightedVCRSum += vcr * segvol
                totalVol += segvol
        
        if totalVol == 0.0: #Just in case the line group has no volume
            totalVol = 1
            weightedVCRSum = 0
            
        return {'branches' : branches,
                'boardings' : boardings,
                'peakVolume' : peakVolume,
                'peakVCR' : peakVCR,
                'wsumVCR' : weightedVCRSum / totalVol}
                
    