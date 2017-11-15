'''
    Copyright 2016 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Attach Centroids To Nodes

    Authors: JamesVaughan

    Latest revision by: JamesVaughan
    
    
    This tool is designed to allow a model system to automatically
    create new centroids on nodes existing in the network.  If a centroid already
    exists it will be moved.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2016-03-22 by JamesVaughan
    
    
'''
import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.

class AttachCentriodsToNodes(_m.Tool()):
    version = '0.0.1'
    ScenarioNumber = _m.Attribute(int)
    Centroids = _m.Attribute(str)
    Nodes = _m.Attribute(str)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Attach Centroids To Nodes",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")
        
        return pb.render()
    
    def run(self):
        pass

    def __call__(self, ScenarioNumber, Nodes, Centroids):  
        try:
            self._execute(ScenarioNumber, Nodes, Centroids)
        except Exception, e:
            raise Exception(_traceback.format_exc(e))

    def _execute(self, ScenarioNumber, Nodes, Centroids):
        nodesToAttachTo = Nodes.split(";")
        centroidNumbers = Centroids.split(";")
        project = _MODELLER.emmebank
        scenario = project.scenario(str(ScenarioNumber))
        network = scenario.get_network()
        #TODO: Un-hardcode this to read in the modes from XTMF
        linkType = 1
        linkSpeed = 40
        lanes = 2.0

        centroidSet = set([network.mode('c'), 
                                 network.mode('h'), 
                                 network.mode('i'),
                                 network.mode('f'),
                                 network.mode('e'),
                                 network.mode('d'),
                                 network.mode('v')])
        for i in range(len(nodesToAttachTo)):
            nodeToAttachTo = self._get_node(network, nodesToAttachTo[i])
            if nodeToAttachTo is None:
                raise Exception("Unable to find a node with the ID " + nodesToAttachTo[i])
            #check to see if the centroid already exists
            centroidNode = self._get_node(network, centroidNumbers[i])
            if centroidNode is not None:
                network.delete_node(centroidNode.id, True)
            centroidNode = network.create_centroid(centroidNumbers[i])
            centroidNode.x = nodeToAttachTo.x
            centroidNode.y = nodeToAttachTo.y
            linkTo = network.create_link(centroidNumbers[i], nodesToAttachTo[i], centroidSet)
            linkFrom = network.create_link(nodesToAttachTo[i], centroidNumbers[i], centroidSet)
            linkTo.length = 0.0
            linkFrom.length = 0.0
            linkTo.type = linkType
            linkTo.num_lanes = lanes
            linkTo.data2 = linkSpeed
            linkTo.data3 = 9999
            linkFrom.type = linkType
            linkFrom.num_lanes = lanes
            linkFrom.data2 = linkSpeed
            linkFrom.data3 = 9999
        scenario.publish_network(network)

    def _get_node(self, network, nodeString):
        return network.node(nodeString)
