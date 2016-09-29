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
Create Aggregation Selection File

    Authors: Matt Austin

    Latest revision by: mattaustin222
    
    
    Creates the .csv file required for using the Create Transit Time Period tool.
    Currently, line groups are defined within this tool code.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-01-19 by mattaustin222
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import csv
from inro.emme.core.exception import ModuleError
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class CreateAggregationSelectionFile(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    COLON = ':'
    COMMA = ','
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    BaseScenario = _m.Attribute(_m.InstanceType)
    
    ExportFile = _m.Attribute(str)

    TorontoSurfaceAgg = _m.Attribute(int)
    TorontoSubwayAgg = _m.Attribute(int)
    MississaugaAgg = _m.Attribute(int)
    DurhamAgg = _m.Attribute(int)
    YorkAgg = _m.Attribute(int)
    BramptonAgg = _m.Attribute(int)
    OakvilleAgg = _m.Attribute(int)
    BurlingtonAgg = _m.Attribute(int)
    MiltonAgg = _m.Attribute(int)
    HSRAgg = _m.Attribute(int)
    GORailAgg = _m.Attribute(int)
    GOBusAgg = _m.Attribute(int)
        
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        self.TorontoSurfaceAgg = 1
        self.TorontoSubwayAgg = 1
        self.MississaugaAgg = 1
        self.DurhamAgg = 1
        self.YorkAgg = 1
        self.BramptonAgg = 1
        self.OakvilleAgg = 1
        self.BurlingtonAgg = 1
        self.MiltonAgg = 1
        self.HSRAgg = 1
        self.GORailAgg = 2
        self.GOBusAgg = 2
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Aggregation Selection File v%s" %self.version,
                     description="Creates an aggregation selection file that can be \
                         used with the Create Transit Time Period Tool. Every line in \
                         the network requires a aggregation type and this tool automates \
                         that process. For each line group listed, please select an \
                         aggregation type.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Base Scenario',
                               allow_none=False)
                
        pb.add_header("DATA FILES")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           title="File name",
                           window_type='save_file',
                           file_filter="*.csv")
        
        pb.add_header("TOOL INPUTS")
        
        keyval1 = {1:'Naive', 2:'Average'}
        pb.add_radio_group(tool_attribute_name='TorontoSurfaceAgg', 
                           keyvalues= keyval1,
                           title= "TTC Surface Routes")
        pb.add_radio_group(tool_attribute_name='TorontoSubwayAgg', 
                           keyvalues= keyval1,
                           title= "TTC Subway Routes")
        pb.add_radio_group(tool_attribute_name='MississaugaAgg', 
                           keyvalues= keyval1,
                           title= "MiWay Routes")
        pb.add_radio_group(tool_attribute_name='DurhamAgg', 
                           keyvalues= keyval1,
                           title= "Durham Routes")
        pb.add_radio_group(tool_attribute_name='YorkAgg', 
                           keyvalues= keyval1,
                           title= "YRT/VIVA Routes")
        pb.add_radio_group(tool_attribute_name='BramptonAgg', 
                           keyvalues= keyval1,
                           title= "Brampton Routes")
        pb.add_radio_group(tool_attribute_name='OakvilleAgg', 
                           keyvalues= keyval1,
                           title= "Oakville Routes")
        pb.add_radio_group(tool_attribute_name='BurlingtonAgg', 
                           keyvalues= keyval1,
                           title= "Burlington Routes")
        pb.add_radio_group(tool_attribute_name='MiltonAgg', 
                           keyvalues= keyval1,
                           title= "Milton Routes")
        pb.add_radio_group(tool_attribute_name='HSRAgg', 
                           keyvalues= keyval1,
                           title= "HSR Routes")
        pb.add_radio_group(tool_attribute_name='GORailAgg', 
                           keyvalues= keyval1,
                           title= "GO Rail Routes")
        pb.add_radio_group(tool_attribute_name='GOBusAgg', 
                           keyvalues= keyval1,
                           title= "GO Bus Routes")

        return pb.render()
    
    ##########################################################################################################
        
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
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            groups = self._DefineGroups()
            
            with _util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_LINE', default = 1, description = "Agg Type") as aggType:
                self._AssignAggType(groups, aggType.id)
                network = self.BaseScenario.get_network()
                self.TRACKER.completeTask()
                print "Loaded network" 
                self._WriteAggSelections(network, aggType.id)

            

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.BaseScenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 

    def _DefineGroups(self):
        GroupIds = []
        GroupIds.append(['T_____', self.TorontoSurfaceAgg, 'TTC Surface'])
        GroupIds.append(['TS____', self.TorontoSubwayAgg, 'TTC Subway']) #must follow surface routes, since pattern is a subset
        GroupIds.append(['M_____', self.MississaugaAgg, 'MiWay'])
        GroupIds.append(['D_____', self.DurhamAgg, 'Durham'])
        GroupIds.append(['Y_____', self.YorkAgg, 'YRT/VIVA'])
        GroupIds.append(['B_____', self.BramptonAgg, 'Brampton'])
        GroupIds.append(['HO____', self.OakvilleAgg, 'Oakville'])
        GroupIds.append(['HB____', self.BurlingtonAgg, 'Burlington'])
        GroupIds.append(['HM____', self.MiltonAgg, 'Milton'])
        GroupIds.append(['W_____', self.HSRAgg, 'HSR'])
        GroupIds.append(['GT____', self.GORailAgg, 'GO Rail'])
        GroupIds.append(['GB____', self.GOBusAgg, 'GO Bus'])
        return GroupIds

    def _AssignAggType(self, groups, aggTypeId):

        tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
        def getSpec(value, selection):
            return {
                "result": aggTypeId,
                "expression": str(value),
                "aggregation": None,
                "selections": {
                    "transit_line": selection
                },
                "type": "NETWORK_CALCULATION"
            }

        i = 0
        for items in groups:
            selector = groups[i][0]
            groupAgg = groups[i][1]
            id = groups[i][2]
            i += 1
            spec = getSpec(groupAgg, selector)
            try:
                tool(spec, scenario= self.BaseScenario)
            except ModuleError:
                msg = "Emme runtime error processing line group '%s'." %id
                _m.logbook_write(msg)
                print msg
                raise

            msg = "Loaded group %s: %s" %(groupAgg, id)
            print msg
            _m.logbook_write(msg)

    def _WriteAggSelections(self, network, aggTypeId):
        with open(self.ExportFile, 'wb') as csvfile:
            aggWrite = csv.writer(csvfile, delimiter = ',')
            aggWrite.writerow(['emme_id', 'agg_type'])
            for line in network.transit_lines():
                if line[aggTypeId] == 1: aggWrite.writerow([line.id, 'naive'])                    
                else : aggWrite.writerow([line.id, 'average'])                    
                
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg