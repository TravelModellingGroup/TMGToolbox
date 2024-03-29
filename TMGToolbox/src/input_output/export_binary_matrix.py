from __future__ import print_function
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
'''
#---METADATA---------------------
'''
ExportBinaryMatrix

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Exports matrix data in the new binary format.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-06-06 by pkucirek
    
    1.0.0 Published on 2014-06-09
    
    1.0.1 Tool now checks that the matrix exists.
    
'''

import inro.modeller as _m
import traceback as _traceback
import gzip
import shutil
import os
import tempfile
import six
import array as _array
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_bank = _MODELLER.emmebank
import six
if six.PY3:
    _m.InstanceType = object
    _m.TupleType = object
    _m.ListType = object

##########################################################################################################

class ExportBinaryMatrix(_m.Tool()):
    
    version = '1.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    MATRIX_TYPES = {1: 'ms',
                    2: 'mo',
                    3: 'md',
                    4: 'mf'}
    
    #---PARAMETERS
    
    xtmf_MatrixNumber = _m.Attribute(int)
    xtmf_MatrixType = _m.Attribute(int)
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    
    MatrixId = _m.Attribute(str)
    ExportFile = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Binary Matrix v%s" %self.version,
                     description="Exports a matrix in the special binary format, which is \
                         considerably smaller and quicker to load.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_matrix(tool_attribute_name= 'MatrixId',
                             id= True,
                             title= "Matrix to export")
        
        pb.add_select_file(tool_attribute_name= 'ExportFile',
                           window_type= 'save_file',
                           file_filter= "Emme matrix files | *.mdf ; *.emxd ; *.mtx ; *.mtx.gz \n All files (*.*)",
                           title= "Export File")
        
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False,
                               note= "Only required if scenarios have different zone systems.")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {        
        var tool = new inro.modeller.util.Proxy(%s) ;

        if (tool.scenario_required())
        {
            $("#Scenario").prop("disabled", false);;
        } else {
            $("#Scenario").prop("disabled", true);;
        }
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.text_type)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=bool)
    def scenario_required(self):
        retval = _util.databankHasDifferentZones(_bank)
        print (retval)
        return retval
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_MatrixType, xtmf_MatrixNumber, ExportFile, xtmf_ScenarioNumber):
        
        if not xtmf_MatrixType in self.MATRIX_TYPES:
            raise IOError("Matrix type '%s' is not recognized. Valid types are " %xtmf_MatrixType + 
                          "1 for scalar, 2 for origin, 3 for destination, and "+ 
                          "4 for full matrices.")
        
        self.MatrixId = self.MATRIX_TYPES[xtmf_MatrixType] + str(xtmf_MatrixNumber)
        self.ExportFile = ExportFile
        if _bank.matrix(self.MatrixId) is None:
            raise IOError("Matrix %s does not exist." %self.MatrixId)
        
        if _util.databankHasDifferentZones(_bank):
            self.Scenario = _bank.scenario(xtmf_ScenarioNumber)
            if self.Scenario is None:
                raise Exception("A valid scenario must be specified as there are " +
                                    "multiple zone systems in this Emme project. "+
                                    "'%s' is not a valid scenario." %xtmf_ScenarioNumber)

        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    def _save_matrix_data(self, file_stream, matrix_data):

        matrix_type_index = {"f" : 1, "d" : 2, 'i' : 3, 'I' : 4}[matrix_data.type]
        intBuff = _array.array("I")
        intBuff.append(0xC4D4F1B2) # magic number
        intBuff.append(1) # version number
        intBuff.append(matrix_type_index)
        intBuff.append(matrix_data.num_dimensions)
        for dim in matrix_data.indices:
            intBuff.append(len(dim))
        for dim in matrix_data.indices:
            for entry in dim:
                intBuff.append(entry)
        intBuff.tofile(file_stream)
        for data_array in matrix_data.raw_data:
            data_array.tofile(file_stream)
        return

    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            matrix = _bank.matrix(self.MatrixId)
            
            if _util.databankHasDifferentZones(_bank):
                data = matrix.get_data(self.Scenario)
            else:
                data = matrix.get_data()
            if self.ExportFile[-2:] == "gz":
                if six.PY3:
                    with gzip.open(self.ExportFile, 'wb') as out_file:
                        self._save_matrix_data(out_file, data)
                else:
                    (temp_file_fd, new_file) = tempfile.mkstemp()
                    os.close(temp_file_fd)
                    try:
                        data.save(new_file)
                        with open (new_file, 'rb') as in_file, gzip.open(self.ExportFile, 'wb') as out_file:
                            shutil.copyfileobj(in_file, out_file)
                    finally:
                        os.remove(new_file)
            else:
                with open(self.ExportFile, 'wb') as out_file:
                    self._save_matrix_data(out_file, data)
            
            self.TRACKER.completeTask()

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Matrix" : self.MatrixId,
                "Export File": self.ExportFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
        
        if _util.databankHasDifferentZones(_bank):
            atts['Scenario'] = self.Scenario
            
        return atts
        