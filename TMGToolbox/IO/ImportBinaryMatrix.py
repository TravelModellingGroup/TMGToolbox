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
Import Binary Matrix

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-06-30 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from inro.emme.matrix import MatrixData as _MatrixData
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
_bank = _MODELLER.emmebank

##########################################################################################################

class ImportBinaryMatrix(_m.Tool()):
    
    version = '0.0.1'
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
    ImportFile = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    MatrixDescription = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Import Binary Matrix v%s" %self.version,
                     description="Imports a binary matrix from file.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_file(tool_attribute_name= 'ImportFile',
                           window_type= 'file',
                           file_filter= '*.emxd; *.mtx',
                           title= "Import File")
        
        pb.add_select_matrix(tool_attribute_name= 'MatrixId',
                             id= True,
                             title= "Matrix",
                             note= "Select an existinf matrix in which to save data.")
        
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
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=bool)
    def scenario_required(self):
        retval = _util.databankHasDifferentZones(_bank)
        print retval
        return retval
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_MatrixType, xtmf_MatrixNumber, ImportFile, xtmf_ScenarioNumber,
                 MatrixDescription):
        
        if not xtmf_MatrixType in self.MATRIX_TYPES:
            raise IOError("Matrix type '%s' is not recognized. Valid types are " %xtmf_MatrixType + 
                          "1 for scalar, 2 for origin, 3 for destination, and "+ 
                          "4 for full matrices.")
        
        self.MatrixId = self.MATRIX_TYPES[xtmf_MatrixType] + str(xtmf_MatrixNumber)
        
        if _util.databankHasDifferentZones(_bank):
            self.Scenario = _bank.scenario(xtmf_ScenarioNumber)
            if self.Scenario == None:
                raise Exception("A valid scenario must be specified as there are " +
                                    "multiple zone systems in this Emme project. "+
                                    "'%s' is not a valid scenario." %xtmf_ScenarioNumber)
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="%s v%s" %(self.__class__.__name__, self.version), \
                              attributes= self._GetAtts()):
            matrix = _util.initializeMatrix(self.MatrixId)
            if self.MatrixDescription:
                matrix.description = self.MatrixDescription
            
            data = _MatrixData.load(self.ImportFile)
            
            origins, destinations = data.indices
            origins = set(origins)
            destinations = set(destinations)
            if origins ^ destinations:
                raise Exception("Asymmetrical matrix detected. Matrix must be square.")
            
            if _util.databankHasDifferentZones(_bank):
                
                zones = set(self.Scenario.zone_numbers)
                if zones ^ origins:
                    
                    with _m.logbook_trace("Zones in matrix file but not in scenario"):
                        for index in origins - zones: _m.logbook_write(index)
                    with _m.logbook_trace("Zones in scenario but not in file"):
                        for index in zones - origins: _m.logbook_write(index)
                    
                    raise Exception("Matrix zones not compatible with scenario %s. Check logbook for details." %self.Scenario)
                
                matrix.set_data(data, scenario= self.Scenario)
            else:
                sc = _bank.scenarios()[0]
                zones = set(sc.zone_numbers)
                if zones ^ origins:
                    
                    with _m.logbook_trace("Zones in matrix file but not in scenario"):
                        for index in origins - zones: _m.logbook_write(index)
                    with _m.logbook_trace("Zones in scenario but not in file"):
                        for index in zones - origins: _m.logbook_write(index)
                    
                    raise Exception("Matrix zones not compatible with emmebank zone system. Check Logbook for details.")
                
                matrix.set_data(data)
            
            self.TRACKER.completeTask()
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
        