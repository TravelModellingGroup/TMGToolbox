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
Hypernetwork Volume Importer
    Authors: David King
    Latest revision by: David King
    
Allows for the visualization of transit volumes on the hypernetwork by assigning volume    
to a link attribute.
    
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2015-02-09 by David King
    
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from html import HTML
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')


#---MAIN MODELLER TOOL--------------------------------------------------------------------------------
class Volume_Extractor(_m.Tool()):
    
    BaseScenario = _m.Attribute(_m.InstanceType)
    SegmentAttribute = _m.Attribute(str)
    LinkAttribute = _m.Attribute(str)
    tool_run_msg = ""
    number_of_tasks = 4
    
    def __init__(self):
        self.BaseScenario = _MODELLER.scenario #Default is primary scenario
        self.SegmentAttribute = "@cvolt"
        self.LinkAttribute = "@volut"
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)
    
    def page(self):
         
         pb = _tmgTPB.TmgToolPageBuilder(self, title="Transit Volume Extractor from a Hypernetwork",
                     description="Extracts the ca_voltr values from the Hypernetwork and assigns it to a Link Extra Attribute,\
                     This allows for the visualization of Transit Volumes in aggregate.\
                     <br><br><em> Requires storage space for two extra attributes. </em>",
                     branding_text = "- TMG Toolbox")
        
         if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
       
         pb.add_header("SCENARIO")
        
         pb.add_select_scenario(tool_attribute_name='BaseScenario',
                               title='Scenario:',
                               allow_none=False)
        
              
         pb.add_header("DEFINING ATTRIBUTES")
                    
         keyval2 = []
         keyval3 = []
         keyval4 = [(-1, "None - Do not save segment base info")]
         for exatt in self.BaseScenario.extra_attributes():
            if exatt.type == 'TRANSIT_SEGMENT':
                val = "%s - %s" %(exatt.name, exatt.description)
                keyval2.append((exatt.name, val))
            elif exatt.type == 'LINK':
                val = "%s - %s" %(exatt.name, exatt.description)
                keyval3.append((exatt.name, val))
                keyval4.append((exatt.name, val))
        
         pb.add_select(tool_attribute_name= 'SegmentAttribute',
                      keyvalues= keyval2,
                      title= "Segment Attribute Selector",
                      note= "Select a TRANSIT SEGMENT extra attribute in which to save \
                      Transit Volumes")
        
         pb.add_select(tool_attribute_name= 'LinkAttribute',
                      keyvalues= keyval3,
                      title="Link Attribute Selector",
                      note= "Select a  LINK extra attribute in which \
                      to the Transit Segment Volumes.")     
          
         return pb.render()

    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
                        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def _Execute(self):
        
        networkCalculationTool = _MODELLER.tool("inro.emme.network_calculation.network_calculator") 
        
        if self.BaseScenario.extra_attribute('@cvolt') is not None:
            _m.logbook_write("Deleting Previous Extra Attributes.")
            self.BaseScenario.delete_extra_attribute('@cvolt')
        _m.logbook_write("Creating Attribute for ca_Voltr_l Value Transfer")
        self.BaseScenario.create_extra_attribute('TRANSIT_SEGMENT', '@cvolt', default_value=0)
        
        if self.BaseScenario.extra_attribute('@volut') is not None:
            _m.logbook_write("Deleting Previous Extra Attributes.")
            self.BaseScenario.delete_extra_attribute('@volut')
        _m.logbook_write("Creating Attribute for ca_Voltr_l Value Transfer")
        self.BaseScenario.create_extra_attribute('LINK', '@volut', default_value=0)
                    
        
        #Transfer ca_Voltr_l into a transit segment attribute.
        spec_transfer_1 = {
            "result": "@cvolt",
            "expression": "voltr",
            "aggregation": None,
            "selections": {
                "link": "all",
                "transit_line": "all"
            },
            "type": "NETWORK_CALCULATION"
        }
        
        with _m.logbook_trace("Transferring Voltr into an Extra Attribute"): #Do Once
            networkCalculationTool(spec_transfer_1, scenario=self.BaseScenario)
            
            
        #Transfer the transit segment attribute into a link attribute
        spec_transfer_2 = {
            "result": "@volut",
            "expression": "@cvolt",
            "aggregation": "+",
            "selections": {
                "link": "all",
                "transit_line": "all"
            },
            "type": "NETWORK_CALCULATION"
        }
        
        with _m.logbook_trace("Transferring  into an  Link Attribute"): #Do Once
            networkCalculationTool(spec_transfer_2, scenario=self.BaseScenario)
            
            
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg