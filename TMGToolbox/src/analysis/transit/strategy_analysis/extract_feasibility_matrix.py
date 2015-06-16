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

'''
Analysis Tool for Extracting Feasibility Matrix

    Author: Peter Kucirek

'''
import inro.modeller as _m
import traceback as _traceback
from multiprocessing import cpu_count
_util = _m.Modeller().module('tmg.common.utilities')
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')

EMME_VERSION = _util.getEmmeVersion(tuple) 

class ExtractFeasibilityMatrix(_m.Tool()):
    
    version = '0.1.1'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    WalkTimeCutoff = _m.Attribute(float)
    WaitTimeCutoff = _m.Attribute(float)
    TotalTimeCutoff = _m.Attribute(float)
    MatrixResultNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    
    NumberOfProcessors = _m.Attribute(int)
    #---Special instance types, used only from Modeller
    scenario = _m.Attribute(_m.InstanceType)
    matrixResult = _m.Attribute(_m.InstanceType)
    modes = _m.Attribute(_m.ListType)
    
    #---Private variables
    _modeList = []
    
    def __init__(self):
        self.databank = _m.Modeller().emmebank

        self.NumberOfProcessors = cpu_count()

        try:
            self.matrixResultTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
            self.matrixCalcTool = _m.Modeller().tool('inro.emme.standard.matrix_calculation.matrix_calculator')
        except Exception, e:
            self.matrixResultTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
            self.matrixCalcTool = _m.Modeller().tool('inro.emme.matrix_calculation.matrix_calculator')
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Feasibility Matrix",
                     description="Extracts a feasibility matrix (where 1 is feasible and 0 is infeasible), based \
                                    on cut-off values for walking, waiting, and total times.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("ANALYSIS OPTIONS")
        
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_mode(tool_attribute_name='modes',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Modes:')
        
        pb.add_select_matrix(tool_attribute_name='matrixResult',
                             title='Result Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_header("PARAMETERS")
        
        pb.add_text_box(tool_attribute_name='WalkTimeCutoff',
                        size=4,
                        title='Walk Time Cutoff:')
        
        pb.add_text_box(tool_attribute_name='WaitTimeCutoff',
                        size=4,
                        title='Wait Time Cutoff:')
        
        pb.add_text_box(tool_attribute_name='TotalTimeCutoff',
                        size=4,
                        title='Total Time Cutoff:')
        
        return pb.render()
    
    def run(self):
        '''Run is called from Modeller.'''
        self.tool_run_msg = ""
        self.isRunningFromXTMF = False
        
        # Convert the list of mode objects to a list of mode characters
        for m in self.modes:
            self._modeList.append(m.id)
        
        # Initialize the result matrix, if necessary
        #def initializeMatrix(id=None, default=0, name="", description="", matrix_type='FULL'):
        self.matrixResult = _util.initializeMatrix(self.matrixResult, matrix_type='FULL', name='trfeas',
                                              description= 'Transit feasibility matrix')
        
        # Run the tool
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            self._cleanup()
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete. Results stored in matrix %s." %self.matrixResult.id)
        
    
    def __call__(self, ScenarioNumber, WalkTimeCutoff, WaitTimeCutoff, TotalTimeCutoff,\
                 ModeString, MatrixResultNumber):
        
        # Get the scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.scenario == None:
            raise Exception("Could not find scenario %s!" %ScenarioNumber)
        
        self.matrixResult = _util.initializeMatrix(MatrixResultNumber, matrix_type='FULL', name='trfeas',
                                              description='Transit feasibility matrix')
        
        # Convert the mode string to a list of characters
        for i in range(0, len(ModeString)):
            self._modeList.append(ModeString[i])
        
        # Set all other variables
        self.WalkTimeCutoff = WalkTimeCutoff
        self.WaitTimeCutoff = WaitTimeCutoff
        self.TotalTimeCutoff = TotalTimeCutoff
        self.ModeString = ModeString
    
        self.isRunningFromXTMF = True
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            self._cleanup()
            raise Exception(_traceback.format_exc(e))    
        
    def _execute(self):
        
        with _m.logbook_trace(name="Extract transit feasibility matrix v%s" %self.version,
                                     attributes={
                                                 "Scenario" : self.scenario.id,
                                                 "Walk Time Cutoff" : self.WalkTimeCutoff,
                                                 "Wait Time Cutoff": self.WaitTimeCutoff,
                                                 "Total Time Cutoff": self.TotalTimeCutoff,
                                                 "ModeString": self.ModeString,
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            self._assignmentCheck()
            
            #---1 Initialize temporary matrices for storing walk, wait, and in-vehicle times
            with nested(_util.tempMatrixMANAGER(description='Temp walk time matrix'),
                        _util.tempMatrixMANAGER(description='Temp wait time matrix'),
                        _util.tempMatrixMANAGER(description='Temp ivtt matrix'))\
                    as (self.walkMatrix, self.waitMatrix, self.ivttMatrix):
            
                #---2 Compute the temporary matrices
                _m.logbook_write("Computing temporary matrices")
                self.matrixResultTool(self._getStrategyAnalysisSpec())
                
                #---3 Compute the final results matrix
                _m.logbook_write("Computing feasibility matrix")
                if EMME_VERSION >= (4,2,1):
                    self.matrixCalcTool(self._getMatrixCalcSpec(), self.scenario,
                                             num_processors=self.NumberOfProcessors)  
                else: 
                    self.matrixCalcTool(self._getMatrixCalcSpec(), self.scenario)         
    
    def _assignmentCheck(self):
        if self.scenario.transit_assignment_type != 'EXTENDED_TRANSIT_ASSIGNMENT':
            raise Exception("No extended transit assignment results were found for scenario %s!" %self.scenario.id)
    
    def _getStrategyAnalysisSpec(self):
        
        spec = {
                "by_mode_subset": {
                                   "modes": self._modeList,
                                   "actual_in_vehicle_times": self.ivttMatrix.id,
                                   "actual_aux_transit_times": self.walkMatrix.id
                                   },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": self.waitMatrix.id
                }
        
        return spec
    
    def _getMatrixCalcSpec(self):
        #          (walk < cutoff) AND (wait < cutoff) AND ((walk + wait + ivtt) < cutoff)   
        expression = "({0} < {3}) && ({1} < {4}) && (({0} + {1} + {2}) < {5})".format(self.walkMatrix.id,
                                                                                    self.waitMatrix.id,
                                                                                    self.ivttMatrix.id,
                                                                                    str(self.WalkTimeCutoff),
                                                                                    str(self.WaitTimeCutoff),
                                                                                    str(self.TotalTimeCutoff))
        
        spec = {
                "expression": expression,
                "result": self.matrixResult.id,
                "constraint": {
                                "by_value": None,
                                "by_zone": None
                                },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
        return spec
    
    def _cleanup(self):
        # like an if statement, except this also works if the name is not in-context
        try:
            self.databank.delete_matrix(self.walkMatrix.id)
            self.databank.delete_matrix(self.waitMatrix.id)
            self.databank.delete_matrix(self.ivttMatrix.id)
        except Exception, e:
            pass
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        
    
    