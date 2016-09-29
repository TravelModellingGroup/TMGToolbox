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

'''
Analysis Tool for flagging premium bus lines for analysis

Currently supports:
    - GO Buses
    - TTC Premium Buses
    - VIVA Buses

Space has been made for ZUM, but since this service is not yet defined,
    it could not be included

    Author: Peter Kucirek

'''
import inro.modeller as _m
import traceback as _traceback


class FlagPremiumBusLines(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    
    #---Variable definitions
    ScenarioNumber = _m.Attribute(int)
    FlagGO = _m.Attribute(bool)
    FlagPremTTC = _m.Attribute(bool)
    FlagVIVA = _m.Attribute(bool)
    FlagZum = _m.Attribute(bool)
    
    #---Special instance types, used only from Modeller
    scenario = _m.Attribute(_m.InstanceType)
    
    def __init__(self):
        self.counter = 0
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Flag Premium Bus Lines",
                     description="Flags certain premium lines by assigning '1' to line extra attribute '@lflag'. Initializes \
                         @lflag to 0 first.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_checkbox(tool_attribute_name='FlagGO',
                        title="Flag GO Bus lines?")
        
        pb.add_checkbox(tool_attribute_name='FlagPremTTC',
                        title="Flag Premium TTC bus lines?")
        
        pb.add_checkbox(tool_attribute_name='FlagVIVA',
                        title="Flag VIVA bus lines?",
                        note="Assumes NCS11 line ids.")
        
        pb.add_checkbox(tool_attribute_name='FlagZum',
                        title="Flag ZUM bus lines?",
                        note="CURRENTLY UNSUPPORTED.")
        
        return pb.render()
    
    def run(self):
        '''Run is called from Modeller.'''
        self.tool_run_msg = ""
        self.isRunningFromXTMF = False
        
        # Run the tool
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool completed. %s lines were flagged." %self.counter)
    
    def __call__(self, ScenarioNumber, FlagGO, FlagPremTTC, FlagVIVA, \
                 FlagZum):
        
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if self.scenario == None:
            raise Exception("Could not find scenario %s!" %ScenarioNumber)
        
        self.FlagGO = FlagGO
        self.FlagPremTTC = FlagPremTTC
        self.FlagVIVA = FlagVIVA
        self.FlagZum = FlagZum
        
        self.isRunningFromXTMF = True
        
        #Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
        
    def _execute(self):
        
        with _m.logbook_trace(name="Flag premium buses v%s" %self.version,
                                     attributes={
                                                 "Scenario" : str(self.scenario.id),
                                                 "Flag GO Buses": self.FlagGO,
                                                 "Flag TTC Premium Buses": self.FlagPremTTC,
                                                 "Flag VIVA Buses": self.FlagVIVA,
                                                 "Flag ZUM": self.FlagZum,
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            #---0. Set up all Emme tools and data structures
            try:
                self.netWorkCalculationTool = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
                _m.logbook_write(name="Emme 3.4.2 Tool Names used")
            except Exception, e:
                self.netWorkCalculationTool = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
                _m.logbook_write(name="Emme 4.0.3 Tool Names used")
            
            #---Initialize the flag attribute
            self._initFlagAttribute()
            self.counter = 0
            
            #---Get network
            network = self.scenario.get_network()
            
            #---Set up the list of functions
            functions = []
            if self.FlagGO:
                functions.append(self._flagGoBuses)
            if self.FlagPremTTC:
                functions.append(self._flagTTCPremiumBuses)
            if self.FlagVIVA:
                functions.append(self._flagVIVABuses)
            if self.FlagZum:
                functions.append(self._flagZumBuses)
            
            #---Execute
            for line in network.transit_lines():
                for f in functions:
                    f(line)
            
            #---Publish
            self.scenario.publish_network(network)
            
    def _initFlagAttribute(self):
        if self.scenario.extra_attribute('@lflag') == None:
            #@lflag hasn't been defined
            self.scenario.create_extra_attribute('TRANSIT_LINE', '@lflag', default_value=0)
        else:
            self.scenario.extra_attribute('@lflag').initialize(value=0)
    
    def _flagGoBuses(self, line):
        if line.mode.id == 'g':
            line.__setattr__('@lflag', 1)
            self.counter += 1
    
    def _flagTTCPremiumBuses(self, line):
        if line.mode.id == 'p':
            line.__setattr__('@lflag', 1)
            self.counter += 1
    
    def _flagVIVABuses(self, line):
        if line.id[0] == 'Y' and line.id[1] == 'V':
            line.__setattr__('@lflag', 1)
            self.counter += 1
    
    def _flagZumBuses(self, line):
        raise Exception("Flagging of ZUM lines is currently unsupported.")
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        
        
    