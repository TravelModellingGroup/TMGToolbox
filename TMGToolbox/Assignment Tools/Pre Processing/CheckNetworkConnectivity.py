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
''Check Network Connectivity

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Runs an auto and/or transit assignment to find nodes with 
     connectivity issues (for given modes). Identifies fountain nodes (that 
     go out), sink nodes (that only come in), and orphan nodes (that neither 
     come in nor go out). Islands are NOT identified. 
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-04-24 by pkucirek
    
    1.0.0 Tested and published on 2014-05-02
    
    1.0.1 Added searchability to mode selectors.
    
'''

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from html import HTML
from numpy import array
from numpy import where

import inro.modeller as _m

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
EMME_VERSION = _util.getEmmeVersion(float) 

##########################################################################################################

class CheckNetworkConnectivity(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 3 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    AutoModeIds = _m.Attribute(_m.ListType)
    TransitModeIds = _m.Attribute(_m.ListType)
    
    PreserveAssignmentFlag = _m.Attribute(bool)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    xtmf_AutoModeString = _m.Attribute(str)
    xtmf_TransitModeString = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.AutoModeIds = []
        self.TransitModeIds = []
        
        self.PreserveAssignmentFlag = True
    
    def page(self):
        
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Check Network Connectivity v%s" %self.version,
                     description="Runs an auto and/or transit assignment to find nodes with \
                         connectivity issues (for given modes). Identifies fountain nodes (that \
                         go out), sink nodes (that only come in), and orphan nodes (that neither \
                         come in nor go out). Islands are <b>not</b> identified. \
                         <br><br><b>Temporary storage requirements:</b> One scenario (if needed), \
                         one matrix for transit times, and one matrix for <em>each auto mode \
                         selected</em>.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        autoModeKeyval = {}
        for id, type, descr in _util.getScenarioModes(self.Scenario, ['AUTO', 'AUX_AUTO']):
            val = " - ".join([id, "(%s)" %type, descr])
            autoModeKeyval[id] = val
        
        transitModeKeyval = {}
        for id, type, descr in _util.getScenarioModes(self.Scenario, ['TRANSIT', 'AUX_TRANSIT']):
            val = " - ".join([id, "(%s)" %type, descr])
            transitModeKeyval[id] = val
            
        pb.add_select(tool_attribute_name= 'AutoModeIds', keyvalues= autoModeKeyval,
                      title= 'Select Auto Mode(s)', note= "Leave empty to disable checking for auto connectivity.",
                      searchable= True)
        
        pb.add_select(tool_attribute_name= 'TransitModeIds', keyvalues= transitModeKeyval,
                      title= "Select Transit Modes", note= "Leave empty to disable checking for transit connectivity.",
                      searchable= True)
        
        pb.add_checkbox(tool_attribute_name= 'PreserveAssignmentFlag',
                        label= "Preserve existing assignment results?",
                        note= "Space for a temporary scenario is required if checked.")
        
                #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            
            $("#AutoModeIds")
                .empty()
                .append(tool.preload_auto_modes())
            inro.modeller.page.preload("#AutoModeIds");
            $("#AutoModeIds").trigger('change')
            
            $("#TransitModeIds")
                .empty()
                .append(tool.preload_transit_modes())
            inro.modeller.page.preload("#TransitModeIds");
            $("#TransitModeIds").trigger('change')
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            nFountains, nSinks, nOrphans = self._Execute()
            
            if (nFountains + nSinks + nOrphans) > 0:
                tup = (nFountains, nSinks, nOrphans, self.Scenario)
                msg = "Found %s fountain node(s), %s sink node(s), and %s orphan node(s) in scenario %s." %tup
                msg += " Check logbook for details."
            else:
                msg = "No network connectivity issues were found."

            self.tool_run_msg = _m.PageBuilder.format_info(msg)
            
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        _MODELLER.desktop.refresh_needed(False)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with _util.tempMatrixMANAGER(matrix_type= 'SCALAR', description= "Zero demand matrix") \
                    as demandMatrix:
                with self._tempScenarioMANAGER():
                    dataTuples = []
                    
                    if self.AutoModeIds:
                        self._CheckAutoConnectivity(demandMatrix.id, dataTuples)
                    
                    if self.TransitModeIds:
                        self._CheckTransitConnectivity(demandMatrix.id, dataTuples)
                    
                    
                    
                    totalFountains = set()
                    totalSinks = set()
                    totalOrphans = set()
                    for type, modes, fountains, sinks, orphans in dataTuples:
                        for node in fountains: totalFountains.add(node)
                        for node in sinks: totalSinks.add(node)
                        for node in orphans: totalOrphans.add(node)
                    
                    nFountains = len(totalFountains)
                    nSinks = len(totalSinks)
                    nOrphans = len(totalOrphans)
                    
                    if (nFountains + nSinks + nOrphans) > 0:
                        self._WriteReport(dataTuples)
                        return nFountains, nSinks, nOrphans
                    else: return 0,0,0
                    
    ##########################################################################################################   
    
    @contextmanager
    def _tempScenarioMANAGER(self):
        hasCopy = False
        bank = _MODELLER.emmebank
        
        if self.Scenario.has_transit_results or self.Scenario.has_traffic_results:
            if self.PreserveAssignmentFlag:
                copyId = _util.getAvailableScenarioNumber()
                
                originalScenario = self.Scenario
                copy = bank.copy_scenario(self.Scenario.id, copyId, False, False, False)
                _m.logbook_write("Copied scenario %s to temporary scenario %s" %(originalScenario, copyId))
                
                self.Scenario = copy
                hasCopy = True
        
        try:
            yield
        finally:
            if hasCopy:
                self.Scenario = originalScenario
                bank.delete_scenario(copyId)
                _m.logbook_write("Deleted temporary scenario %s." %copyId)
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _CheckAutoConnectivity(self, demandMatrixId, dataTuples):
        managers = []
        for modeId in self.AutoModeIds:
            managers.append(_util.tempMatrixMANAGER(description= "Temp times matrix for mode %s" %modeId))
        
        with nested(*managers) as timesMatrices:
            classInfo = []
            for i, modeId in enumerate(self.AutoModeIds):
                classInfo.append((modeId, timesMatrices[i].id))
            
            print "Auto assignment prepared."
            self._RunAutoAssignment(demandMatrixId, classInfo)
            print "Auto assignment complete."
            
            bank = _MODELLER.emmebank
            for modeId, matrixId in classInfo:
                matrix = bank.matrix(matrixId)
                
                
                fountains, sinks, orphans = self._GetDisconnectedNodes(matrix)
                dataTuples.append(("Auto", [modeId], fountains, sinks, orphans))
                
                print "Processed auto mode %s" %modeId
                
    def _RunAutoAssignment(self, demandMatrixId, classInfo):
        
        classes = []
        for modeId, timesMatrixId in classInfo:
            classSpec = {
                        "mode": modeId,
                        "demand": demandMatrixId,
                        "generalized_cost": None,
                        "results": {
                            "link_volumes": None,
                            "turn_volumes": None,
                            "od_travel_times": {
                                "shortest_paths": timesMatrixId
                            }
                        },
                        "analysis": {
                            "analyzed_demand": None,
                            "results": {
                                "od_values": None,
                                "selected_link_volumes": None,
                                "selected_turn_volumes": None
                            }
                        }
                    }
            classes.append(classSpec)
        
        spec = {
                "type": "STANDARD_TRAFFIC_ASSIGNMENT",
                "classes": classes,
                "performance_settings": {
                    "number_of_processors": 1
                },
                "background_traffic": None,
                "path_analysis": None,
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "stopping_criteria": {
                    "max_iterations": 0,
                    "relative_gap": 0,
                    "best_relative_gap": 0,
                    "normalized_gap": 0
                }
            }
        
        tool = _MODELLER.tool('inro.emme.traffic_assignment.standard_traffic_assignment')
        
        tool(spec, self.Scenario)
    
    def _CheckTransitConnectivity(self, demandMatrixId, dataTuples):
        with _util.tempMatrixMANAGER(description="Transit times matrix") as timesMatrix:
            
            self._RunTransitAssignment(demandMatrixId, timesMatrix.id)
            print "Transit assignment complete."
            
            matrix = _MODELLER.emmebank.matrix(timesMatrix.id)
            fountains, sinks, orphans = self._GetDisconnectedNodes(matrix)
            
            dataTuples.append(("Transit", self.TransitModeIds, fountains, sinks, orphans))
            print "Processed transit connectivity."
    
    def _RunTransitAssignment(self, demandMatrixId, timesMatrixId):
        spec = {
            "modes": self.TransitModeIds,
            "demand": demandMatrixId,
            "waiting_time": {
                "headway_fraction": 0.5,
                "effective_headways": "hdw",
                "spread_factor": 1,
                "perception_factor": 1
            },
            "boarding_time": {
                "penalty": 0,
                "perception_factor": 1
            },
            "aux_transit_time": {
                "perception_factor": 1
            },
            "od_results": {
                "transit_times": timesMatrixId,
                "total_waiting_times": None,
                "first_waiting_times": None,
                "boarding_times": None,
                "by_mode_subset": None
            },
            "strategy_analysis": None,
            "type": "STANDARD_TRANSIT_ASSIGNMENT"
        }
        
        tool = _MODELLER.tool('inro.emme.transit_assignment.standard_transit_assignment')
        
        tool(spec, scenario= self.Scenario)
    
    def _GetDisconnectedNodes(self, matrix):
        matrixData = matrix.get_data(self.Scenario)
        
        numpyArray = array(matrixData.raw_data)
        infinity = float('1E20') - 0.1 #'Emme infinity' is 1e+20
        pMatches, qMatches = where(numpyArray > infinity)
        
        originIndices, destinationIndices = matrixData.indices
        nZones = len(originIndices) - 1 #Subtract one since each zone is always connected to itself
        
        zoneEnds = {}
        for pIndex, qIndex in _util.itersync(pMatches, qMatches):
            p = originIndices[pIndex]
            q = destinationIndices[qIndex]
            
            if p in zoneEnds:
                zoneEnds[p][0] += 1
            else:
                zoneEnds[p] = [1, 0]
            
            if q in zoneEnds:
                zoneEnds[q][1] += 1
            else:
                zoneEnds[q] = [0, 1]

        fountains, sinks, orphans = [], [], []
        
        for zone, counts in zoneEnds.iteritems():
            outCount, inCount = counts
            
            if inCount == nZones:
                if outCount == nZones:
                    orphans.append(zone)
                else:
                    fountains.append(zone)
            elif outCount == nZones:
                sinks.append(zone)
        
        return fountains, sinks, orphans
    
    def _WriteReport(self, dataTuples):
        pb = _m.PageBuilder("Network Connectivity Report")
        
        for type, modes, fountains, sinks, orphans in dataTuples:
            self._AddReportSection(pb, type, modes, fountains, sinks, orphans)
        
        _m.logbook_write("Network connectivity report", value= pb.render())
    
    def _AddReportSection(self, pb, type, modes, fountains, sinks, orphans):
        modes = [str(mode) for mode in modes]
        
        h = HTML()
        
        plural = ''
        if len(modes) > 1: plural = "s"
        sectionTitle = "{0} results for mode{1} {2!s}".format(type, plural, modes)
        
        #h.h3(sectionTitle)
        
        nFountains = len(fountains)
        nSinks = len(sinks)
        nOrphans = len(orphans)
        
        if nFountains > 0:
            
            plural = ''
            if nFountains > 1: plural = 's'
            title= "Found %s fountain node%s:" %(nFountains, plural)
            
            t = h.table()
            tr = t.tr()
            tr.th(title)
            
            for node in fountains:
                t.tr().td(str(node))
            
        if nSinks > 0:
            
            plural = ''
            if nSinks > 1: plural = 's'
            title= "Found %s sink node%s:" %(nSinks, plural)
            
            t = h.table()
            tr = t.tr()
            tr.th(title)
            
            for node in sinks:
                t.tr().td(str(node))
                
        if nOrphans > 0:
            
            plural = ''
            if nOrphans > 1: plural = 's'
            title= "Found %s orphan node%s:" %(nOrphans, plural)
            
            t = h.table()
            tr = t.tr()
            tr.th(title)
            
            for node in orphans:
                t.tr().td(str(node))
        
        pb.wrap_html(sectionTitle, body= str(h))
            
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def preload_auto_modes(self):
        options = []
        h = HTML()
        for id, type, description in _util.getScenarioModes(self.Scenario,  ['AUTO', 'AUX_AUTO']):
            text = "%s - %s" %(id, description)
            options.append(str(h.option(text, value= id)))
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def preload_transit_modes(self):
        options = []
        h = HTML()
        for id, type, description in _util.getScenarioModes(self.Scenario,  ['AUX_TRANSIT', 'TRANSIT']):
            text = "%s - %s" %(id, description)
            options.append(str(h.option(text, value= id)))
        return "\n".join(options)
        