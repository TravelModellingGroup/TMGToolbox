#---LICENSE----------------------
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
Extract Operator Transfer Matrix

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-06-09 by pkucirek
    
    1.0.0 Published and documented on 2014-06-11
    
    1.1.0 Added in feature to just extract the walk-all-way matrix
    
    1.1.1 Fixed some documentation.
    
    1.1.2 Updated to allow for multi-threaded matrix calcs in 4.2.1+
    
'''

import inro.modeller as _m

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os.path import exists
from json import loads as _parsedict
from os.path import dirname
import tempfile as _tf
import shutil as _shutil
from multiprocessing import cpu_count

_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalculator = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
traversalAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.traversal_analysis')
networkResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.network_results')
strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
matrixCalculator = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
matrixExportTool = _MODELLER.tool('inro.emme.data.matrix.export_matrices')
EMME_VERSION = _util.getEmmeVersion(tuple)

##########################################################################################################

@contextmanager
def blankContextManager(var= None):
    try:
        yield var
    finally:
        pass

@contextmanager
def getTemporaryFolder():
    folder = _tf.mkdtemp()
    try:
        yield folder
    finally:
        _shutil.rmtree(folder)

LINE_GROUPS_ALPHA_OP = [(1, "line=B_____", "Brampton"),
                            (2, "line=HB____", "Burlington"),
                               (3, "line=D_____", "Durham"),
                               (4, "mode=gr", "GO"),
                               (5, "line=H_____", "Halton"),
                               (6, "line=W_____", 'Hamilton'),
                               (7, "line=HM____", "Milton"),
                               (8, "line=M_____", "Mississauga"),
                               (9, "line=HO____", "Oakville"),
                               (10, "line=T_____", "TTC"),
                               (11, "line=Y_____", "YRT")]
    
LINE_GROUPS_ALPHA_OP_MODE = [(1, "line=B_____", "Brampton"),
                              (2, "line=HB____", "Burlington"),
                           (3, "line=D_____", "Durham"),
                           (4, "mode=g", "GO Bus"),
                           (5, "mode=r", "GO Train"),
                           (6, "line=W_____", 'Hamilton'),
                           (7, "line=HM____", "Milton"),
                           (8, "line=M_____", "Mississauga"),
                           (9, "line=HO____", "Oakville"),
                           (10, "line=T_____ and mode=b", "TTC Bus"),
                           (11, "mode=s", "TTC Streetcar"),
                           (12, "mode=m", "TTC Subway"),
                           (14, "line=Y_____", "YRT"),
                           (13, "line=YV____", "VIVA")]

LINE_GROUPS_NCS11 = [(24, "line=B_____", "Brampton"),
                       (80, "line=D_____", "Durham"),
                       (65, "mode=g", "GO Bus"),
                       (90, "mode=r", "GO Train"),
                       (46, "line=HB____", "Burlington"),
                       (44, "line=HM____", "Milton"),
                       (42, "line=HO____", "Oakville"),
                       (60, "line=W_____", 'Hamilton'),
                       (20, "line=M_____", "Mississauga"),
                       (26, "line=T_____", "TTC"),
                       (70, "line=Y_____", "YRT")]

LINE_GROUPS_GTAMV4 = [(1, "line=B_____", "Brampton"),
                       (2, "line=D_____", "Durham"),
                       (3, "mode=g", "GO Bus"),
                       (4, "mode=r", "GO Train"),
                       (5, "line=H_____", "Halton"),
                       (6, "line=W_____", 'Hamilton'),
                       (7, "line=M_____", "Mississauga"),
                       (8, "mode=s", "Streetcar"),
                       (9, "mode=m", "Subway"),
                       (10, "line=T_____ and mode=b", "TTC Bus"),
                       (12, "line=Y_____", "YRT"),
                       (11, "line=YV____", "VIVA")]

LINE_GROUPS_GTAMV4_PREM = [(1, "line=B_____", "Brampton"),
                           (2, "line=D_____", "Durham"),
                           (3, "mode=g", "GO Bus"),
                           (4, "mode=r", "GO Train"),
                           (5, "line=H_____", "Halton"),
                           (6, "line=W_____", 'Hamilton'),
                           (7, "line=M_____", "Mississauga"),
                           (8, "mode=s", "Streetcar"),
                           (9, "mode=m", "Subway"),
                           (10, "line=T_____ and mode=b", "TTC Bus"),
                           (11, "line=T14___", "TTC Premium Bus"),
                           (13, "line=Y_____", "YRT"),
                           (12, "line=YV____", "VIVA")]

class OperatorTransferMatrix(_m.Tool()):
    
    version = '1.1.2'
    tool_run_msg = ""
    number_of_tasks = 8 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    Scenario = _m.Attribute(_m.InstanceType)
    xtmf_ScenarioNumber = _m.Attribute(int)
    DemandMatrixId = _m.Attribute(str)
    ClassName = _m.Attribute(str)
    
    ExportTransferMatrixFlag = _m.Attribute(bool)
    LineGroupOptionOrAttributeId = _m.Attribute(str)
    TransferMatrixFile = _m.Attribute(str)
    
    ExportWalkAllWayMatrixFlag = _m.Attribute(bool)
    AggregationPartition = _m.Attribute(_m.InstanceType)
    xtmf_AggregationPartition = _m.Attribute(str)
    WalkAllWayExportFile = _m.Attribute(str)

    NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.ExportTransferMatrixFlag = True
        self.ExportWalkAllWayMatrixFlag = False

        self.NumberOfProcessors = cpu_count()
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Operator Transfer Matrix v%s" %self.version,
                     description="Extracts and exports a matrix of passenger volumes transferring \
                         from and to each operator, including initial boardings, final alightings \
                         and total walk-all-way volumes. Summing over each column is equivalent \
                         to aggregating the boardings for each operator; but only if the each line\
                         has a non-zero group number (i.e. full coverage).\
                         <br><br>Each operator (or <em>line group</em>) is identified numerically \
                         (e.g. <b>1</b> for the first group, <b>2</b> for the second, etc.) based on \
                         several pre-set schemes. The 0<sup>th</sup> 'group' is special: the 0<sup>th</sup> \
                         row corresponds to initial boardings, and the 0<sup>th</sup> column to \
                         final alightings. The cell at 0,0 contains the total walk-all-way volumes \
                         for the scenario.\
                         <br><br><b>Walk-all-way matrix:</b> This tool also calculates, for each OD \
                         the fraction of trips walking all-way. If desired, this tool can aggregate \
                         this matrix (based on an existing <em>Zone Partition</em>) and export it.\
                         <br><br><b>Temporary storage requirements:</b> 1 full matrix, 2 transit \
                         segment attributes, and 1 transit line attribute (if using a pre-built \
                         grouping scheme). ",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        if EMME_VERSION >= (4,1):
            pb.add_text_element("<em><b>Performance note for Emme 4.1 and newer:</b> \
                When analyzing the results of a congested transit assignment, this \
                tool will automatically blend the results over all iterations in \
                order to keep the results consistent with those saved to the network. \
                This is a slow operation so allow for additional run time when \
                analyzing many iterations.</em>")
        
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_matrix(tool_attribute_name= 'DemandMatrixId',
                             filter=['FULL'], allow_none=True, id=True,
                             title= "Demand to Analyze",
                             note= "If set to None, the tool will use the demand matrix from the assignment, \
                                 however this will affect run time for this tool.")
        
        if self._GetAssignmentType() == "MULTICLASS_TRANSIT_ASSIGNMENT":
            classes = self._LoadClassInfo()
            keyval1 = []
            for className, alpha in classes:
                keyval1.append((className, className))
        else:
            keyval1 = [(-1, "Multiclass assignment not available")]
        pb.add_select(tool_attribute_name= 'ClassName',
                      keyvalues= keyval1,
                      title= "Class Name",
                      note= "The name of the assignment class to analyze. \
                          <br>Only required if a multiclass transit assignment has been run \
                          (Emme 4.1 and newer).")
        
        
        pb.add_header("TRANSFER MATRIX")
        
        pb.add_checkbox(tool_attribute_name= 'ExportTransferMatrixFlag',
                        label= "Export Transfer Matrix?")
        
        keyval2 = [(1, "<em>Pre-built:</em> NCS11 operator codes"),
                   (2, "<em>Pre-built:</em> Alphabetical by operator"),
                   (3, "<em>Pre-built:</em> Alphabetical by operator and mode"),
                   (4, "<em>Pre-built:</em> GTAModel V4 line groups"),
                   (5, "<em>Pre-built:</em> GTAModel V4 groups + TTC prem. bus"),
                   ("ut1", "<em>Custom:</em> Group IDs stored in UT1"),
                   ("ut2", "<em>Custom:</em> Group IDs stored in UT2"),
                   ("ut3", "<em>Custom:</em> Group IDs stored in UT3")]
        for exatt in self.Scenario.extra_attributes():
            if exatt.type != "TRANSIT_LINE": continue
            text = "<em>Custom:</em> Group IDs stored in %s - %s" %(exatt.name, exatt.description)
            keyval2.append((exatt.name, text))
        pb.add_select(tool_attribute_name= 'LineGroupOptionOrAttributeId',
                      keyvalues= keyval2,
                      title= "Line Groups \ Grouping Scheme",
                      note= "Select a pre-built option or an existing transit line \
                          attribute with group codes")
        
        pb.add_select_file(tool_attribute_name= 'TransferMatrixFile',
                           window_type= 'save_file',
                           file_filter= "*.csv",
                           title= "Transit Matrix File",
                           note= "CSV file to save the transfer matrix to.")
        
        
        pb.add_header("WALK-ALL-WAY MATRIX")
        
        pb.add_checkbox(tool_attribute_name= 'ExportWalkAllWayMatrixFlag',
                        label= "Export walk-all-way matrix?")
        
        pb.add_select_partition(tool_attribute_name= 'AggregationPartition',
                                allow_none= True,
                                title= "Aggregation Partition",
                                note= "<font color='green'><b>Optional:</b></font> \
                                    Select none to disable exporting the walk all-way matrix.")
        
        pb.add_select_file(tool_attribute_name= 'WalkAllWayExportFile',
                           window_type= 'save_file',
                           file_filter= "*.csv",
                           title= "Walk-all-way Matrix File",
                           note= "<font color='green'><b>Optional</b></font>")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        if (tool.class_name_is_required())
        {
            $("#ClassName").prop('disabled', false);
        } else {
            $("#ClassName").prop('disabled', true);
        }
        
        if (! tool.preload_transfer_matrix_flag())
        {
            $("#LineGroupOptionOrAttributeId").prop('disabled', true);
            $("#TransferMatrixFile").prop('disabled', true);
        }
        
        if (! tool.preload_waw_matrix_flag())
        {
            $("#AggregationPartition").prop('disabled', true);
            $("#WalkAllWayExportFile").prop('disabled', true);
        }
        
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            
            $("#LineGroupOptionOrAttributeId")
                .empty()
                .append(tool.preload_line_group_options())
            inro.modeller.page.preload("#LineGroupOptionOrAttributeId");
            $("#LineGroupOptionOrAttributeId").trigger('change')
            
            if (tool.class_name_is_required())
            {
                $("#ClassName")
                    .empty()
                    .append(tool.preload_class_names())
                inro.modeller.page.preload("#ClassName");
                $("#ClassName").trigger('change')
            
                $("#ClassName").prop('disabled', false);
            } else {
                $("#ClassName")
                    .empty()
                    .append("<option value='-1'>Multiclass assignment not available</option>")
                inro.modeller.page.preload("#ClassName");
                $("#ClassName").trigger('change')
            
                $("#ClassName").prop('disabled', true);
            }
        });
        
        $("#ExportTransferMatrixFlag").bind('change', function()
        {
            $(this).commit();
            
            var flag = ! tool.preload_transfer_matrix_flag();
            $("#LineGroupOptionOrAttributeId").prop('disabled', flag);
            $("#TransferMatrixFile").prop('disabled', flag);
        });
        
        $("#ExportWalkAllWayMatrixFlag").bind('change', function()
        {
            $(this).commit();
            
            var flag = ! tool.preload_waw_matrix_flag();
            $("#AggregationPartition").prop('disabled', flag);
            $("#WalkAllWayExportFile").prop('disabled', flag);
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            if self.ExportTransferMatrixFlag or self.ExportWalkAllWayMatrixFlag:
                
                if self.ExportTransferMatrixFlag and not self.TransferMatrixFile:
                    raise IOError("No transfer matrix file specified.")
                
                if self.ExportWalkAllWayMatrixFlag:                    
                    if not self.WalkAllWayExportFile: raise TypeError("No walk-all-way matrix file specified")
                    
                self._Execute()
                _MODELLER.desktop.refresh_needed(False)
        except Exception, e:
            _MODELLER.desktop.refresh_needed(False)
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")

    def __call__(self, xtmf_ScenarioNumber, ExportTransferMatrixFlag, ExportWalkAllWayMatrixFlag, TransferMatrixFile, 
                 xtmf_AggregationPartition, WalkAllWayExportFile, LineGroupOptionOrAttributeId):
        self.tool_run_msg = ""
        self.TRACKER.reset()                              

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        if(xtmf_AggregationPartition.lower() == "none"):
            self.AggregationPartition == None;
        else:
            self.AggregationPartition = _MODELLER.emmebank.partition(xtmf_AggregationPartition)                    

        try:
            if self.ExportTransferMatrixFlag or self.ExportWalkAllWayMatrixFlag:
                
                if self.ExportTransferMatrixFlag and not self.TransferMatrixFile:
                    raise IOError("No transfer matrix file specified.")
                
                if self.ExportWalkAllWayMatrixFlag:                    
                    if not self.WalkAllWayExportFile: raise TypeError("No walk-all-way matrix file specified")
                    
                self._Execute()     
                                                           
        except Exception, e:                        
            raise
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type= bool)
    def class_name_is_required(self):
        return self._GetAssignmentType() == 'MULTICLASS_TRANSIT_ASSIGNMENT'
    
    @_m.method(return_type=unicode)
    def preload_class_names(self):
        classInfo = self._LoadClassInfo()
        options = []
        for name, alpha in classInfo:
            options.append("<option value='%s'>%s</option>" %(name, name))
        return "\n".join(options)
    
    @_m.method(return_type=unicode)
    def preload_line_group_options(self):
        options = [(1, "<em>Pre-built:</em> NCS11 operator codes"),
                   (2, "<em>Pre-built:</em> Alphabetical by operator"),
                   (3, "<em>Pre-built:</em> Alphabetical by operator and mode"),
                   (4, "<em>Pre-built:</em> GTAModel V4 line groups"),
                   (5, "<em>Pre-built:</em> GTAModel V4 groups + TTC prem. bus"),
                   ("<em>Custom:</em> ut1", "Group IDs stored in UT1"),
                   ("<em>Custom:</em> ut2", "Group IDs stored in UT2"),
                   ("<em>Custom:</em> ut3", "Group IDs stored in UT3")]
        
        for exatt in self.Scenario.extra_attributes():
            if exatt.type != "TRANSIT_LINE": continue
            text = "<em>Custom:</em> Group IDs stored in %s - %s" %(exatt.name, exatt.description)
            options.append((exatt.name, text))
        
        options = ["<option value=%s>%s</option>" %tup for tup in options]
        return "\n".join(options)
    
    @_m.method(return_type= bool)
    def preload_transfer_matrix_flag(self):
        return self.ExportTransferMatrixFlag
    
    @_m.method(return_type= bool)
    def preload_waw_matrix_flag(self):
        return self.ExportWalkAllWayMatrixFlag
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            managers = [_util.tempMatrixMANAGER("Walk-all-way matrix"),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT',
                                                        description= "Initial boardings attribute"),
                        _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT',
                                                        description= "Final alightings attribute"),
                        getTemporaryFolder()]
            
            #Handle creating the transit line attribute in which to flag groups (if required). 
            if self.LineGroupOptionOrAttributeId.isdigit():
                managers.insert(0, _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE',
                                                                   description= "Line group ID",
                                                                   returnId= True))
                lineGroupOption = int(self.LineGroupOptionOrAttributeId)
            else:
                managers.insert(0, blankContextManager(self.LineGroupOptionOrAttributeId))
                lineGroupOption = 0
            
            with nested(*managers) as (lineGroupAtributeID, walkAllWayMatrix, 
                                       boardAttribute, alightAttribute,
                                       tempFolder):
                
                #---1. Flag pre-built groupings, if needed
                if lineGroupOption and self.ExportTransferMatrixFlag:
                    with _m.logbook_trace("Applying pre-built groupings"):
                        self._ApplyPreBuiltCodes(lineGroupOption, lineGroupAtributeID)
                self.TRACKER.completeTask()
                
                #---2. Get the traversal matrix
                if self.ExportTransferMatrixFlag:
                    transferMatrix = self._GetTraversalMatrix(lineGroupAtributeID, tempFolder)
                    
                    
                    #---3. Attach initial boarding and final alighting data to matrix
                    self._GetBoardingsAndAlightings(transferMatrix, lineGroupAtributeID, 
                                                    boardAttribute.id, alightAttribute.id)
                    print "Loaded initial boardings and final alightings"
                else: transferMatrix = None 
                
                #---4. Get the walk-all-way matrix
                self._GetWalkAllWayMatrix(walkAllWayMatrix, transferMatrix)
                print "Loaded walk all-way matrix"
                
                #---5. Export the transfer matrix
                if self.ExportTransferMatrixFlag:
                    self._WriteExportFile(transferMatrix)
                
                #---6. Export the aggregated walk-all-way matrix (if desired)
                if self.ExportWalkAllWayMatrixFlag:
                    self._ExportWalkAllWayMatrix(walkAllWayMatrix)
                

    ##########################################################################################################
    
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _GetAssignmentType(self):
        if not self.Scenario.has_transit_results: return None
        
        configPath = dirname(_MODELLER.desktop.project_file_name()) \
                    + "/Database/STRATS_s%s/config" %self.Scenario
        
        if not exists(configPath): return self.Scenario.transit_assignment_type
        
        with open(configPath) as reader:
            config = _parsedict(reader.readline())
        
        data = config['data']
        return data['type']
        
    
    def _LoadClassInfo(self):
        
        if not self.Scenario.has_transit_results: return []
        
        configPath = dirname(_MODELLER.desktop.project_file_name()) \
                    + "/Database/STRATS_s%s/config" %self.Scenario
        
        if not exists(configPath): return []
        
        with open(configPath) as reader:
            config = _parsedict(reader.readline())
        
        classes = []
        for info in config['strat_files']:
            className = info['name']
            if not 'alpha' in info['data']:
                alpha = 0.0
            else: alpha = info['data']['alpha']
            
            classes.append((className, alpha))
        
        return classes
    
    def _ApplyPreBuiltCodes(self, option, attributeId):
        options = {1: LINE_GROUPS_NCS11,
                   2: LINE_GROUPS_ALPHA_OP,
                   3: LINE_GROUPS_ALPHA_OP_MODE,
                   4: LINE_GROUPS_GTAMV4,
                   5: LINE_GROUPS_GTAMV4_PREM}
        
        def flagGroup(value, selector, descr):
                spec= {
                        "result": attributeId,
                        "expression": str(value),
                        "aggregation": None,
                        "selections": {
                            "transit_line": selector
                        },
                        "type": "NETWORK_CALCULATION"
                    }
                with _m.logbook_trace("Flagging %s lines as %s" %(descr, value)):
                    networkCalculator(spec, scenario=self.Scenario)
        
        groupings = options[option]
        self.TRACKER.startProcess(len(groupings))
        for groupId, selector, name in groupings:
            flagGroup(groupId, selector, name)
            self.TRACKER.completeSubtask()
    
    def _GetTraversalMatrix(self, lineGroupAtributeID, tempFolder):
        #---2. Load class / iteration information for traversal analysis
        if self._GetAssignmentType() == "CONGESTED_TRANSIT_ASSIGNMENT":
            if EMME_VERSION >= (4,1,0):
                classWeights = []
            else:
                classWeights = self._LoadClassInfo()
        elif self._GetAssignmentType() == "MULTICLASS_TRANSIT_ASSIGNMENT":
            classWeights = [(self.ClassName, 1.0)]
        else:
            classWeights = []
        
        #---3. Run the traversal analysis tool for each class (if needed)
        files = {}
        nTasks = max(len(classWeights), 1)
        self.TRACKER.startProcess(nTasks)
        if classWeights:
            for className, weight in classWeights:
                filepath = _tf.mktemp(".csv", dir= tempFolder)
                files[className] = filepath
                self._RunTraversalAnalysis(lineGroupAtributeID, filepath, className)
                self.TRACKER.completeSubtask()
        else:
            filepath = _tf.mktemp(".csv", dir= tempFolder)
            self._RunTraversalAnalysis(lineGroupAtributeID, filepath)
            files = filepath
        self.TRACKER.completeTask()
        print "Processed traversal matrices"
        
        #---4. Load or load and combine traversal matrices
        self.TRACKER.startProcess(nTasks)
        if classWeights:
            transferMatrix = {}
            for className, weight in classWeights:
                filepath = files[className]
                classMatrix = self._ParseTraversalResults(filepath)
                for key, value in classMatrix.iteritems():
                    weightedValue = weight * value
                    if key in transferMatrix: transferMatrix[key] += weightedValue
                    else: transferMatrix[key] = weightedValue
                self.TRACKER.completeSubtask()
                print "Loaded class %s" %className
        else:
            filepath = files
            transferMatrix = self._ParseTraversalResults(filepath) 
        self.TRACKER.completeTask()
        print "Aggregated transfer matrix."
        
        return transferMatrix
        
    
    def _RunTraversalAnalysis(self, attributeId, filepath, className= None):
        spec = {
                "portion_of_path": "COMPLETE",
                "gates_by_trip_component": {
                    "in_vehicle": None,
                    "aux_transit": None,
                    "initial_boarding": None,
                    "transfer_boarding": attributeId,
                    "transfer_alighting": attributeId,
                    "final_alighting": None
                },
                "analyzed_demand": self.DemandMatrixId,
                "path_analysis": None,
                "type": "EXTENDED_TRANSIT_TRAVERSAL_ANALYSIS"
            }
        
        if self.DemandMatrixId != None:
            spec['constraint'] = {
                                    "by_value": {
                                        "interval_min": 0,
                                        "interval_max": 0,
                                        "condition": "EXCLUDE",
                                        "od_values": self.DemandMatrixId
                                    },
                                    "by_zone": None
                                }
        else:
            spec['constraint'] = None
        
        print "Running traversal analysis on class %s" %className
        if className != None:
            traversalAnalysisTool(spec, filepath, 
                                  scenario= self.Scenario,
                                  class_name= className)
        else:
            traversalAnalysisTool(spec, filepath,
                                  scenario= self.Scenario)
            
    def _ParseTraversalResults(self, filepath):
        retval = {}
        
        with open(filepath) as reader:
            line = ""
            while not line.startswith("a"):
                line = reader.readline()
            for line in reader:
                cells = line.strip().split()
                if len(cells) != 3: continue
                o = int(cells[0])
                d = int(cells[1])
                try:
                    val = float(cells[2])
                except ValueError:
                    val = cells[2].replace('u', '.')
                    val = float(val)
                od = (o,d)
                retval[od] = val
        return retval
    
    def _GetBoardingsAndAlightings(self, transferMatrix, lineGroupAtributeID, boardingAttributeId,
                                   alightingAttributeId):
        self._RunNetworkResults(boardingAttributeId, alightingAttributeId)
        
        self._LoadBoardingsAndAlightings(lineGroupAtributeID, boardingAttributeId, alightingAttributeId,
                                         transferMatrix)
    
    def _RunNetworkResults(self, boardingAttributeId, alightingAttributeId):        
        spec= {
                "on_links": None,
                "on_segments": {
                    "initial_boardings": boardingAttributeId,
                    "final_alightings": alightingAttributeId
                },
                "aggregated_from_segments": None,
                "analyzed_demand": self.DemandMatrixId,
                "constraint": None,
                "type": "EXTENDED_TRANSIT_NETWORK_RESULTS"
            }
        
        if self.ClassName:
            self.TRACKER.runTool(networkResultsTool, spec, self.Scenario, class_name= self.ClassName)
        else:
            self.TRACKER.runTool(networkResultsTool, spec, self.Scenario)
    
    def _LoadBoardingsAndAlightings(self, lineGroupAtributeID, boardingAttributeId, alightingAttributeId, 
                                   transferMatrix):
        
        lineGroups = _util.fastLoadTransitLineAttributes(self.Scenario, [lineGroupAtributeID])
        lineActivity = _util.fastLoadSummedSegmentAttributes(self.Scenario, [boardingAttributeId,
                                                                         alightingAttributeId])
        
        groupActivity = {}
        
        for lineId, lineAtts in lineGroups.iteritems():
            groupId = int(lineAtts[lineGroupAtributeID])
            
            if lineId in lineActivity:
                initialBoardings = lineActivity[lineId][boardingAttributeId]
                finalAlightings = lineActivity[lineId][alightingAttributeId]
            else:
                initialBoardings = 0.0
                finalAlightings = 0.0
            
            if groupId in groupActivity:
                activity = groupActivity[groupId]
                activity[0] += initialBoardings
                activity[1] += finalAlightings
            else:
                groupActivity[groupId] = [initialBoardings, finalAlightings]
        
        for groupId, activity in groupActivity.iteritems():
            initialBoardings, finalAlightings = activity
            
            transferMatrix[(0, groupId)] = initialBoardings
            transferMatrix[(groupId, 0)] = finalAlightings
        
        self.TRACKER.completeTask() 
    
    def _GetWalkAllWayMatrix(self, wawMatrix, transferMatrix):
        self._RunStrategyAnalysis(wawMatrix.id)
        
        wawSum = self._SumWalkAllWayMatrix(wawMatrix.id)
        
        if self.ExportTransferMatrixFlag:
            transferMatrix[(0,0)] = wawSum 
    
    def _RunStrategyAnalysis(self, wawMatrixId):
        spec = {
                    "trip_components": {
                        "boarding": None,
                        "in_vehicle": "length",
                        "aux_transit": None,
                        "alighting": None
                    },
                    "sub_path_combination_operator": "+",
                    "sub_strategy_combination_operator": ".min.",
                    "selected_demand_and_transit_volumes": {
                        "sub_strategies_to_retain": "FROM_COMBINATION_OPERATOR",
                        "selection_threshold": {
                            "lower": 0,
                            "upper": 0
                        }
                    },
                    "analyzed_demand": self.DemandMatrixId,
                    "constraint": None,
                    "results": {
                        "strategy_values": None,
                        "selected_demand": wawMatrixId,
                        "transit_volumes": None,
                        "aux_transit_volumes": None,
                        "total_boardings": None,
                        "total_alightings": None
                    },
                    "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
                }
        
        if self.ClassName:
            strategyAnalysisTool(spec, scenario= self.Scenario, class_name= self.ClassName)
        else:
            strategyAnalysisTool(spec, scenario= self.Scenario)
    
    def _SumWalkAllWayMatrix(self, wawMatrixId):
        spec = {
                "expression": wawMatrixId,
                "result": None,
                "constraint": {
                    "by_value": None,
                    "by_zone": None
                },
                "aggregation": {
                    "origins": "+",
                    "destinations": "+"
                },
                "type": "MATRIX_CALCULATION"
            }
        
        if EMME_VERSION >= (4,2,1):
            return self.TRACKER.runTool(matrixCalculator, spec, scenario=self.Scenario,
                                             num_processors=self.NumberOfProcessors)['result']
        else:
            return self.TRACKER.runTool(matrixCalculator, spec, scenario=self.Scenario)['result']
        
    def _WriteExportFile(self, transferMatrix):
        with open(self.TransferMatrixFile, 'w') as writer:
            headerSet = set()
            for origin, destination in transferMatrix.iterkeys():
                headerSet.add(origin)
                headerSet.add(destination)
            headers = [h for h in headerSet]
            headers.sort()
            
            header = ",".join( [""] + [str(h) for h in headers])
            writer.write(header)
            
            for origin in headers:
                row = [str(origin)]
                for destination in headers:
                    key = (origin, destination)
                    if key in transferMatrix:
                        value = transferMatrix[key]
                    else:
                        value = 0.0
                    row.append(str(value))
                writer.write("\n" + ",".join(row))
    
    def _ExportWalkAllWayMatrix(self, walkAllWayMatrix):
        partSpec = {'origins': self.AggregationPartition.id,
                    'destinations': self.AggregationPartition.id,
                    'operator': 'sum'}
        matrixExportTool([walkAllWayMatrix],
                         partition_aggregation= partSpec,
                         export_file= self.WalkAllWayExportFile,
                         field_separator= ',',
                         full_matrix_line_format= 'SQUARE')