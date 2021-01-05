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
Execute Python Script

    Authors: Peter Kucirek    
    
    Runs a Python Script embedded in a file.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created on March 27, 2013
    
    0.1.1 Fixed a problem where static variables in the script would raise a NameError.
    
    0.2.0 Upgraded to print more readily to Modeller's Python Console window
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
import sys

##########################################################################################################

class ExecutePythonScript(_m.Tool()):
    
    version = '0.2.0'
    tool_run_msg = ""
    
    #---Variable definitions
    filename = _m.Attribute(str)
    xtmf_fileName = _m.Attribute(str)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Execute Python Script",
                                description="A powerful utility Tool which facilitates executing a single Python script.\
                                <br><br>All '<b>print</b>' statements get re-directed to the logbook.",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_file(tool_attribute_name="filename", window_type="file",
                           title="Script:", 
                           file_filter="*.py")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""        
        try:
            self._execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Script execution complete.")
    
    def __call__(self, xtmf_fileName):
        self.filename = xtmf_fileName
        try:
            self._execute()
        except Exception as e:
            raise Exception(_traceback.format_exc())
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            _m.logbook_write("Executing Python script from file '%s'" %self.filename)
            
            with self._printRedirectMANAGER():
                execfile(self.filename, locals())

    ##########################################################################################################
    
    @contextmanager
    def _printRedirectMANAGER(self):
        base = sys.stdout
        sys.stdout = redirectPrint(base)
        
        try:
            yield
        finally:
            sys.stdout = base
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Script File" : self.filename,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
            
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
class redirectPrint():
    
    def __init__(self, base):
        self._echo = base
    
    def write(self, statement):
        if not statement.isspace():
            self._echo.write("%s\n" %statement)
            _m.logbook_write(statement)
            
    
    