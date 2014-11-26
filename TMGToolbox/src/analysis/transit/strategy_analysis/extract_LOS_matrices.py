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

'''
Analysis Tool for Extracting Travel Time Matrices

    Author: Peter Kucirek

'''
import inro.modeller as _m
import traceback as _traceback
_util = _m.Modeller().module('tmg.common.utilities')

class ExtractTravelTimeMatrices(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    ModeString = _m.Attribute(str)
    InVehicleTimeMatrixNumber = _m.Attribute(int)
    WalkTimeMatrixNumber = _m.Attribute(int)
    WaitTimeMatrixNumber = _m.Attribute(int)
    BoardingTimeMatrixNumber = _m.Attribute(int)
    
    #---Special instance types, used only from Modeller
    scenario = _m.Attribute(_m.InstanceType)
    modes = _m.Attribute(_m.ListType)
    ivttMatrix = _m.Attribute(_m.InstanceType)
    walkMatrix = _m.Attribute(_m.InstanceType)
    waitMatrix = _m.Attribute(_m.InstanceType)
    boardingMatrix = _m.Attribute(_m.InstanceType)
    
    #---Private variables
    _modeList = []
    
    def __init__(self):
        self.databank = _m.Modeller().emmebank
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Extract Travel Time Matrices",
                     description="Extracts average in-vehicle, walking, waiting, and boarding time\
                     matrices from a strategy-based assignment.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_mode(tool_attribute_name='modes',
                           filter=['TRANSIT', 'AUX_TRANSIT'],
                           allow_none=False,
                           title='Modes:',
                           note='Select modes used in the assignment.')
        
        pb.add_select_matrix(tool_attribute_name='ivttMatrix',
                             title='IVTT Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_select_matrix(tool_attribute_name='walkMatrix',
                             title='Walk Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_select_matrix(tool_attribute_name='waitMatrix',
                             title='Wait Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        pb.add_select_matrix(tool_attribute_name='boardingMatrix',
                             title='Boarding Matrix:',
                             filter=['FULL'],
                             note="If no matrix is selected, an available matrix will be created.",
                             allow_none=True)
        
        return pb.render()
    
    def run(self):
        '''Run is called from Modeller.'''
        self.tool_run_msg = ""
        self.isRunningFromXTMF = False
        
        # Initialize blank matrices if needed.
        if self.ivttMatrix == None:
            self._initIVTT(self.databank.available_matrix_identifier('FULL'))
        if self.walkMatrix == None:
            self._initWalk(self.databank.available_matrix_identifier('FULL'))
        if self.waitMatrix == None:
            self._initWait(self.databank.available_matrix_identifier('FULL'))
        if self.boardingMatrix == None:
            self._initBoard(self.databank.available_matrix_identifier('FULL'))
        
        # Convert the list of mode objects to a list of mode characters
        for m in self.modes:
            self._modeList.append(m.id)
        
        # Run the tool
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete. Results stored in matrices\
                                {0}, {1}, {2}, and {3}.".format(self.ivttMatrix.id, self.walkMatrix.id, 
                                                               self.waitMatrix.id, self.boardingMatrix.id))
            
    
    def __call__(self, ScenarioNumber, ModeString, InVehicleTimeMatrixNumber,
                 WalkTimeMatrixNumber, WaitTimeMatrixNumber, BoardingTimeMatrixNumber):
        
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.scenario == None:
            raise Exception("Could not find scenario %s!" %ScenarioNumber)
        
        # Initialize the result matrices
        self._initBoard("mf%s" %BoardingTimeMatrixNumber)
        self._initIVTT("mf%s" %InVehicleTimeMatrixNumber)
        self._initWait("mf%s" %WaitTimeMatrixNumber)
        self._initWalk("mf%s" %WalkTimeMatrixNumber)
        
        # Convert the mode string to a list of characters
        for i in range(0, len(ModeString)):
            self._modeList.append(ModeString[i])
        
        self.isRunningFromXTMF = True
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
        
    def _execute(self):
        
        with _m.logbook_trace(name="Extract Travel Time Matrices v%s" %self.version,
                                     attributes={
                                                 "Scenario" : self.scenario.id,
                                                 "Modes": str(self._modeList),
                                                 "IVTT Matrix": self.ivttMatrix.id,
                                                 "Walk Time Matrix": self.walkMatrix.id,
                                                 "Wait Time Matrix": self.waitMatrix.id,
                                                 "Boarding Time Matrix": self.boardingMatrix.id,
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            self._assignmentCheck()
            
            try:
                matrixAnalysisTool = _m.Modeller().tool('inro.emme.transit_assignment.extended.matrix_results')
            except Exception, e:
                matrixAnalysisTool = _m.Modeller().tool('inro.emme.standard.transit_assignment.extended.matrix_results')
            
            matrixAnalysisTool(self._getAnalysisSpec(), self.scenario)
    
    def _initIVTT(self, mtxId):
        self.ivttMatrix = _util.initializeMatrix(mtxId, name='trIVTT', description= 'Avg total in vehicle times')
    
    def _initWalk(self, mtxId):
        self.walkMatrix = _util.initializeMatrix(mtxId, name='trWalk', description= 'Avg total walk times')
    
    def _initWait(self, mtxId):
        self.waitMatrix = _util.initializeMatrix(mtxId, name='trWait', description= 'Avg total wait times')
    
    def _initBoard(self, mtxId):
        self.boardingMatrix = _util.initializeMatrix(mtxId, name='trBord', description= 'Avg total boarding times')
    
    def _assignmentCheck(self):
        if self.scenario.transit_assignment_type != 'EXTENDED_TRANSIT_ASSIGNMENT':
            raise Exception("No extended transit assignment results were found for scenario %s!" %self.scenario.id)
    
    def _getAnalysisSpec(self):
        
        spec = {
                "by_mode_subset": {
                                   "modes": self._modeList,
                                   "actual_total_boarding_times": self.boardingMatrix.id,
                                   "actual_in_vehicle_times": self.ivttMatrix.id,
                                   "actual_aux_transit_times": self.walkMatrix.id
                                   },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": self.waitMatrix.id
                }
        
        return spec
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        