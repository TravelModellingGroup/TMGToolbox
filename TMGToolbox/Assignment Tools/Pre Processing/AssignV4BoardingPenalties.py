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
Assign V4 Boarding Penalties

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Assigns line-specific boarding penalties (stored in UT3) based on pre-specified (e.g.
    hard-coded) groupings, for transit assignment estimation.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-14 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class AssignV4BoardingPenalties(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 15 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    SubwayBoardingPenalty = _m.Attribute(float)
    GoTrainBoardingPenalty = _m.Attribute(float)
    GoBusBoardingPenalty = _m.Attribute(float)
    StreetcarXROWBoardingPenalty = _m.Attribute(float)
    StreetcarBoardingPenalty = _m.Attribute(float)
    TTCBusBoardingPenalty = _m.Attribute(float)
    YRTBoardingPenalty = _m.Attribute(float)
    VIVABoardingPenalty = _m.Attribute(float)
    BramptonBoardingPenalty = _m.Attribute(float)
    ZUMBoardingPenalty = _m.Attribute(float)
    MiWayBoardingPenalty = _m.Attribute(float)
    DurhamBoardingPenalty = _m.Attribute(float)
    HaltonBoardingPenalty = _m.Attribute(float)
    HSRBoardingPenalty = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.SubwayBoardingPenalty = 1.0
        self.GoTrainBoardingPenalty = 1.0
        self.GoBusBoardingPenalty = 1.0
        self.StreetcarBoardingPenalty = 1.0
        self.StreetcarXROWBoardingPenalty = 1.0
        self.TTCBusBoardingPenalty = 1.0
        self.YRTBoardingPenalty = 1.0
        self.VIVABoardingPenalty = 1.0
        self.BramptonBoardingPenalty = 1.0
        self.ZUMBoardingPenalty = 1.0
        self.MiWayBoardingPenalty = 1.0
        self.DurhamBoardingPenalty = 1.0
        self.HaltonBoardingPenalty = 1.0
        self.HSRBoardingPenalty = 1.0
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Assign V4 Boarding Penalties v%s" %self.version,
                     description="Assigns line-specific boarding penalties (stored in UT3) \
                         based on hard-coded line groupings.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name='GoTrainBoardingPenalty',
                        size=10, title="GO Train Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='GoBusBoardingPenalty',
                        size=10, title="GO Bus Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='SubwayBoardingPenalty',
                        size=10, title="Subway Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='StreetcarXROWBoardingPenalty',
                        size=10, title="Streetcar (Excl. ROW) Boarding Penalty",
                        note="Currently hard-coded to T509, T510, and T512")
        
        pb.add_text_box(tool_attribute_name='TTCBusBoardingPenalty',
                        size=10, title="TTC Bus Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='StreetcarBoardingPenalty',
                        size=10, title="Streetcar Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='VIVABoardingPenalty',
                        size=10, title="YRT VIVA Boarding Penalty",
                        note="Currently hard-coded to lines beginning with 'YV'")
        
        pb.add_text_box(tool_attribute_name='YRTBoardingPenalty',
                        size=10, title="YRT (non-VIVA) Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='ZUMBoardingPenalty',
                        size=10, title="Brampton ZUM Boarding Penalty",
                        note="Currently hard-coded to B501 and B502")
        
        pb.add_text_box(tool_attribute_name='BramptonBoardingPenalty',
                        size=10, title="Brampton Transit (non-ZUM) Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='MiWayBoardingPenalty',
                        size=10, title="MiWay (Mississauga) Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='DurhamBoardingPenalty',
                        size=10, title="Durham Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='HaltonBoardingPenalty',
                        size=10, title="Halton Boarding Penalty")
        
        pb.add_text_box(tool_attribute_name='HSRBoardingPenalty',
                        size=10, title="HSR (Hamilton) Boarding Penalty")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            if self.SubwayBoardingPenalty == None: raise NullPointerException("Subway boarding penalty not specified")
            if self.GoTrainBoardingPenalty == None: raise NullPointerException("GO Train boarding penalty not specified")
            if self.GoBusBoardingPenalty == None: raise NullPointerException("GO Bus boarding penalty not specified")
            if self.StreetcarXROWBoardingPenalty == None: raise NullPointerException("Streetcar XROW boarding penalty not specified")
            if self.StreetcarBoardingPenalty == None: raise NullPointerException("Streetcar boarding penalty not specified")
            if self.TTCBusBoardingPenalty == None: raise NullPointerException("TTC Bus boarding penalty not specified")
            if self.YRTBoardingPenalty == None: raise NullPointerException("YRT boarding penalty not specified")
            if self.VIVABoardingPenalty == None: raise NullPointerException("VIVA boarding penalty not specified")
            if self.BramptonBoardingPenalty == None: raise NullPointerException("Brampton boarding penalty not specified")
            if self.ZUMBoardingPenalty == None: raise NullPointerException("ZUM boarding penalty not specified")
            if self.MiWayBoardingPenalty == None: raise NullPointerException("MiWay boarding penalty not specified")
            if self.DurhamBoardingPenalty == None: raise NullPointerException("Durham boarding penalty not specified")
            if self.HaltonBoardingPenalty == None: raise NullPointerException("Halton boarding penalty not specified")
            if self.HSRBoardingPenalty == None: raise NullPointerException("HSR boarding penalty not specified")          
            
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumber,
                 SubwayBoardingPenalty,
                 GoTrainBoardingPenalty,
                 GoBusBoardingPenalty,
                 StreetcarXROWBoardingPenalty,
                 StreetcarBoardingPenalty,
                 TTCBusBoardingPenalty,
                 YRTBoardingPenalty,
                 VIVABoardingPenalty,
                 BramptonBoardingPenalty,
                 ZUMBoardingPenalty,
                 MiWayBoardingPenalty,
                 DurhamBoardingPenalty,
                 HaltonBoardingPenalty,
                 HSRBoardingPenalty):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.SubwayBoardingPenalty = SubwayBoardingPenalty
        self.GoTrainBoardingPenalty = GoTrainBoardingPenalty
        self.GoBusBoardingPenalty = GoBusBoardingPenalty
        self.StreetcarXROWBoardingPenalty = StreetcarXROWBoardingPenalty
        self.StreetcarBoardingPenalty = StreetcarBoardingPenalty
        self.TTCBusBoardingPenalty = TTCBusBoardingPenalty
        self.YRTBoardingPenalty = YRTBoardingPenalty
        self.VIVABoardingPenalty = VIVABoardingPenalty
        self.BramptonBoardingPenalty = BramptonBoardingPenalty
        self.ZUMBoardingPenalty = ZUMBoardingPenalty
        self.MiWayBoardingPenalty = MiWayBoardingPenalty
        self.DurhamBoardingPenalty = DurhamBoardingPenalty
        self.HaltonBoardingPenalty = HaltonBoardingPenalty
        self.HSRBoardingPenalty = HSRBoardingPenalty
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            tool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
            
            with _m.logbook_trace("Resetting UT3 to 0"):
                tool(specification=self._GetClearAllSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying GO Train BP"):
                tool(specification=self._GetGoTrainSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying GO Bus BP"):
                tool(specification=self._GetGoBusSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying Subway BP"):
                tool(specification=self._GetSubwaySpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying Streetcar BP"):
                tool(specification=self._GetAllStreetcarSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying Streetcar XROW BP"):
                tool(specification=self._GetStreetcarXROWSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying TTC Bus BP"):
                tool(specification=self._GetTTCBusSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
                
            with _m.logbook_trace("Applying YRT BP"):
                tool(specification=self._GetAllYRTSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying VIVA BP"):
                tool(specification=self._GetVIVASpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying Brampton Transit BP"):
                tool(specification=self._GetAllBramptonSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying ZUM BP"):
                tool(specification=self._GetZUMSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
                
            with _m.logbook_trace("Applying MiWay BP"):
                tool(specification=self._GetMiWaySpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
                
            with _m.logbook_trace("Applying Durham BP"):
                tool(specification=self._GetDurhamSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
            
            with _m.logbook_trace("Applying Halton BP"):
                tool(specification=self._GetHaltonSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
                
            with _m.logbook_trace("Applying Hamilton BP"):
                tool(specification=self._GetHamiltonSpec(), scenario=self.Scenario)
                self.TRACKER.completeTask()
                
            _MODELLER.desktop.refresh_needed(True)
            
    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _MANAGERtemplate(self):
        # Code here is executed upon entry {
        
        # }
        try:
            yield # Yield return a temporary object
            
            # Code here is executed upon clean exit {
            
            # }
        finally:
            # Code here is executed in all cases. {
            pass
            # }
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _GetClearAllSpec(self):
        return {
                    "result": "ut3",
                    "expression": "0",
                    "aggregation": None,
                    "selections": {
                        "transit_line": "all"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetSubwaySpec(self):
        return {
                    "result": "ut3",
                    "expression": self.SubwayBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "mode=m"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetGoTrainSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.GoTrainBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "mode=r"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetGoBusSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.GoBusBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "mode=g"
                    },
                    "type": "NETWORK_CALCULATION"
                }
        
    def _GetAllStreetcarSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.StreetcarBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "mode=s"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetStreetcarXROWSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.StreetcarXROWBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=T509__ or line=T510__ or line=T512__"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetTTCBusSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.TTCBusBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=T_____ and mode=bp"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetAllYRTSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.YRTBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=Y_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetVIVASpec(self):
        return {
                    "result": "ut3",
                    "expression": self.VIVABoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=YV____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetAllBramptonSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.BramptonBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=B_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetZUMSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.ZUMBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=B501__ or line=B502__"
                    },
                    "type": "NETWORK_CALCULATION"
                }
        
    def _GetMiWaySpec(self):
        return {
                    "result": "ut3",
                    "expression": self.MiWayBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=M_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetDurhamSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.DurhamBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=D_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetHaltonSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.HaltonBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=H_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    def _GetHamiltonSpec(self):
        return {
                    "result": "ut3",
                    "expression": self.HSRBoardingPenalty.__str__(),
                    "aggregation": None,
                    "selections": {
                        "transit_line": "line=W_____"
                    },
                    "type": "NETWORK_CALCULATION"
                }
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        