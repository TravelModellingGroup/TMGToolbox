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
Flag Link Directions

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-12 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import numpy
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
NullPointerException = _util.NullPointerException

##########################################################################################################

class FlagLinkDirection(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    LinkDirectionAttributeId = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Flag Link Direction v%s" %self.version,
                     description="Hard-coded to GTHA geographic type groupings, this tool \
                         assigns direction integers to each link (stored in an extra \
                         attribute). 1 = North, 2 = East, 3 = South, 4 = West",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        keyval = {}
        for att in _MODELLER.scenario.extra_attributes():
            if att.type == 'LINK': keyval[att.id] = "%s - %s" %(att.id, att.description)
        pb.add_select(tool_attribute_name='LinkDirectionAttributeId',
                      keyvalues= keyval,
                      title= "Link direction attribute",
                      note= "The attribute to save direction into")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#LinkDirectionAttributeId")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#LinkDirectionAttributeId");
            $("#LinkDirectionAttributeId").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
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
            
            network = self.Scenario.get_network()
            print "Loaded network"
            
            def calcBearing(link, delta=0): #In radians
                rad = numpy.arctan2(link.j_node.x - link.i_node.x, link.j_node.y - link.i_node.y) + delta
                if rad < 0:
                    return rad + numpy.pi * 2
                return rad
            
            def getDelta(link):
                t = link.type / 100
                if t == 4 or t == 5: return 45
                if t == 6 or t == 7: return -15
                return 15
            
            self.TRACKER.startProcess(network.element_totals['links'])
            for link in network.links():
                delta = getDelta(link)
                delta = numpy.deg2rad(delta)
                
                bearing = numpy.rad2deg(calcBearing(link, delta)) #In degrees
                
                dir = 0
                if bearing <= 45: dir = 1 #North
                elif bearing <= 135: dir = 2 #East
                elif bearing <=225: dir = 3 #South
                elif bearing <= 315: dir = 4 #West
                else: dir = 1 #North again
                
                link[self.LinkDirectionAttributeId] = dir
                
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            print "Done processing links"
            
            self.Scenario.publish_network(network)
            

    ########################################################################################################## 
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Direction Attribute": self.LinkDirectionAttributeId,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    @_m.method(return_type=unicode)
    def _GetSelectAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            label = "{id} - {name}".format(id=att.name, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        