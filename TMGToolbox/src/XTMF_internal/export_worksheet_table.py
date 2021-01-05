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
    0.0.2 Updated to set Primary Scenario properly by JamesVaughan
    
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
    xtmf_WorksheetPaths = _m.Attribute(str)
    FilePath = _m.Attribute(str) 
    FileName = _m.Attribute(str) 
    WorksheetPaths = _m.Attribute(list)

    Scenario = _m.Attribute(_m.InstanceType)

            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   
        self.WorksheetPaths = []

    def run(self):
        self.tool_run_msg = ""
        #testPath = "C:\Users\matta_000\Documents\EMME Projects\SmartTrack\Worksheets\TestModes.emt|C:\Users\matta_000\Documents\EMME Projects\SmartTrack\Worksheets\TestModes2.emt"
        #self.FilePath = "C:\Users\matta_000\Documents\XTMF\Projects\Test"
        #self.FileName = "TestFile.csv"

        #for paths in testPath.split("|"):
        #    if os.path.isfile(paths): # optionally provide full path to worksheet file
        #        # check to see if the file is already in the correct location
        #        head, tail = os.path.split(paths)
        #        worksheetLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Worksheets'))
        #        with open(paths, 'r') as f:
        #            checkFile = False
        #            for line in f:
        #                if "name = " in line.lower(): # this is the convention for the table title in the table file
        #                    tableTitle = line[7:].strip() # grab the table name and remove formatting      
        #                    checkFile = True
        #                    break
        #            if not checkFile:
        #                raise Exception("File is not a valid Emme table file")
        #        if head == worksheetLocation:                
        #            self.WorksheetPaths.append([tableTitle]) # set the table title as a list of lists to feed in to the INRO tool
        #        else:
        #            try:
        #                shutil.copy2(paths, worksheetLocation) # copy the worksheet file to the project worksheet directory
        #                self.WorksheetPaths.append([tableTitle])
        #            except:
        #                raise Exception("Failed to copy worksheet to project/Worksheets directory")
        #    else:        
        #        self.WorksheetPaths.append(paths.split(",")) # currently can only handle one path

        #try:
        #    self._Execute()
        #except Exception as e:
        #    msg = str(e) + "\n" + _traceback.format_exc()
        #    raise Exception(msg)

        
    def __call__(self, xtmf_ScenarioNumber, xtmf_WorksheetPaths, FilePath, FileName):
        self.tool_run_msg = ""

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
                
        for paths in xtmf_WorksheetPaths.split("|"):
            if os.path.isfile(paths): # optionally provide full path to worksheet file
                # check to see if the file is already in the correct location
                head, tail = os.path.split(paths)
                worksheetLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Worksheets'))
                with open(paths, 'r') as f:
                    checkFile = False
                    for line in f:
                        if "name = " in line.lower(): # this is the convention for the table title in the table file
                            tableTitle = line[7:].strip() # grab the table name and remove formatting      
                            checkFile = True
                            break
                    if not checkFile:
                        raise Exception("File is not a valid Emme table file")
                if head == worksheetLocation:                
                    self.WorksheetPaths.append([tableTitle]) # set the table title as a list of lists to feed in to the INRO tool
                else:
                    try:
                        shutil.copy2(paths, worksheetLocation) # copy the worksheet file to the project worksheet directory
                        self.WorksheetPaths.append([tableTitle])
                    except:
                        raise Exception("Failed to copy worksheet to project/Worksheets directory")
            else:        
                self.WorksheetPaths.append(paths.split(",")) # currently can only handle one path

        self.FileName = FileName

        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)


    def _Execute(self):

        with _m.logbook_trace(name="{classname}".format(classname=(self.__class__.__name__)),
                                     attributes=self._GetAtts()):

            
            logbookLocation = os.path.abspath(os.path.join(os.path.dirname(emmebankLocation), os.pardir, 'Logbook'))
            initialDir = os.listdir(logbookLocation)
            #we need to do this in since the active scenario is executed in the call method.
            _MODELLER.desktop.data_explorer().replace_primary_scenario(self.Scenario)
            LogTable(worksheet_items_or_folders=self.WorksheetPaths, field_separator=",")
            finalDir = os.listdir(logbookLocation)
            newItems = []
            count = 0
            if self.FileName:
                fileNameSplit = self.FileName.split(".")
                fileNameHead = fileNameSplit[0]
                fileNameExt = fileNameSplit[1]
                for item in finalDir:
                    if item not in initialDir:                        
                        oldOutputFiles = os.listdir(os.path.join(logbookLocation, item))
                        
                        for file in oldOutputFiles:
                            if count == 0:
                                fileNameInsert = ""
                            else:
                                fileNameInsert = str(count)
                            os.renames(os.path.join(logbookLocation, item, file), 
                                        os.path.join(logbookLocation, item, fileNameHead + fileNameInsert + "." + fileNameExt))
                            count += 1
                        newItems.append(item)
                            
            else:
                for item in finalDir:
                    if item not in initialDir:
                        newItems.append(item)
            for item in newItems:
                try:
                    copy_tree(os.path.abspath(os.path.join(logbookLocation, item)), self.FilePath) # copy folder to chosen path
                    # note: copy_tree will overwrite any file with the same name
                    shutil.rmtree(os.path.abspath(os.path.join(logbookLocation, item))) # clean up
                except Exception as e:
                    msg = str(e) + "\n" + _traceback.format_exc()
                    raise Exception(msg)

            

                
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
