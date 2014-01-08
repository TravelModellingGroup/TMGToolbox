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
GEO RENUMBER NODES

    Authors: Peter Kucirek

    Latest revision by: @pkucirek
    
    
    Re-numbers nodes based on a geographic mesh imported from a shapefile. Since this is
    for NCS11, region/county names and their associated node ranges are hard-coded.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')
_geo = _MODELLER.module('TMG2.Common.Geometry')
Shapely2ESRI = _geo.Shapely2ESRI
PolygonMeshSearchGrid = _geo.PolygonMeshSearchGrid

##########################################################################################################

class GeoRenumberNodes(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    CountyBoundaryFile = _m.Attribute(str)
    ReportFlag = _m.Attribute(bool)
    
    nodeRegions = {'City of Toronto': range(10000, 20000),
                    'Durham Region': range(20000, 30000),
                    'York Region': range(30000, 40000),
                    'Peel Region': range(40000, 50000),
                    'Halton Region': range(50000, 60000),
                    'City of Hamilton': range(60000, 70000),
                    'Niagara Region': range(70000, 80000),
                    'Waterloo Region': range(82001, 85000),
                    'Wellington County': range(85001, 87000),
                    'Dufferin County': range(87001, 88000),
                    'Simcoe County': range(88001, 90000),
                    'Kawartha Lakes Division': range(90001, 91000),
                    'Peterborough County': range(91001, 92000),
                    'Brant County': range(81001, 82000)}
    
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Geometric Renumber Nodes v%s" %self.version,
                     description="Re-numbers nodes based on a geographic mesh imported from a shapefile. \
                         A compatible shapefile should be obtained from TMG in order for this to work.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='CountyBoundaryFile',
                           window_type='file',
                           file_filter="*.shp",
                           title="Boundary File",
                           note="Select a polygon file containing county boundaries.")
        
        pb.add_checkbox(tool_attribute_name='ReportFlag',
                        label="Report conversions to the logbook?",
                        note="Write to the logbook which nodes IDs were changed, and their new values.")
        
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
        
        
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with _m.logbook_trace("Loading shapefile"):
                boundaries = self._LoadCheckGeometry()
            
            network = self.Scenario.get_network()
            self.TRACKER.completeTask()
            
            with _m.logbook_trace("Classifying nodes"):
                self._ClassifyNodes(network, boundaries)
                
            with _m.logbook_trace("Renumbering nodes"):
                fixedNodeIDs = self._OffsetNodeNumbers(network)
                _m.logbook_write("Offset node numbers")
                
                mappings = self._RenumberNodes(network, fixedNodeIDs)
                _m.logbook_write("Re-numbered nodes")
            
            if self.ReportFlag:
                _m.logbook_write("Conversion Report", value=self._WriteMappingsReport(mappings))
            
            self.Scenario.publish_network(network, True)
            self.TRACKER.completeTask()
            
            self.tool_run_msg = _m.PageBuilder.format_info("Done. %s nodes were renumbered." %len(mappings))

    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadCheckGeometry(self):
        with Shapely2ESRI(self.CountyBoundaryFile) as reader:
            if not 'County' in reader.getFieldNames():
                raise IOError("Shapefile does not define a 'County' field!")
            
            boundaries = []
            countyNames = set()
            
            self.TRACKER.startProcess(len(reader))
            for shape in reader.readThrough():
                boundaries.append(shape)
                countyNames.add(shape['County'])
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            _m.logbook_write("%s boundary shapes loaded." %len(reader))
            
            defaultSet = set([key for key in self.nodeRegions.iterkeys()])
            diff = countyNames.symmetric_difference(defaultSet)
            
            if diff:
                raise IOError("County/node range mismatch; the following counties are not defined \
                in both the tool and the shapefile: %s" %diff)
            
        return boundaries
    
    def _ClassifyNodes(self, network, boundaries):
        network.create_attribute('NODE', 'numberCategory', None)
        searchGrid = PolygonMeshSearchGrid(boundaries, 10)
                
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        errorCount = 0
        for node in network.regular_nodes():
            
            if node.number >= 96000 and node.number < 98000:
                node.numberCategory = 'Rails'
                self.TRACKER.completeSubtask()
                continue
            elif node.number >= 900000 and node.number < 1000000:
                node.numberCategory = 'HOV'
                self.TRACKER.completeSubtask()
                continue
                        
            try:
                containers = searchGrid.findContainingGeometries(node)
                if len(containers) > 1:
                    raise Exception("Shapefile contains overlapping features")
                elif len(containers) == 0:
                    raise IOError("Shapefile does not cover node")
                
                shape = containers[0]
                node.numberCategory = shape['County']
                self.TRACKER.completeSubtask()
            except Exception, e:
                errorCount += 1
                if errorCount < 20:
                    _m.logbook_write("Unable to determine a category for node %s: %s" %(node, e))
                elif errorCount == 20:
                    _m.logbook_write("Unable to determine a category for node %s: %s" %(node, e))
                    _m.logbook_write("Future logging of this warning supressed.")
                self.TRACKER.completeSubtask()
                continue
        self.TRACKER.completeTask()
        _m.logbook_write("Done. %s errors encountered, corresponding nodes were not classified" %errorCount)
    
    def _OffsetNodeNumbers(self, network):
        fixedNodeIDs = set()
        
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        for node in network.regular_nodes():
            if node.numberCategory == 'Rails' or node.numberCategory == None or node.numberCategory == 'HOV':
                fixedNodeIDs.add(node.number)
            else:
                node.number += 100000 #100k
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        
        return fixedNodeIDs
    
    def _RenumberNodes(self, network, fixedNodeIDs):
        iterartors = dict([(key, val.__iter__()) for (key, val) in self.nodeRegions.iteritems()])
        mappings = {}
        
        self.TRACKER.startProcess(network.element_totals['regular_nodes'])
        for node in network.regular_nodes():
            if node.numberCategory == 'Rails' or node.numberCategory == None or node.numberCategory == 'HOV':
                pass
            else:
                iter = iterartors[node.numberCategory]
                
                newNumber = iter.next()
                while(newNumber in fixedNodeIDs):
                    newNumber = iter.next()
                mappings[node.number - 100000] = newNumber
                node.number = newNumber
                
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
        return mappings
    
    def _WriteMappingsReport(self, mappings):
        pb = _m.PageBuilder(title="Node Renumbering Report")
        
        for tup in mappings.iteritems():
            pb.add_html("<p>%s: %s</p>" %tup)
        
        return pb.render()
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    