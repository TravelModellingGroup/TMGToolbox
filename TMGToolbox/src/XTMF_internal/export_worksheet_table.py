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

_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
LogTable = _MODELLER.tool('inro.emme.desktop.log_worksheet_table')
EMME_VERSION = _util.getEmmeVersion(tuple) 

##########################################################################################################

class ExportWorksheetTable(_m.Tool()):

     #---PARAMETERS
    xtmf_ScenarioNumber = _m.Attribute(str)
    xtmf_WorksheetPath = _m.Attribute(str)
    FilePath = _m.Attribute(str) #folder in which to save the output. Folder MUST NOT exist yet.
    WorksheetPath = _m.Attribute(list)

    Scenario = _m.Attribute(_m.InstanceType)
            
    def __init__(self):
        #---Init internal variables
        #self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario   

    def run(self):
        self.tool_run_msg = ""
        
    def __call__(self, xtmf_ScenarioNumber, xtmf_WorksheetPath, FilePath):
        self.tool_run_msg = ""

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        self.WorksheetPath = [xtmf_WorksheetPath.split(",")] # currently can only handle one path

        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)


    def _Execute(self):

        with _m.logbook_trace(name="{classname}".format(classname=(self.__class__.__name__)),
                                     attributes=self._GetAtts()):

            emmebankLocation = _MODELLER.emmebank.path
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
                    copytree(os.path.abspath(os.path.join(logbookLocation, item)), self.FilePath) # copy folder to chosen path
                    shutil.rmtree(os.path.abspath(os.path.join(logbookLocation, item))) # clean up
                except:
                    raise Exception("Copying failed")

            

    def copytree(src, dst, symlinks=False, ignore=None): # standard shutil.copytree will not work if dst path already exists
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks, ignore)
            else:
                shutil.copy2(s, d)
                
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
