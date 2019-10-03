#---LICENSE----------------------
'''
    Copyright 2018 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
    Apply Operator Codes

    Authors: byusuf

    Latest revision by: byusuf
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2018-06-29 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ConvertNCS16toNCS11(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    ncs16_scenario_number = _m.Attribute(_m.InstanceType) # common variable or parameter
    ncs11_scenario_number = _m.Attribute(_m.InstanceType)

    vehicle_conversion = [(1,1),
                           (2,2),
                           (3,3),
                           (4,4),
                           (5,5),
                           (6,6),
                           (7,8),
                           (8,9),
                           (9,10),
                           (10,11),
                           (11,12),
                           (12,13),
                           (13,14),
                           (14,15),
                           (15,16),
                           (16,17),
                           (17,18),
                           (18,19),
                           (19,20)]
    
    vdf_conversion = [(31,51)]

    centroid_conversion = [
        (8503,9710,"GO"),
        (9500,9721,"GO"),
        (9253,9719,"GO"),
        (9252,9718,"GO"),
        (9251,9717,"GO"),
        (9250,9716,"GO"),
        (9005,9715,"GO"),
        (9004,9714,"GO"),
        (8023,9713,"GO"),
        (8022,9712,"GO"),
        (8021,9711,"GO"),
        (8017,9703,"GO"),
        (8018,9704,"GO"),
        (8019,9705,"GO"),
        (8020,9706,"GO"),
        (8500,9707,"GO"),
        (8501,9708,"GO"),
        (8502,9709,"GO"),
        (9255,9730,"GO"),
        (9010,9728,"GO"),
        (9009,9727,"GO"),
        (9008,9726,"GO"),
        (9007,9725,"GO"),
        (9006,9724,"GO"),
        (8761,9741,"GO"),
        (8762,9742,"GO"),
        (8763,9743,"GO"),
        (8764,9744,"GO"),
        (9764,9746,"GO"),
        (8767,9751,"GO"),
        (8766,9750,"GO"),
        (8030,9749,"GO"),
        (8029,9748,"GO"),
        (8032,9753,"GO"),
        (8033,9754,"GO"),
        (8768,9755,"GO"),
        (8770,9757,"GO"),
        (8773,9762,"GO"),
        (8026,9731,"GO"),
        (8027,9732,"GO"),
        (9012,9733,"GO"),
        (9013,9734,"GO"),
        (9014,9735,"GO"),
        (9256,9737,"GO"),
        (9254,9720,"GO"),
        (8760,9740,"GO"),
        (9015,9736,"GO"),
        (8028,9739,"GO"),
        (8765,9745,"GO"),
        (8771,9758,"GO"),
        (8769,9756,"GO"),
        (9765,9747,"GO"),
        (8772,9760,"GO"),
        (9011,9729,"GO"),
        (9751,9761,"GO"),
        (9750,9759,"GO"),
        (9763,9738,"GO"),
        (9016,9763,"UPX"),
        (8025,9723,"GO"),
        (9257,9765,"GO"),
        (9501,9764,"GO"),
        (8774,9766,"GO"),
        (8001,9801,"Subway"),
        (8002,9802,"Subway"),
        (8012,9812,"Subway"),
        (8024,9722,"GO"),
        (8016,9702,"GO"),
        (8003,9803,"Subway"),
        (8004,9804,"Subway"),
        (8031,9752,"GO"),
        (8005,9805,"Subway"),
        (8006,9806,"Subway"),
        (8007,9807,"Subway"),
        (8000,9701,"GO"),
        (8013,9813,"Subway"),
        (8014,9814,"Subway"),
        (8011,9811,"Subway"),
        (8008,9808,"Subway"),
        (8015,9815,"Subway"),
        (8009,9809,"Subway"),
        (8010,9810,"Subway"),
        (9000,9600,"BRT"),
        (9001,9601,"BRT"),
        (9002,9602,"BRT"),
        (8757,9500,"Carpool"),
        (8754,9501,"Carpool"),
        (8755,9502,"Carpool"),
        (8753,9503,"Carpool"),
        (8750,9504,"Carpool"),
        (8758,9505,"Carpool"),
        (8759,9506,"Carpool"),
        (8756,9507,"Carpool"),
        (8751,9508,"Carpool"),
        (8752,9509,"Carpool"),
        (9003,9510,"Carpool"),
        ]

    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Convert from NCS16 to NCS11 v%s" %self.version,
                                description="Converts a network from NCS16 to NCS11 for backwards compatibility.",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='ncs16_scenario_number',
                               title=' NCS16 Scenario:',
                               allow_none=False)
        availableScenarioIds = []
        for i in range(1, _MODELLER.emmebank.dimensions['scenarios'] + 1):
            scenario = _MODELLER.emmebank.scenario(i)
            if scenario == None:
                title = None
            else:
                title = _MODELLER.emmebank.scenario(i).title
            availableScenarioIds.append((i, str(i)+" - "+str(title)))
        
        pb.add_select(tool_attribute_name='ncs11_scenario_number',
                      keyvalues=availableScenarioIds,
                      title='NCS11 Scenario:',
                      note="NCS11 Scenario Number")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            self.scenario = _MODELLER.emmebank.scenario(self.ncs16_scenario_number)
            network = self.scenario.get_network()
            ## change any link with non ncs11 compliant vdf
            ## self._ChangeVDF(ncs16_network)
            for link in network.links():
                if link.volume_delay_func == self.vdf_conversion[0][0]:
                    link.volume_delay_func = self.vdf_conversion[0][1]
            ## convert back to ncs11 compliant vehicle types (where possible)
            for vehicle in network.transit_vehicles():
                vehicle.number = vehicle.number + 50
            for vehicle_number in self.vehicle_conversion:
                vehicle = network.transit_vehicle(vehicle_number[0]+50)
                vehicle.number = vehicle_number[1]
            ## convert back to ncs11 compliant node numbers
            for centroid in self.centroid_conversion:
                if network.node(centroid[0]) is not None: 
                    centroid = network.node(centroid[0])
                    centroid.number = centroid.number + 100000
            for centroid in self.centroid_conversion:
                if network.node(centroid[0] + 100000) is not None: 
                    centroid_node = network.node(centroid[0] + 100000)
                    centroid_node.number = centroid[1]
            ncs11_scenario = _MODELLER.emmebank.scenario(self.ncs11_scenario_number)
            if ncs11_scenario != None:
                _MODELLER.emmebank.delete_scenario(self.ncs11_scenario_number)
            ncs11_scenario = _MODELLER.emmebank.copy_scenario(self.ncs16_scenario_number, self.ncs11_scenario_number)
            ncs11_scenario.publish_network(network)
            title = str(ncs11_scenario.title)
            title=title[0:50].strip()+" - NCS11"
            ncs11_scenario.title = title


    ##########################################################################################################
    
    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
