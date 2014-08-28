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
Convert Vehicles

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Converts an existing DMG2001 standard network to NCS11 vehicle definitions.
        
'''
#---VERSION HISTORY
'''
    0.1.1 Created.
    
    0.1.2 Fixed a minor bug with respect to LRT vehicles
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_util = _m.Modeller().module('TMG2.Common.Utilities')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ConvertVehicles(_m.Tool()):
    
    version = '0.1.2'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Convert Vehicles v%s" %self.version,
                                description="Converts vehicle definitions and properties \
                                    according to NCS11 definitions.",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name="scenario",
                               title="Select scenario",
                               allow_none=False)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.")
    
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            network = self.scenario.get_network()
            
            self._prepVehicleLineMap(network)
            
            #---Create new vehicle ids
            with _m.logbook_trace("Adding vehicle 19"):
                v19 = network.create_transit_vehicle(19, 'g') # Unused.
                self._changeVehicleProperties(v19, "DblDeckBus", 2.5, 80, 80)
            
            with _m.logbook_trace("Adding vehicle 18"):
                v18 = network.create_transit_vehicle(18, 'g') 
                self._replaceVehicle(network.transit_vehicle(10), v18) #Copy old V10
                self._changeVehicleProperties(v18, "GoBus", 2.5, 55, 55)
            
            with _m.logbook_trace("Adding vehicle 17"):
                v17 = network.create_transit_vehicle(17, 'q') # Reserved.
                self._changeVehicleProperties(v17, description="BRT")
            
            with _m.logbook_trace("Adding vehicle 16"):
                v16 = network.create_transit_vehicle(16, 'b') #Copy old V7
                self._replaceVehicle(network.transit_vehicle(7), v16)
                self._changeVehicleProperties(v16, "Bus18", aeq=3.0, scap=55, tcap=85)
            
            with _m.logbook_trace("Adding vehicle 15"):
                v15 = network.create_transit_vehicle(15, 'b') # Maybe this should be 'q'?
                self._changeVehicleProperties(v15, "Deluxe18", 3.0, 70, 70)
            
            with _m.logbook_trace("Adding vehicle 14"):
                v14 = network.create_transit_vehicle(14, 'b') # Maybe this should be 'q'?
                self._changeVehicleProperties(v14, "Deluxe12", 2.5, 45, 45)
            
            with _m.logbook_trace("Adding vehicle 13"):
                v13 = network.create_transit_vehicle(13, 'b') # Copy old V8
                self._replaceVehicle(network.transit_vehicle(8), v13)
                self._changeVehicleProperties(v13, "Bus12", 2.5, 35, 55)
            
            with _m.logbook_trace("Adding vehicle 12"):
                v12 = network.create_transit_vehicle(12, 'b')
                self._replaceVehicle(network.transit_vehicle(9), v12) # Copy old V9
                self._changeVehicleProperties(v12, "Bus9", 2.5, 25, 40)
            
            with _m.logbook_trace("Adding vehicle 11"):
                v11 = network.create_transit_vehicle(11, 's') # Unused (new TTC SC)
                self._changeVehicleProperties(v11, "LFLRV30", 3.5, 70, 130)
            
            #---Move old vehicle ids
            with _m.logbook_trace("Modifying vehicle 10"):
                v10 = network.transit_vehicle(10)
                self._changeVehicleMode(network, v10, 's')
                self._replaceVehicle(network.transit_vehicle(6), v10) # Copy old V6
                self._changeVehicleProperties(v10, "ALRV23", 3.5, 60, 110)
            
            with _m.logbook_trace("Modifying vehicle 9"):
                v9 = network.transit_vehicle(9)
                self._changeVehicleMode(network, v9, 's')
                self._replaceVehicle(network.transit_vehicle(5), v9) # Copy old V5
                self._changeVehicleProperties(v9, "CLRV16", 3.0, 45, 75)
            
            with _m.logbook_trace("Modifying vehicle 8"):
                v8 = network.transit_vehicle(8)
                self._changeVehicleMode(network, v8, 'l') # Reserved (Eglinton Crosstown LRT)
                self._changeVehicleProperties(v8, "LRV")
            
            with _m.logbook_trace("Modifying vehicle 7"):
                v7 = network.transit_vehicle(7)
                self._changeVehicleMode(network, v7, 'l')
                self._replaceVehicle(network.transit_vehicle(4), v7) # Copy old V4
                self._changeVehicleProperties(v7, "SCxROW", scap=45, tcap=75)
            
            with _m.logbook_trace("Modifying vehicle 6"):
                v6 = network.transit_vehicle(6)
                self._changeVehicleMode(network, v6, 'm') # Unused (new subway Rocket cars)
                self._changeVehicleProperties(v6, "Sub6carRkt", scap=400, tcap=1100)
            
            with _m.logbook_trace("Modifying vehicle 5"):
                v5 = network.transit_vehicle(5)
                self._changeVehicleMode(network, v5, 'm')
                self._replaceVehicle(network.transit_vehicle(2), v5) # Copy old V2
                self._changeVehicleProperties(v5, "Sub6carT1", scap=400, tcap=1000)
                '''
                TODO:
                - Hard code the re-coding of Sheppard subway
                '''
            
            with _m.logbook_trace("Modifying vehicle 4"):
                v4 = network.transit_vehicle(4)
                self._changeVehicleMode(network, v4, 'm')
                self._changeVehicleProperties(v4, "Sub4carT1", scap=260, tcap=670)
            
            with _m.logbook_trace("Modifying vehicle 3"):
                v3 = network.transit_vehicle(3)
                self._changeVehicleProperties(v3, "SRT4car", scap=120, tcap=220)
            
            with _m.logbook_trace("Modifying vehicle 2"):
                v2 = network.transit_vehicle(2)
                self._changeVehicleMode(network, v2, 'r')
                self._changeVehicleProperties(v2, "GoTrain12", scap=1900, tcap=1900)
            
            with _m.logbook_trace("Modifying vehicle 1"):
                #v1 remains unchanged.
                v1 = network.transit_vehicle(1)
                self._changeVehicleProperties(v1, "GoTrain10", scap=1600, tcap=1900)
                
            self.scenario.publish_network(network)

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _prepVehicleLineMap(self, network):
        self.vm = {} # Set up vehicle map

        for line in network.transit_lines():
            try:
                self.vm[line.vehicle].append(line)
            except KeyError, ke:
                self.vm[line.vehicle] = [line]
    
    def _checkFixScenario(self, network):
        vehiclesToBeDeleted = []
    
        for veh in network.transit_vehicles():
            if self.veh.number <= 10:
                continue
            
            if self.veh in self.vm:
                raise Exception("A vehicle id not compliant with DMG2001 was used in \
                    the network and cannot be removed as it is being used by %s transit \
                    line(s)." %len(self.vm[veh]))
            
            vehiclesToBeDeleted.append(veh.number)
        
        for id in vehiclesToBeDeleted:
            network.delete_transit_vehicle(id)
            _m.logbook_write("Deleted unused vehicle %s" %id)
    
    def _replaceVehicle(self, oldVehicle, newVehicle):
        if not oldVehicle in self.vm:
            return
        
        for line in self.vm[oldVehicle]:
            line.vehicle = newVehicle
            
        _m.logbook_write("Changed {0} line(s) with vehicle \
                    {1} to use {2}.".format(len(self.vm[oldVehicle]), oldVehicle.number, newVehicle.number))
    
    def _changeVehicleProperties(self, vehicle, description="", aeq=0.0, scap=0, tcap=0):
        
        if description != "" and description != None:
            vehicle.description = description
            _m.logbook_write("Description = '%s'" %description)
        
        if aeq != 0.0:
            vehicle.auto_equivalent = aeq
            _m.logbook_write("Auto equivalence = %s" %aeq)
            
        if scap != 0:
            vehicle.seated_capacity = scap
            _m.logbook_write("Seated capacity = %s" %scap)
        
        if tcap < scap:
            tcap = scap
        
        if tcap != 0:
            vehicle.total_capacity = tcap
            _m.logbook_write("Total capacity = %s" %tcap)
    
    def _changeVehicleMode(self, network, vehicle, modeChar):
        oldMode = vehicle.mode.id
        vehicle._mode = network.mode(modeChar)
        _m.logbook_write("Changed mode of vehicle {0} \
                from {1} to {2}.".format(vehicle.id, oldMode, modeChar))
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    