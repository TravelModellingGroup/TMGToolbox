"""
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
"""

from contextlib import contextmanager
from multiprocessing import cpu_count
import multiprocessing
import inro.modeller as _m

_trace = _m.logbook_trace
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_geolib = _MODELLER.module('tmg.common.geometry')
Shapely2ESRI = _geolib.Shapely2ESRI
networkCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
subareaAnalysisTool = _MODELLER.tool('inro.emme.subarea.subarea')
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

class ExportSubareaTool(_m.Tool()):
    version = '1.1.1'
    tool_run_msg = ""
    number_of_tasks = 4 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    #---Variable definitions
    xtmf_ScenarioNumber = _m.Attribute(int)
    Scenario = _m.Attribute(_m.InstanceType)
    
    xtmf_PeakHourFactor = _m.Attribute(str) 

    xtmf_ModeList = _m.Attribute(str) #Must be passed as a string, with modes comma separated (e.g. 'a,b,c') cov => ['a','b','c']
    xtmf_NameString = _m.Attribute(str)
    xtmf_AutoDemand = _m.Attribute(str)
    xtmf_LinkCosts = _m.Attribute(str)
    xtmf_LinkTollAttributeIds = _m.Attribute(str)
    xtmf_TollWeights = _m.Attribute(str)
    xtmf_ResultAttributes = _m.Attribute(str)

    xtmf_MaxIterations = _m.Attribute(str)
    xtmf_rGap = _m.Attribute(str)
    xtmf_brGap = _m.Attribute(str)
    xtmf_normGap = _m.Attribute(str)
    xtmf_PerformanceFlag = _m.Attribute(str)

    xtmf_ExtractTransitFlag = _m.Attribute(str)
    xtmf_SubareaNodeAttribute = _m.Attribute(str)
    xtmf_SubareaFolderPath = _m.Attribute(str)
    xtmf_NodeNumberStarting = _m.Attribute(str)
    xtmf_ShapefileLocation = _m.Attribute(str)
    xtmf_GateLabel = _m.Attribute(str)

    NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        self._tracker = _util.ProgressTracker(self.number_of_tasks)
        
        self.Scenario = _MODELLER.scenario

        self.NumberOfProcessors = multiprocessing.cpu_count()
             
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(
            self, title="Export Subarea Tool v%s" % self.version,
            description="Not Callable from Modeller. Please use XTMF. EXPERIMENTAL",
            branding_text="- XTMF")
        return pb.render()

    def __call__(self, xtmf_ScenarioNumber, xtmf_PeakHourFactor, xtmf_ModeList, xtmf_NameString, xtmf_AutoDemand, xtmf_LinkCosts, xtmf_LinkTollAttributeIds, 
                 xtmf_TollWeights, xtmf_ResultAttributes, xtmf_MaxIterations, xtmf_rGap, xtmf_brGap, xtmf_normGap, xtmf_PerformanceFlag,
                 xtmf_ExtractTransitFlag, xtmf_SubareaNodeAttribute, xtmf_SubareaFolderPath, xtmf_NodeNumberStarting, xtmf_ShapefileLocation, xtmf_GateLabel):

        self.Scenario = _m.Modeller().emmebank.scenario(int(xtmf_ScenarioNumber))
        self.PeakHourFactor = float(xtmf_PeakHourFactor)

        self.ModeList = [str(x).strip(" ") for x in xtmf_ModeList.strip(" ").split(",")]
        self.DemandMatrixIdList = [str(x).strip(" ") for x in xtmf_AutoDemand.strip(" ").split(",")]
        self.LinkCosts = [float(x) for x in xtmf_LinkCosts.strip(" ").split(",")]
        self.TollWeights = [float(x) for x in xtmf_TollWeights.strip(" ").split(",")]
        self.LinkTollAttributeIds = [str(x) for x in xtmf_LinkTollAttributeIds.strip(" ").split(",")]
        self.ClassNames = [str(x) for x in xtmf_NameString.strip(" ").split(",")]
        self.ClassResultAttributes = [str(x) for x in xtmf_ResultAttributes.strip(" ").split(",")]

        self.MaxIterations = int(xtmf_MaxIterations)
        self.RelGap = float(xtmf_rGap)
        self.BestRelGap = float(xtmf_brGap)
        self.NormGap = float(xtmf_normGap)
        if str(xtmf_PerformanceFlag).lower() == 'true':
            self.PerformanceFlag = True
        else:
            self.PerformanceFlag = False
        if str(xtmf_ExtractTransitFlag).lower() == "true":
            if self.Scenario.has_transit_results is False:
                raise Exception ("A transit assignment must be run (and strategies saved) beforehand if you wish to extract out transit in this tool")
            self.ExtractTransit = True
        else:
            self.ExtractTransit = False
        if str(xtmf_SubareaNodeAttribute).lower() == "none" :
            self.SubareaNodeAttribute = None
        else:
            self.SubareaNodeAttribute = str(xtmf_SubareaNodeAttribute)
        self.OutputFolder = str(xtmf_SubareaFolderPath)
        self.StartingNodeNumber = int(xtmf_NodeNumberStarting)
        if str(xtmf_ShapefileLocation).lower() == "none":
            self.ShapefileLocation = None
        else:
            self.ShapefileLocation = str(xtmf_ShapefileLocation)
        if str(xtmf_GateLabel).lower() == "none":
            self.GateLabel = None
        else:
            self.GateLabel = str(xtmf_GateLabel)
        if self.ShapefileLocation is None and self.SubareaNodeAttribute is None:
            raise Exception("You must specify an existing subarea node attribute which defines the subarea or a shapefile that defines the subarea")
        try:
            print("Exporting Subarea")
            self._execute()
            print("Subarea Exported")
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(self):
        with _m.logbook_trace(name="Exporting Subarea (%s v%s)" %(self.__class__.__name__, self.version),
                                     attributes=self._getAtts()):
            
            self._tracker.reset()
            self._checkDemandMatrices()
            
            with self._costAttributeMANAGER() as costAttribute,self._transitTrafficAttributeMANAGER() as bgTransitAttribute,self._subareaNodeAttributeManager() as subareaNodeAttribute:

                self._initResultAttributes()
                #ToDo: NOTE THIS PIECE IS BROKEN WE WILL NEED TO SEE HOW TO UNPACK A LIST IN ANOTHER PR
                for Demand in self.DemandMatrixIdList:
                    with _util.tempMatrixMANAGER(description="Peak hour matrix") as peakHourMatrix:

                        with _m.logbook_trace("Calculating transit background traffic"): #Do Once
                            networkCalcTool(self._getTransitBGSpec(), scenario=self.Scenario)
                            self._tracker.completeSubtask()
                            
                        with _m.logbook_trace("Calculating link costs"): #Do for each class
                            for i in range(len(self.ModeList)):
                                networkCalcTool(self._getLinkCostCalcSpec(costAttribute[i].id, self.LinkCosts[i], self.LinkTollAttributeIds[i]), scenario=self.Scenario)
                                self._tracker.completeSubtask()
                        
                          
                        with _m.logbook_trace("Calculating peak hour matrix"):  #For each class
                            for i in range(len(self.ModeList)):
                                if EMME_VERSION >= (4,2,1):
                                    matrixCalcTool(self._getPeakHourSpec(peakHourMatrix[i].id, self.DemandMatrixList[i].id), scenario = self.Scenario, 
                                                    num_processors=self.NumberOfProcessors)
                                else:
                                    matrixCalcTool(self._getPeakHourSpec(peakHourMatrix[i].id, self.DemandMatrixList[i].id), scenario = self.Scenario)                        
                            self._tracker.completeSubtask()

                        appliedTollFactor = self._calculateAppliedTollFactor()

                        SOLA_spec = self._getPrimarySOLASpec(peakHourMatrix, appliedTollFactor, self.ModeList, self.ClassResultAttributes, costAttribute)

                        if self.ShapefileLocation is not None:
                            network = self.Scenario.get_network()
                            subareaNodes = self._loadShapefile(network)
                            for node in subareaNodes:
                                node[subareaNodeAttribute.id] = 1
                            self.Scenario.publish_network(network)


                        self._tracker.runTool(subareaAnalysisTool, subarea_nodes = subareaNodeAttribute, subarea_folder = self.OutputFolder, 
                                              traffic_assignment_spec = SOLA_spec, extract_transit = self.ExtractTransit, overwrite = True, gate_labels = self.GateLabel,
                                              start_number = self.StartingNodeNumber, scenario=self.Scenario)
                        



    def _getAtts(self):
        atts = {"Run Title": "Exporting Subarea",
                "Scenario" : str(self.Scenario.id),
                "Extract Transit": self.ExtractTransit,
                "Auto Demand Matrix": self.DemandMatrixIdList,
                "Peak Hour Factor" : str(self.PeakHourFactor),
                "Iterations" : str(self.MaxIterations),
                "Subarea Output Path": self.OutputFolder,
                "self": self.__MODELLER_NAMESPACE__}
        return atts

    def _checkDemandMatrices(self):
        self.DemandMatrixList = []
        for i in range(0,len(self.DemandMatrixIdList)):
            demandMatrix = self.DemandMatrixIdList[i]
            if _MODELLER.emmebank.matrix(demandMatrix) is None:
                raise Exception('Matrix %s was not found!' % demandMatrix)
            else:
                self.DemandMatrixList.append(_MODELLER.emmebank.matrix(demandMatrix))

    @contextmanager
    def _costAttributeMANAGER(self):
        #Code here is executed upon entry
        costAttributes = []
        attributes = {}
        for i in range(len(self.ModeList)):
            attributeCreated = False
            at = '@lkcst'+str(i+1)
            costAttribute = self.Scenario.extra_attribute(at)
            if costAttribute is None:
                #@lkcst hasn't been defined
                _m.logbook_write("Creating temporary link cost attribute '@lkcst"+str(i+1)+"'.")
                costAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                costAttributes.append(costAttribute)
                attributeCreated = True
                attributes[costAttribute.id] = attributeCreated
            
            elif self.Scenario.extra_attribute(at).type != 'LINK':
                #for some reason '@lkcst' exists, but is not a link attribute
                _m.logbook_write("Creating temporary link cost attribute '@lcost"+str(i+2)+"'.")
                at = '@lcost'+str(i+2)
                costAttribute = self.Scenario.create_extra_attribute('LINK', at, default_value=0)
                costAttributes.append(costAttribute)
                attributeCreated = True
                attributes[costAttribute.id] = attributeCreated
        
            if not attributeCreated:
                costAttribute.initialize()
                costAttributes.append(costAttribute)
                attributes[costAttribute.id] = attributeCreated
                _m.logbook_write("Initialized link cost attribute to 0.")
        
        try:
            yield costAttributes
            # Code here is executed upon clean exit
        finally:
            # Code here is executed in all cases.
            for key in attributes:
               if attributes[key] is True:
                   _m.logbook_write("Deleting temporary link cost attribute.")
                   self.Scenario.delete_extra_attribute(key)
                   # Delete the extra cost attribute only if it didn't exist before.    
    @contextmanager
    def _transitTrafficAttributeMANAGER(self):
        
        attributeCreated = False
        bgTrafficAttribute = self.Scenario.extra_attribute('@tvph')
        
        if bgTrafficAttribute is None:
            bgTrafficAttribute = self.Scenario.create_extra_attribute('LINK','@tvph', 0)
            attributeCreated = True
            _m.logbook_write("Created extra attribute '@tvph'")
        else:
            bgTrafficAttribute.initialize(0)
            _m.logbook_write("Initialized existing extra attribute '@tvph' to 0.")
        
        if EMME_VERSION >= (4,2,1):
            extraParameterTool = _MODELLER.tool('inro.emme.traffic_assignment.set_extra_function_parameters')
        else:
            extraParameterTool = _MODELLER.tool('inro.emme.standard.traffic_assignment.set_extra_function_parameters')
        
        extraParameterTool(el1 = '@tvph')
        
        try:
            yield
        finally:
            if attributeCreated:
                self.Scenario.delete_extra_attribute("@tvph")
                _m.logbook_write("Deleted extra attribute '@tvph'")
            extraParameterTool(el1 = '0')

    @contextmanager
    def _subareaNodeAttributeManager(self):
        created = True
        if self.SubareaNodeAttribute is None:
            for i in range(0,100):
                at = "@ti"+str(i)
                if self.Scenario.extra_attribute(at) is None:
                    nodeAttribute = self.Scenario.create_extra_attribute('NODE', at)
                    break
        elif self.Scenario.extra_attribute(self.SubareaNodeAttribute) is None:
            nodeAttribute = self.Scenario.create_extra_attribute('NODE', self.SubareaNodeAttribute)
        elif self.Scenario.extra_attribute(self.SubareaNodeAttribute).type != 'NODE':
            raise Exception ("Subarea node attribute has already been defined but of the wrong type in scenario %d" %self.Scenario.number)
        else:
            nodeAttribute = self.Scenario.extra_attribute(self.SubareaNodeAttribute)
            created = False
        try:
            yield nodeAttribute
        finally:
            if created is True:
                self.Scenario.delete_extra_attribute(nodeAttribute.id)

    def _initResultAttributes(self):

        def get_attribute_name(at):
            if at.startswith("@"):
                return at
            else:
                return "@" + at

        classVolumeAttributes = [get_attribute_name(at) for at in self.ClassResultAttributes]
        i = 0
        for name in classVolumeAttributes:
            if name == "@None" or name == "@none":
                name = None
                continue
            if self.Scenario.extra_attribute(name) is not None:
                _m.logbook_write("Deleting Previous Extra Attributes.")
                self.Scenario.delete_extra_attribute(name)
            _m.logbook_write("Creating link volume attribute '@%s'for class %s." %(name, self.ClassNames[i]))
            self.Scenario.create_extra_attribute('LINK',name, default_value=0)
            i += 1

    def _getTransitBGSpec(self):
        return {
                "result": "@tvph",
                "expression": "(60 / hdw) * (vauteq) * (ttf >= 3)",
                "aggregation": "+",
                "selections": {
                                "link": "all",
                                "transit_line": "all"
                                },
                "type": "NETWORK_CALCULATION"
                }

    def _getLinkCostCalcSpec(self, costAttributeId, linkCost, linkTollAttributeId):
        return {
                "result": costAttributeId,
                "expression": "length * %f + %s" %(linkCost, linkTollAttributeId),
                "aggregation": None,
                "selections": {
                               "link": "all"
                               },
                "type": "NETWORK_CALCULATION"
                }
    
    def _getPeakHourSpec(self, peakHourMatrixId, demandMatrixId): #Was passed the matrix id VALUE, but here it uses it as a parameter
        return {
                "expression": demandMatrixId + "*" + str(self.PeakHourFactor), 
                "result": peakHourMatrixId,
                "constraint": {
                                "by_value": None,
                                "by_zone": None
                                },
                "aggregation": {
                                "origins": None,
                                "destinations": None
                                },
                "type": "MATRIX_CALCULATION"
                }
        
    def _calculateAppliedTollFactor(self):
        appliedTollFactor = []
        if self.TollWeights is not None:
            for i in range(0,len(self.TollWeights)):
                #Toll weight is in $/hr, needs to be converted to min/$
                appliedTollFactor.append(60.0 / self.TollWeights[i]) 
        return appliedTollFactor


    def _getPrimarySOLASpec(self, peakHourMatrixId, appliedTollFactor, modeList, resultAttributes, costAttributes):
         
        if self.PerformanceFlag:
            numberOfProcessors = multiprocessing.cpu_count()
        else:
            numberOfProcessors = max(multiprocessing.cpu_count() - 1, 1)
        
               
        #Generic Spec for SOLA
        SOLA_spec = {
                "type": "SOLA_TRAFFIC_ASSIGNMENT",
                "classes":[],
                "path_analysis": None,
                "cutoff_analysis": None,
                "traversal_analysis": None,
                "performance_settings": {
                    "number_of_processors": numberOfProcessors
                },
                "background_traffic": None,
                "stopping_criteria": {
                    "max_iterations": self.MaxIterations,
                    "relative_gap": self.RelGap,
                    "best_relative_gap": self.BestRelGap,
                    "normalized_gap": self.NormGap
                }
            }
        #Creates a list entry for each mode specified in the Mode List and its associated Demand Matrix
        SOLA_Class_Generator = [{
                    "mode": modeList[i],
                    "demand": peakHourMatrixId[i].id,
                    "generalized_cost": {
                        "link_costs": costAttributes[i].id,
                        "perception_factor": appliedTollFactor[i]
                    },
                    "results": {
                        "link_volumes": resultAttributes[i],
                        "turn_volumes": None,
                        "od_travel_times": {
                            "shortest_paths": None
                        }
                    },
                    "path_analyses": None
                } for i in range(0,len(modeList))]        
        SOLA_spec['classes'] = SOLA_Class_Generator

        return SOLA_spec
    def _loadShapefile(self, network):
        with Shapely2ESRI(self.ShapefileLocation, mode = 'read') as reader:
            if int(reader._size) != 1:
                raise Exception ("There are invalid number of features in the Shapefile. There should only be 1 polygon in the shapefile")
            subareaNodes = []
            for boundary in reader.readThrough():
                for node in network.nodes():
                    point = _geolib.nodeToShape(node)
                    if boundary.contains(point) == True:
                        subareaNodes.append(node)
                break
        return subareaNodes