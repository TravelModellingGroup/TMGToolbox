'''
    Copyright 2019 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Remove Redundant Functions

    Authors: Luna Xi

    Latest revision by: 
    
    [Description]
    This tool is used to compare the functions in the networks and the database, 
    it will export all redundant functions (i.e., not used in any scenario) as an individual file 
    and remove them from the database.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_M = _m.Modeller() 
_ExportFunctions = _M.tool('inro.emme.data.function.export_functions')
_DeleteFunctions = _M.tool('inro.emme.data.function.delete_function')
_util = _M.module('tmg.common.utilities')
_tmgTPB = _M.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class RemoveRedundantFunctions(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ExportFile = _m.Attribute(str)


    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _M.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Remove Redundant Functions from Database v%s" %self.version,
                     description="Compare the functions used in the networks with those stored in the database. All \
                     redundant functions (i.e., not used in any scenario) will be exported as an individual file \
                     and will be removed from the database.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
#        pb.add_select_scenario(tool_attribute_name='Scenario',
#                               title='Scenario:',
#                               allow_none=False)

        pb.add_select_file(tool_attribute_name= 'ExportFile',
                           window_type= 'save_file',
                           file_filter= "*.txt \n All files (*.*)",
                           title= "Export Redundant Functions")

        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    def __call__(self, ExportFile):
        
        self.ExportFile = ExportFile

        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):

            # check the functions in the emme database
            fd_database, ft_database, fp_database, fo_database = self._CheckDatabase()

            # check functions used in all scenarios/networks
            fd_network, ft_network, fp_network = self._CheckNetworks()

            # compare the functions between networks and the database, export and remove the redundant ones
            self._CompareFunctions(self.ExportFile, fd_database, ft_database, fp_database, fd_network, ft_network, fp_network)

            self.TRACKER.completeTask()

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Export File": self.ExportFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def unique_append(self, function_list, function_number):
        if (function_number > 0) and (function_number not in function_list):
            function_list.append(function_number)

    # check functions in the Emme database
    def _CheckDatabase(self):
        functions = _M.emmebank.functions()
        database_fd_str = []
        database_ft_str = []
        database_fp_str = []
        database_fo_str = []

        for f in functions:
            f_type = str(f)[0:2]
            if f_type == "fd":
                database_fd_str.append(str(f)[2:])
            elif f_type == "ft":
                database_ft_str.append(str(f)[2:])
            elif f_type == "fp":
                database_fp_str.append(str(f)[2:])
            else:
                database_fo_str.append(str(f)[2:])
                    
        database_fd = list(map(int, database_fd_str))
        database_ft = list(map(int, database_ft_str))
        database_fp = list(map(int, database_fp_str))
        database_fo = list(map(int, database_fo_str))

        print "There are %s Auto Volume Delay (fd) functions in the database." %len(database_fd)
        print "There are %s Transit Time (ft) functions in the database." %len(database_ft)
        print "There are %s Turn Penalty (fp) functions in the database." %len(database_fp)
        print "There are %s other types of functions in the database." %len(database_fo)

        return database_fd, database_ft, database_fp, database_fo

    # check functions used in all scenarios/networks
    def _CheckNetworks(self):
        scens = _M.emmebank.scenarios()
        contained_fd =[]
        contained_ft =[]
        contained_fp =[]

        for scen_id in scens:
            network = _M.emmebank.scenario(scen_id).get_network()
                
            for l in network.links():
                self.unique_append(contained_fd, l.volume_delay_func)
                        
            for sg in network.transit_segments():
                self.unique_append(contained_ft, sg.transit_time_func)
                        
            for r in network.turns():
                self.unique_append(contained_fp, r.penalty_func)
                        
        print "There are %s Auto Volume Delay (fd) functions used in all scenarios/networks." %len(contained_fd)
        print "There are %s Transit Time (ft) functions used in all scenarios/networks." %len(contained_ft)
        print "There are %s Turn Penalty (fp) functions used in all scenarios/networks." %len(contained_fp)

        return contained_fd, contained_ft, contained_fp

    # compare the functions between networks and the database, export and remove the redundant ones
    def _CompareFunctions(self, ExportFile, database_fd, database_ft, database_fp, contained_fd, contained_ft, contained_fp):

        Redun_functions = []

        self.compare_append("fd", Redun_functions, database_fd, contained_fd)
        self.compare_append("ft", Redun_functions, database_ft, contained_ft)
        self.compare_append("fp", Redun_functions, database_fp, contained_fp)

        ## export redundant functions
        if len(Redun_functions) == 0:
            print "No redundant function is found."
        else:
            _ExportFunctions(functions = Redun_functions, export_file = self.ExportFile, append_to_file = False)

        # delete redundant functions from database
        for redun_i in Redun_functions:
            if redun_i is not None:
                _DeleteFunctions(redun_i)

        print "Removed %s functions from the database." %(len(Redun_functions))

    def compare_append(self, type, functionlist, database_functions, contained_functions):
        unused_functions = list(set(database_functions) - set(contained_functions))
        for i in unused_functions:
            functionlist.append(_M.emmebank.function(type + str(i)))


    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
