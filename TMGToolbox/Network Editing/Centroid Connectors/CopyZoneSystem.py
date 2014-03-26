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
Copy Zone System

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Copies a zone system (zone cetnroids + connectors) from one emmebank to another.
    
    It attempts to copy over all centroid connectors based on j-node ID, skipping
    connectors with an invalid node. All-connectors are saved to a polyline shapefile,
    for debugging post-tool. The 'MATCH' attribute of the shapefile can be used to 
    easily identify which connectors could not be copied over. The shapefile also 
    records the original length and the new length, to allow for the identification
    of nodes which have been moved (or created in a different location).
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created March 25 2013.
    
    0.1.1 Added tolerance parameter to autodetect offset nodes.
    
'''

import inro.modeller as _m
import inro.emme.database.emmebank as _mbank
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import shapelib as shp
import math
_g = _m.Modeller().module('TMG2.Common.Geometry')
_util = _m.Modeller().module('TMG2.Common.Utilities')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class CopyZoneSystem(_m.Tool()):
    
    version = '0.1.1'
    tool_run_msg = ""
    
    OtherScenarioNumber = _m.Attribute(int)
    DatabankPath = _m.Attribute(str)
    ShapefilePath = _m.Attribute(str)
    Tolerance = _m.Attribute(float)
    
    #---Special instance types
    currentScenario = _m.Attribute(_m.InstanceType) #
    publishResults = _m.Attribute(bool)
    
    #---Internal variables
    otherScenario = None
    otherDatabank = None
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Copy Zone System",
                     description="Copies a zone system (zone cetnroids + connectors) from one emmebank to another.\
                        <br><br>It attempts to copy over all centroid connectors based on j-node ID, skipping \
                        connectors with an invalid node. All-connectors are saved to a polyline shapefile, \
                        for debugging post-tool. The 'MATCH' attribute of the shapefile can be used to \
                        easily identify which connectors could not be copied over. The shapefile also \
                        records the original length and the new length, to allow for the identification \
                        of nodes which have been moved (or created in a different location). \
                        <br><br>This shapefile is created regardless of whether the results are permanent.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("TO SCENARIO")
        
        pb.add_select_scenario(tool_attribute_name="currentScenario", title="Select target scenario")
        
        pb.add_header("FROM EMMEBANK")
        
        pb.add_select_file(tool_attribute_name="DatabankPath", window_type="file",
                           title="From Emmebank", 
                           file_filter="emmebank")
        
        pb.add_text_box(tool_attribute_name="OtherScenarioNumber",
                        size=2, title="Select scenario number to copy from")
        
        pb.add_header("RESULTS AND ERRORS")
        
        pb.add_checkbox(tool_attribute_name="publishResults", title="Publish results?",
                        note="By default, this tool does NOT make any permanent changes to \
                        <br>the current scenario.")
        
        pb.add_text_box(tool_attribute_name="Tolerance",
                        size=5, title="Link length tolerance",
                        note="This tool with automatically throw out connectors whose difference in length is \
                        <br>greater than this value.")
        
        pb.add_select_file(tool_attribute_name="ShapefilePath", window_type="save_file",
                           title="Save shapefile results", 
                           note="Select a shapefile to save results into. This is <b>not</b> optional.")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        if self.publishResults == None: # Fix the checkbox problem
            self.publishResults = False
        
        with self._emmebankMANAGER():
        
            self.otherScenario = self.otherDatabank.scenario(self.OtherScenarioNumber)
            if self.otherScenario == None:
                raise Exception("Could not find scenario '%s' in other databank!" %self.OtherScenarioNumber)
            
            try:
                self._execute()
            except Exception, e:
                self.tool_run_msg = _m.PageBuilder.format_exception(
                    e, _traceback.format_exc(e))
                raise   
    
    ##########################################################################################################    
    
    
    def _execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._getAtts()):
            
            self.otherScenario = self.otherDatabank.scenario(self.OtherScenarioNumber)
            if self.otherScenario == None:
                raise Exception("Could not find scenario '%s' in other databank!" %self.OtherScenarioNumber)
            
            currentNetwork = self.currentScenario.get_network()
            otherNetwork = self.otherScenario.get_network()
                
            # Delete zones in current network
            for zone in self.currentScenario.zone_numbers:
                currentNetwork.delete_node(zone, cascade=True)
            
            with _g.Shapely2ESRI(self.ShapefilePath,'write', 'LineString') as writer:
                # Initialize the fields in the DBF
                writer.addField('Zone')
                writer.addField('Node')
                writer.addField('MATCH', fieldType='INT')
                writer.addField('Len', fieldType='float')
                writer.addField('Old_Len', fieldType='float')
                
                handledSum = 0
                totalSum = 0
                for otherZone in otherNetwork.centroids():
                    ms = self._addZone(otherZone, currentNetwork, writer)
                    if ms > 0:
                        handledSum += 1
                    totalSum += 1   
                    
            if self.publishResults:
                self.currentScenario.publish_network(currentNetwork)
            
            self.tool_run_msg = _m.PageBuilder.format_info("Tool complete. {0} out of {1} zones were connected.".format(handledSum, totalSum))

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _emmebankMANAGER(self):
        # Code here is executed upon entry {
        self.otherDatabank = _mbank.Emmebank(self.DatabankPath)
        _m.logbook_write("Opened emmebank at '%s'" %self.DatabankPath)
        # }
        try:
            yield # Yield return a temporary object
            
            # Code here is executed upon clean exit {
            
            # }
        finally:
            # Code here is executed in all cases. {
            self.otherDatabank.dispose()
            _m.logbook_write("Closed emmebank as '%s'" %self.DatabankPath)
            # }
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _getAtts(self):
        atts = {
                "Current Scenario" : str(self.currentScenario.id),
                "Other Emmebank" : self.DatabankPath,
                "Other Scenario" : "{0}: {1}".format(self.otherScenario.id, self.otherScenario.title),
                "Tolerance" : self.Tolerance, 
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _addZone(self, otherZone, currentNetwork, shapefileWriter):
        ozCoords = (otherZone.x, otherZone.y)
                                
        currentZone = currentNetwork.create_centroid(otherZone.number)
        currentZone.x = otherZone.x
        currentZone.y = otherZone.y
        
        matchSum = 0
        
        # Iterate through all outbound connectors
        for connector in otherZone.outgoing_links():            
            otherNode = connector.j_node
            onCoords = (otherNode.x, otherNode.y)
            currentNode = currentNetwork.node(otherNode.number)
                
            newLength = 0.0
            match = 0
                
            # If the connector's JNODE exists, copy the connector into the current network.
            if currentNode != None:
                newLength = math.sqrt(pow(currentZone.x - currentNode.x, 2) + pow(currentZone.y - currentNode.y, 2)) / 1000.0
                
                # Skip connectors with a link length difference greater than the specified tolerance.
                if abs(newLength - connector.length) <= self.Tolerance:
                
                    match = 1
                        
                    toLink = currentNetwork.create_link(currentZone.id, currentNode.id, connector.modes)
                    toLink.type = connector.type
                    toLink.num_lanes = connector.num_lanes
                    toLink.volume_delay_func = connector.volume_delay_func
                    toLink.data2 = connector.data2
                    toLink.data3 = connector.data3
                    toLink.length = newLength
                        
                    froLink = currentNetwork.create_link(currentNode.id, currentZone.id, connector.modes)
                    froLink.type = connector.type
                    froLink.num_lanes = connector.num_lanes
                    froLink.volume_delay_func = connector.volume_delay_func
                    froLink.data2 = connector.data2
                    froLink.data3 = connector.data3
                    froLink.length = newLength
                
            # Add the connector to the shapefile, regardless of whether it's been created or not.
            line = _g.LineString([ozCoords, onCoords])
            line.setAttributes({'Zone' : otherZone.id,
                                 'Node' : otherNode.id,
                                 'MATCH' : match,
                                 'Len' : round(connector.length, 4),
                                 'Old_Len' : round(newLength, 4)})
            
            shapefileWriter.writeNext(line)
            
            matchSum += match
                
        return matchSum
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    