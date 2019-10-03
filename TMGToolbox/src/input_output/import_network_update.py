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
IMPORT NETWORK UPDATE

    Authors: pkucirek

    Latest revision by: mattaustin222
    
    
    Opens a Network Update (*.nup) file and applies it to selected scenarios.
    
    NUP files allow network editing macros to be ported to other projects. Normally,
    Emme saves the editing macro's sub-compnents to a folder in the Database
    directory, which prohibits easy sharing of updating macros. Eventually, this
    tool will also allow Python scripts to be executed, but they will have to be
    designed "in good faith" to be compatible.
    
    TO CREATE A NETWORK UPDATE FILE:
    The NUP file is just a renamed ZIP file with the following specification. Two
    text files need to be created and included:
        - info.txt: Contains information and metadata about the update. The first
            line of the file must be the date of the export. Subsequent lines
            will just be printed verbatim to the page. Lines starting with '*'
            will be displayed as lists.
        - run_order.txt: For each line in this file, a script or macro of the same
            name will be executed (currently just macros ending in '.mac' are 
            supported). 
    For each script named in run_order.txt, the corresponding script file MUST also
    exist in the NUP file. For Emme macro scripts, the folder containing the sub-
    components must also exist within the NUP file and have the same name as the
    script. This folder can be copied from the Database folder of the Emme project
    which saved the macro (from a Network Editor session). Finally, the macro
    itself must be edited: replace all instances of the sub-folder's name with '$DIR$'
    For example, if the macro was originally titled "Update_Yonge_St_lanes.mac',
    there will be a folder named "Update_Yong_St_lanes" inside of Database. In the
    .mac file itself, replace all instances of "Update_Yong_St_lanes" with "$DIR$":
        ~<_edb_ 2 211 Update_Yong_St_lanes/00000_nodes
            becomes
        ~<_edb_ 2 211 $DIR$/00000_nodes
    It also recommended to replace the "reports=[macro name]-%s%.rep" line with:
        reports=$REP$-%s%.rep
        ~t9=$REP$-%s%.rep
    This ensures that the reports files are written to the Database folder, not
    the temporary directory (which gets deleted).
    
    Python scripts can also be included in run_order.txt. These scripts are 
    executed IN GOOD FAITH so please try to ensure that they are safe to run
    and are as general as possible. The scenario being updated is saved into the
    locals dictionary as 'nup_scenario' to be accessed by the script if needed.
    For example:
        if 'nup_scenario' in  dir():
            sc = nup_scenario
        else:
            sc = mm.scenario   
    will get the scenario currently being updated by the network updater (or
    the currently-open Primary Scenario if being run as a stand-alone script).
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-04-21 by pkucirek
    
    0.1.1 Added better support for reports
    
    0.2.0 Added support for Python scripts

    0.3.0 Made callable 
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import shutil as _shutil
from os import path
import tempfile as _tf
import zipfile as _zipfile
import sys
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class redirectPrint():
    
    def __init__(self, base):
        self._echo = base
    
    def write(self, statement):
        if not statement.isspace():
            self._echo.write("%s\n" %statement)
            _m.logbook_write(statement)

