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
Export Worksheet Table 

    Authors: mattaustin222

    Latest revision by: mattaustin222
    
    
    XTMF-compatible version of the INRO Log by worksheet
    table and scenario tool. Allows for custom save location
    of the .csv output.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-07-15 by mattaustin222
    
'''

import inro.modeller as _m

import traceback as _traceback
import os
import shutil
from distutils.dir_util import copy_tree

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
LogTable = _MODELLER.tool('inro.emme.desktop.log_worksheet_table')
EMME_VERSION = _util.getEmmeVersion(tuple) 
emmebankLocation = _MODELLER.emmebank.path

##########################################################################################################

class ExportWorksheetTable(_m.Tool()):

     #---PARAMETERS
    xtmf_ScenarioNumber = _m.Attribute(str)
    xtmf_WorksheetPath = _m.Attribute(str)
    FilePath = _m.Attribute(str) 
    WorksheetPath = _m.Attribute(list)

    Scenario = _m.Attribute(_m.InstanceType)

            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   

    def run(self):
        self.tool_run_msg = ""
        #testPath = "C:\Users\matta_000\Documents\EMME Projects\SmartTrack\Worksheets\TestModes.emt"
        #self.FilePath = "C:\Users\matta_000\Documents\XTMF\Projects\Test"

        #if os.path.isfile(testPath): # optionally provide full path to worksheet file
        #    # check to see if the file is already in the correct location
        #    testPath = os.path.abspath(testPath)
        #    head, tail = os.path.split(testPath)            
        #    worksheetLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Worksheets'))
        #with open(testPath, 'r') as f:
        #    checkFile = False
        #    for line in f:
        #        if "name = " in line.lower(): # this is the convention for the table title in the table file
        #            tableTitle = line[7:].strip()      
        #            checkFile = True
        #            break
        #    if not checkFile:
        #        raise Exception("File is not a valid Emme table file")
        #if head == worksheetLocation:                
        #    self.WorksheetPath = [[tableTitle]] # set the path as a list of lists to feed in to the INRO tool
        #    print tableTitle
        #else:
        #    try:
        #        shutil.copy2(testPath, worksheetLocation) # copy the worksheet file to the project worksheet directory
        #        self.WorksheetPath = [[tableTitle]]
        #    except:
        #        raise Exception("Failed to copy worksheet to project/Worksheets directory")

        #try:
        #    self._Execute()
        #except Exception, e:
        #    msg = str(e) + "\n" + _traceback.format_exc(e)
        #    raise Exception(msg)
        
    def __call__(self, xtmf_ScenarioNumber, xtmf_WorksheetPath, FilePath):
        self.tool_run_msg = ""

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        if os.path.isfile(xtmf_WorksheetPath): # optionally provide full path to worksheet file
            # check to see if the file is already in the correct location
            head, tail = os.path.split(xtmf_WorksheetPath)
            worksheetLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Worksheets'))
            with open(xtmf_WorksheetPath, 'r') as f:
                checkFile = False
                for line in f:
                    if "name = " in line.lower(): # this is the convention for the table title in the table file
                        tableTitle = line[7:].strip() # grab the table name and remove formatting      
                        checkFile = True
                        break
                if not checkFile:
                    raise Exception("File is not a valid Emme table file")
            if head == worksheetLocation:                
                self.WorksheetPath = [[tableTitle]] # set the table title as a list of lists to feed in to the INRO tool
            else:
                try:
                    shutil.copy2(xtmf_WorksheetPath, worksheetLocation) # copy the worksheet file to the project worksheet directory
                    self.WorksheetPath = [[tableTitle]]
                except:
                    raise Exception("Failed to copy worksheet to project/Worksheets directory")
        else:        
            self.WorksheetPath = [xtmf_WorksheetPath.split(",")] # currently can only handle one path

        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)


    def _Execute(self):

        with _m.logbook_trace(name="{classname}".format(classname=(self.__class__.__name__)),
                                     attributes=self._GetAtts()):

            
            logbookLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Logbook'))
            initialDir = os.listdir(logbookLocation)
            LogTable(worksheet_items_or_folders=self.WorksheetPath, field_separator=",")
            finalDir = os.listdir(logbookLocation)
            newItems = []
            for item in finalDir:
                if item not in initialDir:
                    newItems.append(item)
            for item in newItems:
                try:
                    copy_tree(os.path.abspath(os.path.join(logbookLocation, item)), self.FilePath) # copy folder to chosen path
                    # note: copy_tree will overwrite any file with the same name
                    shutil.rmtree(os.path.abspath(os.path.join(logbookLocation, item))) # clean up
                except Exception, e:
                    msg = str(e) + "\n" + _traceback.format_exc(e)
                    raise Exception(msg)

            

                
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
