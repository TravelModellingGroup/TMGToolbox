#---LICENSE----------------------
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
Export Transit Line Boardings

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-06-10 by pkucirek
    
    1.0.0 Documented and published on 2014-06-11
    
    1.0.1 Added XTMF interface
    
'''

import inro.modeller as _m

from html import HTML
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExtractTransitLineBoardings(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    LineAggrgeationFile = _m.Attribute(str)
    ReportFile = _m.Attribute(str)
    
    WriteIndividualRoutesFlag = _m.Attribute(bool)
    ReportErrorsToLogbookFlag = _m.Attribute(bool)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.WriteIndividualRoutesFlag = True
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Boardings v%s" %self.version,
                     description="Extracts total boardings for each transit line and exports \
                         them in a CSV file. Optionally, lines can be aggregated using an \
                         external file (two-column CSV).",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='ReportFile',
                           title="Report file",
                           file_filter= "*.csv",
                           window_type='save_file')
        
        pb.add_header("AGGREGATION FILE")
        
        pb.add_select_file(tool_attribute_name='LineAggrgeationFile',
                           title="Line aggregation file:",
                           window_type='file',
                           file_filter= "*.csv",
                           note="<font color='green'><b>Optional: \
                            </b></font>Aggregation file contains two columns with no headers, matching transit\
                            <br>line IDs to their aliases or groups in another data source (e.g., TTS line IDs). The\
                            <br>first column must be Emme transit line IDs. Any errors are skipped.")        
        
        pb.add_checkbox(tool_attribute_name= 'WriteIndividualRoutesFlag',
                        label= "Write individual routes?",
                        note= "Write individual routes that are not found in the aggregation file. \
                            <br>This is the default behaviour if no aggregation file is specified.")
        
        pb.add_checkbox(tool_attribute_name= 'ReportErrorsToLogbookFlag',
                        label= "Report errors to the Logbook?",
                        note= "Write a report if there are lines referenced in the aggregation file but are not in the network.")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        if (tool.check_agg_file())
        {
            $("#WriteIndividualRoutesFlag").prop('disabled', false);
            $("#ReportErrorsToLogbookFlag").prop('disabled', false);
        } else {
            $("#WriteIndividualRoutesFlag").prop('disabled', true);
            $("#ReportErrorsToLogbookFlag").prop('disabled', true);
        }

        $("#LineAggrgeationFile").bind('change', function()
        {
            $(this).commit();
            
            $("#WriteIndividualRoutesFlag").prop('disabled', false);
            $("#ReportErrorsToLogbookFlag").prop('disabled', false);
        });
    });
</script>""" %pb.tool_proxy_tag)
        
        return pb.render()
    
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
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type= bool)
    def check_agg_file(self):
        return bool(self.LineAggrgeationFile)
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, ReportFile, LineAggrgeationFile):
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.ReportFile = ReportFile
        if LineAggrgeationFile:
            self.LineAggrgeationFile = LineAggrgeationFile
            self.ReportErrorsToLogbookFlag = False
            self.WriteIndividualRoutesFlag = False
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if not self.Scenario.has_transit_results:
                raise Exception("Scenario %s has no transit results" %self.Scenario)
            
            if self.LineAggrgeationFile:
                groupLines = self._LoadAggregationFile()
            else: groupLines = {}
            
            fileKeys, networkKeys = self._CheckAggregation(groupLines)
            
            self._ExportResults(fileKeys, networkKeys, groupLines)

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadAggregationFile(self):
        with open(self.LineAggrgeationFile) as reader:
            groupLines = {}
            
            for line in reader:
                if line.isspace(): continue
                lineId, groupId = line.strip().split(',')
                
                if groupId in groupLines: groupLines[groupId].add(lineId)
                else: groupLines[groupId] = set([lineId])
            
            return groupLines
    
    def _CheckAggregation(self, groupLines):
        fileLineIDs = set()
        for IDs in groupLines.itervalues():
            for id in IDs: fileLineIDs.add(id)
        
        data = _util.fastLoadTransitLineAttributes(self.Scenario, ['headway'])
        networkLineIDs = set(data.keys())
        
        linesMissingInNetwork = fileLineIDs - networkLineIDs
        linesNotInAggregationFile = networkLineIDs - fileLineIDs
        
        if self.ReportErrorsToLogbookFlag and len(linesMissingInNetwork) > 0:
            self._WriteErrorReport(linesMissingInNetwork)
        
        if self.WriteIndividualRoutesFlag:
            return list(groupLines.keys()), list(linesNotInAggregationFile)
        else:
            return list(groupLines.keys()), []
    
    def _WriteErrorReport(self, linesMissingInNetwork):
        h = HTML()
        t = h.table()
        tr = t.tr()
        tr.th("Line ID")
        for id in linesMissingInNetwork:
            tr = t.tr()
            tr.td(str(id))
        
        pb = _m.PageBuilder(title="Lines not in network report")
        
        pb.wrap_html("Lines references in file but not in network", body= str(t))
        
        _m.logbook_write("Error report", value= pb.render())
    
    def _ExportResults(self, fileKeys, networkKeys, groupLines):
        fileKeys.sort()
        networkKeys.sort()
        
        lineBoardings = _util.fastLoadSummedSegmentAttributes(self.Scenario, ['transit_boardings'])
        
        with open(self.ReportFile, 'w') as  writer:
            writer.write("Line,Boardings")
            
            for key in fileKeys:
                boardings = 0.0
                if key in groupLines:
                    lineIDs = groupLines[key]
                    
                    for id in lineIDs:
                        if not id in lineBoardings: continue
                        boardings += lineBoardings[id]['transit_boardings']
                
                writer.write("\n%s,%s" %(key, boardings))
            
            for key in networkKeys:
                boardings = 0.0
                if key in lineBoardings:
                    boardings = lineBoardings[key]['transit_boardings']
                writer.write("\n%s,%s" %(key, boardings))
                