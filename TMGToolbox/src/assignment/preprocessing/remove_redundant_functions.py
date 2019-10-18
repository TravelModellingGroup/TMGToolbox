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
_exportFcns = _M.tool('inro.emme.data.function.export_functions')
_deleteFcns = _M.tool('inro.emme.data.function.delete_function')
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
    
    def __call__(self, xtmf_ScenarioNumber, ExportFile):
        
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        self.ExportFile = ExportFile

        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):

            # check functions in the Emme database
            fcns = _M.emmebank.functions()
            fdlist = []
            ftlist = []
            fplist = []
            folist = []

            for f in fcns:
                f_type = str(f)[0:2]
                if f_type == "fd":
                    fdlist.append(str(f)[2:])
                elif f_type == "ft":
                    ftlist.append(str(f)[2:])
                elif f_type == "fp":
                    fplist.append(str(f)[2:])
                else:
                    folist.append(str(f)[2:])
                    
            fdlist_database = list(map(int, fdlist))
            ftlist_database = list(map(int, ftlist))
            fplist_database = list(map(int, fplist))
            folist_database = list(map(int, folist))

            print "There are %s Auto Volume Delay (fd) functions in the database." %len(fdlist_database)
            print "There are %s Transit Time (ft) functions in the database." %len(ftlist_database)
            print "There are %s Turn Penalty (fp) functions in the database." %len(fplist_database)
            print "There are %s other types of functions in the database." %len(folist_database)


            # check functions used in all scenarios/networks
            scens = _M.emmebank.scenarios()
            fdlist_net =[]
            ftlist_net =[]
            fplist_net =[]

            for scen_id in scens:
                lks = _M.emmebank.scenario(scen_id).get_network().links()
                segs = _M.emmebank.scenario(scen_id).get_network().transit_segments()
                trns = _M.emmebank.scenario(scen_id).get_network().turns()
                
                for l in lks:
                    l_fcn = l.volume_delay_func 
                    if (l_fcn > 0) and (l_fcn not in fdlist_net):
                        fdlist_net.append(l_fcn)
                        
                for sg in segs:
                    sg_fcn = sg.transit_time_func 
                    if (sg_fcn > 0) and (sg_fcn not in ftlist_net):
                        ftlist_net.append(sg_fcn)
                        
                for r in trns:
                    r_fcn = r.penalty_func 
                    if (r_fcn > 0) and (r_fcn not in fplist_net):
                        fplist_net.append(r_fcn)
                        
            print "There are %s Auto Volume Delay (fd) functions used in all scenarios/networks." %len(fdlist_net)
            print "There are %s Transit Time (ft) functions used in all scenarios/networks." %len(ftlist_net)
            print "There are %s Turn Penalty (fp) functions used in all scenarios/networks." %len(fplist_net)

            
            # compare the functions between networks and the database
            fdlist_diff = list(set(fdlist_database) - set(fdlist_net))
            ftlist_diff = list(set(ftlist_database) - set(ftlist_net))
            fplist_diff = list(set(fplist_database) - set(fplist_net))
            
            Redun_fcns = []
            
            for fd_i in fdlist_diff:
                fd_id = "fd%s" %fd_i
                Redun_fcns.append(_M.emmebank.function(fd_id))
                
            for ft_i in ftlist_diff:
                ft_id = "ft%s" %ft_i
                Redun_fcns.append(_M.emmebank.function(ft_id))
                
            for fp_i in fplist_diff:
                fp_id = "fp%s" %fp_i
                Redun_fcns.append(_M.emmebank.function(fp_id))


            # export redundant functions
            if len(Redun_fcns) == 0:
                print "No redundant function is found."
            else:
                _exportFcns(functions = Redun_fcns, export_file = self.ExportFile, append_to_file = False)

            
            # delete redundant functions from database
            for redun_i in Redun_fcns:
                if redun_i is not None:
                    _deleteFcns(redun_i)

            print "Removed %s functions from the database." %(len(Redun_fcns))

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

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    