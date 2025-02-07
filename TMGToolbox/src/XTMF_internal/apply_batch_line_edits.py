from __future__ import print_function
#---LICENSE----------------------
'''
    Copyright 2015-2016 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Apply Batch Line Edits

    Authors: mattaustin222, JamesVaughan

    Latest revision by: JamesVaughan
    
    
    This tool brings in a list of changes to be applied to transit lines
    in a set of scenarios. The aim of the tool is to reduce the 
    work required in making sweeping changes to headways and speeds
    of transit lines. It is intended only to be called from XTMF.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-02-24 by mattaustin222
    0.0.2 Added the ability to process multiple alt files in sequence by JamesVaughan
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
netCalc = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ApplyBatchLineEdits(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here

    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters necessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get initialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only

    inputFile = _m.Attribute(str) # file should have the following header: 
                                        # filter|x_hdwchange|x_spdchange
                                        # where filter is a network calculator filter expression
                                        # x refers to the scenario number
                                        # the x columns can be multiple (ie. multiple definitions
                                        # in a single file)
                                        # hdwchange and spdchange are factors by which
                                        # to change headways and speeds for the filtered
                                        # lines
    additionalInputFiles = _m.Attribute(str) #Either a string containing 'None' or a list of additional alt files ; separated.

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
                
        pb = _m.ToolPageBuilder(self, title="Apply Batch Line Edits",
                     description="Cannot be called from Modeller.",
                     runnable=False,
                     branding_text="XTMF")
        
        return pb.render()
    
    ##########################################################################################################
        
    def __call__(self, xtmf_ScenarioNumber, inputFile, additionalInputFiles = None):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        #---2 Set up instruction file
        self.InstructionFile = inputFile
        if (self.InstructionFile is None):
            raise Exception("Need to provide an input file.")
        # Process the additional files, if it is the string None then there are no additional files otherwise they are ; separated
        if additionalInputFiles  is None or additionalInputFiles == "None":
            self.InputFiles = []
        else:
            self.InputFiles = additionalInputFiles.split(';')
        # Add the base transaction file to the beginning
        self.InputFiles.insert(0, self.InstructionFile)
        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)

    ##########################################################################################################    
        
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            #init the ProgressTracker now that we know how many files we need to load
            self.TRACKER = _util.ProgressTracker(len(self.InputFiles))
            for altFile in self.InputFiles:
                changesToApply = self._LoadFile(altFile)
                print("Instruction file loaded")
                if changesToApply: 
                    self._ApplyLineChanges(changesToApply)
                    print("Headway and speed changes applied")
                else:
                    print("No changes available in this scenario")
                self.TRACKER.completeTask()


    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _LoadFile(self, fileName):
        with open(fileName) as reader:
            header = reader.readline()
            cells = header.strip().split(self.COMMA)
            
            filterCol = cells.index('filter')
            headwayTitle = self.Scenario.id + '_hdwchange'
            speedTitle = self.Scenario.id + '_spdchange'
            try:
                headwayCol = cells.index(headwayTitle)
            except Exception as e:
                msg = "Error. No headway match for specified scenario: '%s'." %self.Scenario.id
                _m.logbook_write(msg)
                print(msg)
                return
            try:
                speedCol = cells.index(speedTitle)
            except Exception as e:
                msg = "Error. No speed match for specified scenario: '%s'." %self.Scenario.id
                _m.logbook_write(msg)
                print(msg)
                return

            instructionData = []
            
            for num, line in enumerate(reader):
                cells = line.strip().split(self.COMMA)
                
                line_filter = cells[filterCol]
                # if the column is left blank, carry forward a factor of 1
                headway = cells[headwayCol] if cells[headwayCol] else 1.0
                speed = cells[speedCol] if cells[speedCol] else 1.0
                instructionData.append((str(line_filter),float(headway),float(speed)))
        
        return instructionData

    def _ApplyLineChanges(self, inputData):
        for (line_filter, headway, speed) in inputData:
            if headway != 1:
                spec = {
                    "type": "NETWORK_CALCULATION",
                    "expression": str(headway) + "*hdw",
                    "result": "hdw",
                    "selections": {
                        "transit_line": line_filter}}
                netCalc(spec, self.Scenario)
            if speed != 1:
                spec = {
                    "type": "NETWORK_CALCULATION",
                    "expression": str(speed) + "*speed",
                    "result": "speed",
                    "selections": {
                        "transit_line": line_filter}}
                netCalc(spec, self.Scenario)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
            