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
Convert VDFs

    Authors: Michael Hain

    Latest revision by: Peter Kucirek
    
    
    Converts VDF indices from DMG2001 to NCS11
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created by Michael Hain
    
    0.2.0 Updated by Peter Kucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_util = _m.Modeller().module('tmg.common.utilities')
_tmgTPB = _m.Modeller().module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ConvertVDFs(_m.Tool()):
    
    version = '0.2.0'
    tool_run_msg = ""
    
    #---Special instance types
    scenario = _m.Attribute(_m.InstanceType) #
    makeChangesPermanent = _m.Attribute(bool) #
    
    def __init__(self):
        self.networkCalculator = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Convert VDFs v%s" %self.version,
                                description="Converts link classification types (stored as VDF ids) from \
                                DMG2001 to NCS11.",
                                branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="scenario",
                               title="Select a scenario",
                               allow_none=False)
        
        pb.add_checkbox(tool_attribute_name="makeChangesPermanent",
                        title="Make changes permanent?",
                        note="If unchecked, new VDF values will be stored in link extra attribute '@vdf'.")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        if self.makeChangesPermanent == None: # Fix the checkbox problem
            self.makeChangesPermanent = False;
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="Convert Link VDFs v%s" %self.version,
                                     attributes=self._getAtts()):
            
            with self._vdfAttributeMANAGER() as self.attr:
                with _m.logbook_trace("Calculating new VDFs into attribute %s" %self.attr.id):
                    self._assignVDFToLinkSubSet(11, "vdf=11,12") # Urban freeways
                    self._assignVDFToLinkSubSet(12, "vdf=13,14") # Freeways
                    self._assignVDFToLinkSubSet(13, "vdf=21,24") # Freeway ramps
                    self._assignVDFToLinkSubSet(14, "vdf=15") # Tolled freeways
                    self._assignVDFToLinkSubSet(15, "vdf=25") # Tolled freeway ramps
                    self._assignVDFToLinkSubSet(16, "vdf=99 and not length=0 and ul2=100,9999") # Freeways HOV lanes
                    self._assignVDFToLinkSubSet(17, "vdf=99 and length=0,0.1 and ul2=100,9999") # Freeway HOV ramps
                    
                    self._assignVDFToLinkSubSet(20, "vdf=30,39 and lanes=1 and ul3=600,9999") # Two-lane rural roads
                    self._assignVDFToLinkSubSet(21, "vdf=30,39 and lanes=2,99 and ul3=600,9999") # Multi-lane rural roads 
                    self._assignVDFToLinkSubSet(22, "vdf=30,39 and ul3=0,599")
                    self._assignVDFToLinkSubSet(22, "type=217,219 or type=224 or type=325 or type=537 or type=700,999 and vdf=40,49")
                    self._assignVDFToLinkSubSet(22, "type=217,219 or type=224 or type=325 or type=537 or type=700,999 and vdf=60,69")
                    
                    self._assignVDFToLinkSubSet(30, "vdf=40,49 and %s=0" %self.attr.id) # Assign only to links which have not already been assigned.
                    self._assignVDFToLinkSubSet(30, "vdf=30,39 and type=0,112")
                    
                    self._assignVDFToLinkSubSet(40, "vdf=50,59 and ul3=700,9999")
                    self._assignVDFToLinkSubSet(41, "vdf=99 and ul2=0,99")
                    self._assignVDFToLinkSubSet(42, "vdf=50,59 and ul3=0,699")
                    
                    self._assignVDFToLinkSubSet(50, "vdf=60,69 and %s=0 and lanes=2,99 and ul3=401,9999" %self.attr.id)
                    self._assignVDFToLinkSubSet(51, "lanes=1 or ul3=0,400 and vdf=60,69 and %s=0" %self.attr.id)
                    self._assignVDFToLinkSubSet(51, "type=538 and vdf=64")
                    
                    self._assignVDFToLinkSubSet(90, "vdf=90") #Centroid connectors
                
                if self.makeChangesPermanent:
                    with _m.logbook_trace("Copying new VDF values into network"):
                        self._copyAttributeToVDF()

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _vdfAttributeMANAGER(self):
        #Code here is executed upon entry
        
        att = None
        
        att = self.scenario.extra_attribute("@vdf")
        if att == None:
            att =  self.scenario.create_extra_attribute('LINK', '@vdf', default_value=0)
            _m.logbook_write("Created temporary link '%s' attribute to store new VDFs." %att.id)
        else:
            att.initialize()
            _m.logbook_write("Initialized attribute '%s'." %att.id)
        
        try:
            yield att
        finally:
            # Code here is executed in all cases.
            if self.makeChangesPermanent:
                i = att.id
                self.scenario.delete_extra_attribute(att)
                _m.logbook_write("Deleted temporary link attribute '%s'" %i)
            else:
                _m.logbook_write("Temporary link attribute '%s' made permanent." %att.id)
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Scenario" : str(self.scenario.id),
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
        
    def _assignVDFToLinkSubSet(self, vdf, filterExpression):
        spec = {
                "result": self.attr.id,
                "expression": str(vdf),
                "selections": {"link": filterExpression},
                "type": "NETWORK_CALCULATION"
                }
        self.networkCalculator(spec, scenario=self.scenario)
    
    def _copyAttributeToVDF(self):
        spec = {
                "result": "vdf",
                "expression": self.attr.id,
                "selections": {"link": "all"},
                "type": "NETWORK_CALCULATION"
                }
        self.networkCalculator(spec, scenario=self.scenario)
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    