class ImportNetworkUpdate(_m.Tool()):
    
    version = '0.3.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenarios = _m.Attribute(_m.ListType) # common variable or parameter
    NetworkUpdateFile = _m.Attribute(str)

    xtmf_ScenarioString = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Network Update v%s" %self.version,
                     description="Opens a Network Update (*.nup) file, which contains \
                         scripts and macros used to update one or more scenarios. \
                         <br><br>Macros used to perform a network update are based on \
                         Emme's Network Editor, which can sometimes cause an error \
                         when network elements are missing. It is recommended to check \
                         the Database directory for the created reports file(s). \
                         <br><br><font color='red'><b>Warning:</b></font> This tool \
                         makes irreversible changes to your scenarios. Make sure to \
                         test the update on copies first.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name='Scenarios',
                               title='Scenarios',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='NetworkUpdateFile',
                           window_type='file', file_filter='*.nup',
                           title="Network update file")
        
        pb.add_html("""<div class="t_element" id="NetworkUpdateInfoDiv" style="padding: 0px inherit;">
        </div>""")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;
        
        $("#NetworkUpdateFile").bind('change', function()
        {
            $(this).commit();
            
            //Change the package info
            var info = tool.get_file_info();
            $("#NetworkUpdateInfoDiv").removeAttr( 'style' );
            $("#NetworkUpdateInfoDiv").html(info);
                
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        
        return pb.render()
    
    ##########################################################################################################
    def __call__(self, xtmf_ScenarioString, NetworkUpdateFile):
        
        xtmf_ScenarioList = xtmf_ScenarioString.split(',')
        if xtmf_ScenarioList is None:
            raise Exception("No scenarios chosen!")

        self.Scenarios = []
        for sc in xtmf_ScenarioList:
            try:
                self.Scenarios.append(_m.Modeller().emmebank.scenario(int(sc))) 
            except:
                raise Exception("Error adding scenario %s" %sc)
            
        self.NetworkUpdateFile = NetworkUpdateFile

        if self.NetworkUpdateFile is None or self.NetworkUpdateFile.lower() == "none":
            print "No network update file selected" # won't throw an error if called without a nup file
        else:
            try:
                self._Execute()
            except Exception as e:
                msg = str(e) + "\n" + _traceback.format_exc(e)
                raise Exception(msg)        
        
    def run(self):
        self.tool_run_msg = ""
        
        try:
            if not self.Scenarios: raise Exception("No scenarios selected")
            if not self.NetworkUpdateFile: raise Exception("No network update file selected")
            
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with self._zipFileMANAGER() as zf:
                reader = zf.open('run_order.txt', 'rU')
                try:
                    scripts = [line.strip() for line in reader]
                finally:
                    reader.close()
                                
                self.TRACKER.reset(len(scripts))
                nl = set(zf.namelist())
                
                for script in scripts:
                    if script.endswith(".mac"):
                        if not script in nl:
                            raise IOError("NUP file formatting error: Script %s does not exist" %script)
                        
                        with _m.logbook_trace("Running MACRO %s" %script):
                            self._RunMacro(zf, script)
                    elif script.endswith(".py"):
                        if not script in nl:
                            raise IOError("NUP file formatting error: Script %s does not exist" %script)
                        with _m.logbook_trace("Running PY_SCRIPT %s" %script):
                            self._RunPythonScript(zf, script)
                    else:
                        _m.logbook_write("Script type of '%'s not supported" %script)
                    self.TRACKER.completeTask()


    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _zipFileMANAGER(self):
        # Code here is executed upon entry {
        zf = _zipfile.ZipFile(self.NetworkUpdateFile)
        # }
        try:
            yield zf
        finally:
            zf.close()
    
    @contextmanager
    def _tempDirectoryMANAGER(self):
        databankDirectory = path.dirname(_MODELLER.emmebank.path)
        tempDirectory = _tf.mkdtemp(dir= databankDirectory)
        _m.logbook_write("Created temp directory at %s" %tempDirectory)
        
        try:
            yield tempDirectory 
        finally:
            _shutil.rmtree(tempDirectory, True)  
            _m.logbook_write("Deleted temp directory at %s" %tempDirectory)  
    
    @contextmanager
    def _printRedirectMANAGER(self):
        base = sys.stdout
        sys.stdout = redirectPrint(base)
        
        try:
            yield
        finally:
            sys.stdout = base
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Network Update File": self.NetworkUpdateFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
        
        for i, scenario in enumerate(self.Scenarios):
            key = "Scenario %s" %i
            atts[key] = str(scenario)
            
        return atts 
    
    def _RunMacro(self, zipFile, macroName):
        tool = _MODELLER.tool('inro.emme.prompt.run_macro')
        
        self.TRACKER.startProcess(2 + len(self.Scenarios))
        with self._tempDirectoryMANAGER() as tempFolder:
            relativeName = path.basename(tempFolder)
            
            prefix = path.splitext(macroName)[0]
            #---1: Copy the macro's required files
            filesToExtract = [name for name in zipFile.namelist() \
                              if name.startswith("%s/" %prefix) or \
                              name.startswith("%s\\" %prefix)]
            for name in filesToExtract:
                zipFile.extract(name, tempFolder)
            self.TRACKER.completeSubtask()
            
            #---2: Parse/copy macro
            reader = zipFile.open(macroName, 'rU')    
            try:
                with open(path.join(tempFolder, macroName), 'w') as writer:
                    for line in reader:
                        line = line.replace("$REP$", macroName)
                        if line.startswith("~<"):
                            line = line.replace('$DIR$', "%s/%s" %(relativeName, prefix))
                        elif line.startswith("comment="):
                            continue #Skips commenting to logbook
                        writer.write(line)
            finally:
                reader.close()
            self.TRACKER.completeSubtask()
            
            #---3: Run the macro on the given scenarios
            for sc in self.Scenarios:
                tool(macro_name= path.join(tempFolder, macroName),
                     scenario= sc)
                self.TRACKER.completeSubtask()
        #File cleanup is handled by the context managers
    
    def _RunPythonScript(self, zipFile, scriptName):
        self.TRACKER.startProcess(len(self.Scenarios))
        
        with self._tempDirectoryMANAGER() as tempFolder:
            zipFile.extract(scriptName, tempFolder)
            scriptFile = path.join(tempFolder, scriptName)
            
            for sc in self.Scenarios:
                nup_scenario = sc
                with self._printRedirectMANAGER():
                    execfile(scriptFile, locals())
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=unicode)
    def get_file_info(self):
        '''
        Reads the info file with which accompanies the update. The first
        line is assumed to be the export date, with subsequent lines being
        comments and metadata. Lines beginning with * are treated as
        ordered list items.
        '''
        with self._zipFileMANAGER() as zf:
            
            info = zf.open('info.txt')
            lines = info.readlines()
            '''
            lines = [Date of update, subsequent comment lines]
            '''
            
            dateLine = "<b>Date:</b> %s" %lines[0]
            htmlLines = []
            listBuffer = []
            for line in lines[1:]:
                if listBuffer:
                    if line.startswith("*"):
                        listBuffer.append(line[1:])
                    else:
                        htmlList = "<ol>"
                        for item in listBuffer:
                            htmlList += "<li>%s" %item
                        htmlList += "</ol>"
                        htmlLines[len(htmlLines) - 1] += htmlList
                        listBuffer = []
                        htmlLines.append(line)
                else:
                    if line.startswith("*"):
                        listBuffer.append(line[1:])
                    else:
                        htmlLines.append(line)
            if listBuffer:
                htmlList = "<ol>"
                for item in listBuffer:
                    htmlList += "<li>%s" %item
                htmlList += "</ol>"
                htmlLines[len(htmlLines) - 1] += htmlList
                listBuffer = []
            cell = "<br>".join([dateLine] + htmlLines)
            
            return "<table border='1' width='90&#37'><tbody><tr><td valign='top'>%s</td></tr></tbody></table>" %cell
        