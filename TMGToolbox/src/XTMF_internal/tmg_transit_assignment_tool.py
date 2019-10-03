"""
    Copyright 2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
import traceback as _traceback
import time as _time
import math
from contextlib import contextmanager
from contextlib import nested
from multiprocessing import cpu_count
from re import split as _regex_split
from json import loads as _parsedict
import inro.modeller as _m
import csv

_trace = _m.logbook_trace
_MODELLER = _m.Modeller()
_bank = _MODELLER.emmebank
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_netEdit = _MODELLER.module('tmg.common.network_editing')
#congestedAssignmentTool = _MODELLER.tool('inro.emme.transit_assignment.congested_transit_assignment')
_dbUtils = _MODELLER.module('inro.emme.utility.database_utilities')
extendedAssignmentTool =_MODELLER.tool('inro.emme.transit_assignment.extended_transit_assignment')
networkCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
networkResultsTool = _MODELLER.tool("inro.emme.transit_assignment.extended.network_results")
matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')
strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)

class TransitAssignmentTool(_m.Tool()):
    version = '1.0.0'
    tool_run_msg = ''
    number_of_tasks = 15

    WalkPerception = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType)
    DemandMatrixList = _m.Attribute(_m.ListType)
    ClassNames = _m.Attribute(list)
    HeadwayFractionAttributeId = _m.Attribute(str)
    EffectiveHeadwayAttributeId = _m.Attribute(str)
    WalkSpeed = _m.Attribute(float)

    #---- class-specific inputs
        # perception values
    ClassWaitPerceptionList = _m.Attribute(list)
    ClassBoardPerceptionList = _m.Attribute(list)
    ClassFarePerceptionList = _m.Attribute(list)
    WalkPerceptionList = _m.Attribute(list)

    xtmf_ClassWaitPerceptionString = _m.Attribute(str)
    xtmf_ClassBoardPerceptionString = _m.Attribute(str)
    xtmf_ClassFarePerceptionString = _m.Attribute(str)
    xtmf_WalkPerceptionString = _m.Attribute(str)

        # attributes
    LinkFareAttributeIdList = _m.Attribute(list)
    SegmentFareAttributeIdList = _m.Attribute(list)
    WalkAttributeIdList = _m.Attribute(list)
    
    xtmf_LinkFareAttributeIdString = _m.Attribute(str)
    xtmf_SegmentFareAttributeIdString = _m.Attribute(str)
    xtmf_WalkPerceptionAttributeIdString = _m.Attribute(str)

        #modes
    xtmf_ClassModeList = _m.Attribute(str)
    #-----


    #----LOS outputs (by class)
    InVehicleTimeMatrixList = _m.Attribute(list)
    WaitTimeMatrixList = _m.Attribute(list)
    WalkTimeMatrixList = _m.Attribute(list)
    FareMatrixList = _m.Attribute(list)
    CongestionMatrixList = _m.Attribute(list)
    PenaltyMatrixList = _m.Attribute(list)
    


    xtmf_InVehicleTimeMatrixString = _m.Attribute(str)
    xtmf_WaitTimeMatrixString = _m.Attribute(str)
    xtmf_WalkTimeMatrixString = _m.Attribute(str)
    xtmf_FareMatrixString = _m.Attribute(str)
    xtmf_CongestionMatrixString = _m.Attribute(str)
    xtmf_PenaltyMatrixString = _m.Attribute(str)
    xtmf_ImpedanceMatrixString = _m.Attribute(str)
    
    #-----

    CalculateCongestedIvttFlag = _m.Attribute(bool)
    CongestionExponentString = _m.Attribute(str)
    EffectiveHeadwaySlope = _m.Attribute(float)
    AssignmentPeriod = _m.Attribute(float)
    Iterations = _m.Attribute(int)
    NormGap = _m.Attribute(float)
    RelGap = _m.Attribute(float)
    xtmf_ScenarioNumber = _m.Attribute(int)
    xtmf_DemandMatrixString = _m.Attribute(str)
    xtmf_NameString = _m.Attribute(str)
    xtmf_congestedAssignment=_m.Attribute(bool)
    xtmf_CSVFile = _m.Attribute(str)

    xtmf_OriginDistributionLogitScale = _m.Attribute(float)
    xtmf_WalkDistributionLogitScale = _m.Attribute(float)

    xtmf_SurfaceTransitSpeed = _m.Attribute(str)
    xtmf_WalkAllWayFlag = _m.Attribute(str)

    xtmf_XRowTTFRange = _m.Attribute(str)
    xtmf_NodeLogitScale = _m.Attribute(float)

    if EMME_VERSION >= (4, 1):
        NumberOfProcessors = _m.Attribute(int)

    def __init__(self):
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)
        self.Scenario = _MODELLER.scenario
        self.DemandMatrixList = [_bank.matrix('mf91')]
        self.ClassNames = ['']

        #attribute IDs
        self.LinkFareAttributeIdList = ['@lfare']
        self.SegmentFareAttributeIdList = ['@sfare']
        self.HeadwayFractionAttributeId = '@frac'
        self.EffectiveHeadwayAttributeId = '@ehdw'
        self.WalkAttributeIdList = ['@walkp']

        self.CalculateCongestedIvttFlag = True
        self.WalkPerception = '1.8:i=10000,20000 or j=10000,20000 or i=97000,98000 or j=97000,98000 \n3.534:i=20000,90000 or j=20000,90000 \n1.14:type=101\n2.26:i=0,1000 or j=0,1000\n1.12:i=1000,7000 or j=1000,7000\n1:mode=t and i=97000,98000 and j=97000,98000\n0:i=9700,10000 or j=9700,10000'
        self.WalkSpeed = 4

        #class-specific inputs
        self.ClassWaitPerceptionList = [3.534]
        self.ClassBoardPerceptionList = [1.0]
        self.ClassFarePerceptionList = [10.694]
        self.ClassModeList = []

        lines = ['1: 0.41: 1.62',
         '2: 0.41: 1.62',
         '3: 0.41: 1.62',
         '4: 0.41: 1.62',
         '5: 0.41: 1.62']
        self.CongestionExponentString = '\n'.join(lines)
        self.EffectiveHeadwaySlope = 0.2
        self.AssignmentPeriod = 3.00
        self.NormGap = 0
        self.RelGap = 0
        self.Iterations = 5
        if EMME_VERSION >= (4, 1):
            self.NumberOfProcessors = cpu_count()
        self._useLogitConnectorChoice = True
        self.xtmf_OriginDistributionLogitScale = 0.2
        self._connectorLogitTruncation = 0.05
        self._useLogitAuxTrChoice = False
        self.xtmf_WalkDistributionLogitScale = 0.2
        self._auxTrLogitTruncation = 0.05
        self._useMultiCore = False
        self._congestionFunctionType = 'CONICAL'
        self._considerTotalImpedance = True

    def page(self):
        if EMME_VERSION < (4, 1, 5):
            raise ValueError('Tool not compatible. Please upgrade to version 4.1.5+')
        pb = _tmgTPB.TmgToolPageBuilder(self, 
                                        title='Multi-Class Transit Assignment v%s' % self.version, 
                                        description="Executes a congested transit assignment procedure\
                                        for GTAModel V4.0.\
                                        <br><br><b>Cannot be called from Modeller.</b>\
                                        <br><br>Hard-coded assumptions:\
                                        <ul><li> Boarding penalties are assumed stored in <b>UT3</b></li>\
                                        <li> The congestion term is stored in <b>US3</b></li>\
                                        <li> In-vehicle time perception is 1.0</li>\
                                        <li> All available transit modes will be used.</li>\
                                        </ul>\
                                        <font color='red'>This tool is only compatible with Emme 4.1.5 and later versions</font>",
                                        runnable = False,
                                        branding_text='- TMG Toolbox')

        return pb.render()

    def run(self):
        self.tool_run_msg = ''
        self.TRACKER.reset()
        try:
            if self.AssignmentPeriod is None:
                raise NullPointerException('Assignment period not specified')
            if self.WalkPerception is None:
                raise NullPointerException('Walk perception not specified')
            if self.CongestionExponentString is None:
                raise NullPointerException('Congestion parameters not specified')
            if self.Iterations is None:
                raise NullPointerException('Maximum iterations not specified')
            if self.NormGap is None:
                raise NullPointerException('Normalized gap not specified')
            if self.RelGap is None:
                raise NullPointerException('Relative gap not specified')
            if self.EffectiveHeadwaySlope is None:
                raise NullPointerException('Effective headway slope not specified')
            if self.LinkFareAttributeIdList is None:
                raise NullPointerException('Link fare attribute not specified')
            if self.SegmentFareAttributeIdList is None:
                raise NullPointerException('Segment fare attribute not specified')

            @contextmanager
            def blank(att):
                try:
                    yield att
                finally:
                    pass

            if self.HeadwayFractionAttributeId is None:
                manager1 = _util.tempExtraAttributeMANAGER(self.Scenario, 'NODE', default=0.5)
            else:
                manager1 = blank(self.Scenario.extra_attribute(self.HeadwayFractionAttributeId))
            if self.WalkAttributeIdList is None:
                manager2 = _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK', default=1.0)
            else:
                manager2 = blank(self.Scenario.extra_attribute(self.WalkAttributeIdList))
            if self.EffectiveHeadwayAttributeId is None:
                manager3 = _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', default=0.0)
            else:
                manager3 = blank(self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId))
            nest = nested(manager1, manager2, manager3)
            with nest as headwayAttribute, walkAttribute, effectiveHeadwayAttribute:
                headwayAttribute.initialize(0.5)
                walkAttribute.initialize(1.0)
                effectiveHeadwayAttribute.initialize(0.0)
                self.HeadwayFractionAttributeId = headwayAttribute.id
                self.WalkAttributeIdList = walkAttribute.id
                self.EffectiveHeadwayAttributeId = effectiveHeadwayAttribute.id
                self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise 

        self.tool_run_msg = _m.PageBuilder.format_info('Done.')

    def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixString, xtmf_NameString,\
        WalkSpeed, xtmf_WalkPerceptionString, xtmf_WalkPerceptionAttributeIdString, \
        xtmf_ClassWaitPerceptionString, xtmf_ClassBoardPerceptionString, xtmf_ClassFarePerceptionString, xtmf_ClassModeList,\
        HeadwayFractionAttributeId, xtmf_LinkFareAttributeIdString, xtmf_SegmentFareAttributeIdString, \
        EffectiveHeadwayAttributeId, EffectiveHeadwaySlope,  AssignmentPeriod, \
        Iterations, NormGap, RelGap, \
        xtmf_InVehicleTimeMatrixString, xtmf_WaitTimeMatrixString, xtmf_WalkTimeMatrixString, xtmf_FareMatrixString, xtmf_CongestionMatrixString, xtmf_PenaltyMatrixString, xtmf_ImpedanceMatrixString, \
        xtmf_OriginDistributionLogitScale, CalculateCongestedIvttFlag, CongestionExponentString, xtmf_congestedAssignment, xtmf_CSVFile, xtmf_SurfaceTransitSpeed, xtmf_WalkAllWayFlag, \
        xtmf_XRowTTFRange, xtmf_NodeLogitScale):
        
        if EMME_VERSION < (4, 1, 5):
            raise Exception('Tool not compatible. Please upgrade to version 4.1.5+')
        
        self.EffectiveHeadwayAttributeId = EffectiveHeadwayAttributeId
        self.HeadwayFractionAttributeId = HeadwayFractionAttributeId
        self.CalculateCongestedIvttFlag = CalculateCongestedIvttFlag
        self.EffectiveHeadwaySlope = EffectiveHeadwaySlope
        self.CongestionExponentString = CongestionExponentString
        self.xtmf_OriginDistributionLogitScale = xtmf_OriginDistributionLogitScale
        self.AssignmentPeriod = AssignmentPeriod
        self.Iterations = Iterations
        self.NormGap = NormGap
        self.RelGap = RelGap
        self.xtmf_congestedAssignment = xtmf_congestedAssignment
        self.ClassNames = [x for x in xtmf_NameString.split(',')]

        if xtmf_SurfaceTransitSpeed.lower() == 'false' or xtmf_SurfaceTransitSpeed == "":
            self.SurfaceTransitSpeed = False
        else:
            self.SurfaceTransitSpeed = [x for x in xtmf_SurfaceTransitSpeed.split(',')]

        if str(xtmf_WalkAllWayFlag).lower() == "true":
            self.WalkAllWayFlag = True
        else:
            self.WalkAllWayFlag = False
   
        #class-specific inputs
        self.ClassWaitPerceptionList = [float (x.strip("\'").strip('\"')) for x in xtmf_ClassWaitPerceptionString.split(',')]
        self.ClassBoardPerceptionList = [float (x.strip("\'").strip('\"')) for x  in xtmf_ClassBoardPerceptionString.split(',')]
        self.ClassFarePerceptionList = [float(x.strip("\'").strip('\"')) for x in xtmf_ClassFarePerceptionString.split(',')]
        
        self.ttfs_xrow = set()
        xtmf_XRowTTFRange = xtmf_XRowTTFRange.split(",")
        for ttf_range in xtmf_XRowTTFRange:
            if "-" in ttf_range:
                ttf_range = ttf_range.split("-")
                for i in range(int(ttf_range[0]), int(ttf_range[1])+1):
                    self.ttfs_xrow.add(int(i))
            else:
                self.ttfs_xrow.add(int(ttf_range))

        self.LinkFareAttributeIdList = xtmf_LinkFareAttributeIdString.split(',')
        self.SegmentFareAttributeIdList = xtmf_SegmentFareAttributeIdString.split(',')

        xtmf_WalkPerceptionString = xtmf_WalkPerceptionString.strip("\'").strip('\"')

        if xtmf_WalkPerceptionString is not None:
            xtmf_WalkPerceptionString = xtmf_WalkPerceptionString.replace('::', '\n')
            self.WalkPerceptionList = xtmf_WalkPerceptionString.split(';')
        if xtmf_WalkPerceptionAttributeIdString is not None:
            self.WalkAttributeIdList = xtmf_WalkPerceptionAttributeIdString.split(',')

        self.Scenario = _bank.scenario(xtmf_ScenarioNumber)
        if self.Scenario is None:
            raise Exception('Scenario %s was not found!' % xtmf_ScenarioNumber)

        aux_mode_chars = ''
        for mode in self.Scenario.modes():
            if mode.type == 'AUX_TRANSIT':
                aux_mode_chars += mode.id   

        self.ClassModeList = [["*"] if  "*" in x else list(set(x + aux_mode_chars) ) for x in xtmf_ClassModeList.split(',')]

        self.DemandMatrixList = []
        for demandMatrix in xtmf_DemandMatrixString.split(','):
            if _bank.matrix(demandMatrix) is None:
                raise Exception('Matrix %s was not found!' % demandMatrix)
            else:
                self.DemandMatrixList.append(_bank.matrix(demandMatrix))

        for walk in self.WalkAttributeIdList:
            if self.Scenario.extra_attribute(walk) is None:
                raise Exception('Walk perception attribute %s does not exist' % walk)
        if self.Scenario.extra_attribute(self.HeadwayFractionAttributeId) is None:
            raise Exception('Headway fraction attribute %s does not exist' % self.HeadwayFractionAttributeId)
        if self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId) is None:
            raise Exception('Effective headway attribute %s does not exist' % self.EffectiveHeadwayAttributeId)
        for id in self.LinkFareAttributeIdList:
            if  self.Scenario.extra_attribute(id) is None:
                raise Exception('Link fare attribute %s does not exist' % id)
        for id in self.SegmentFareAttributeIdList:
           if self.Scenario.extra_attribute(id) is None:
                raise Exception('Segment fare attribute %s does not exist' % id)
        if xtmf_InVehicleTimeMatrixString:
            self.InVehicleTimeMatrixList = xtmf_InVehicleTimeMatrixString.split(',')
        if xtmf_WaitTimeMatrixString:
            self.WaitTimeMatrixList = xtmf_WaitTimeMatrixString.split(',')
        if xtmf_WalkTimeMatrixString:
            self.WalkTimeMatrixList = xtmf_WalkTimeMatrixString.split(',')
        if xtmf_FareMatrixString:
            self.FareMatrixList = xtmf_FareMatrixString.split(',')
        if xtmf_CongestionMatrixString:
            self.CongestionMatrixList = xtmf_CongestionMatrixString.split(',')
        if xtmf_PenaltyMatrixString:
            self.PenaltyMatrixList = xtmf_PenaltyMatrixString.split(',')
        if xtmf_ImpedanceMatrixString:
            self.ImpedanceMatrixList = xtmf_ImpedanceMatrixString.split(',')

        if float(xtmf_NodeLogitScale) == 1:
            self.NodeLogitScale = False
        else:
            self.NodeLogitScale = float(xtmf_NodeLogitScale)

        if xtmf_CSVFile.lower() == 'none':
            self.CSVFile = None
        else:
            self.CSVFile = xtmf_CSVFile
        print 'Starting Transit Assignment'
        try:
            self._Execute()
        except Exception as e:
            raise Exception(_util.formatReverseStack())
        print 'Finished Transit Assignment'

    def _Execute(self):
        with _trace(name='{classname} v{version}'.format(classname=self.__class__.__name__, version=self.version), attributes=self._GetAtts()):
            with _trace('Checking travel time functions'):
                changes = self._HealTravelTimeFunctions()
                if changes == 0:
                    _m.logbook_write('No problems were found')
            self._InitMatrices()
            self._ChangeWalkSpeed()
            with self._getImpendenceMatrices():
                self.TRACKER.startProcess(5)
                self._AssignHeadwayFraction()
                self.TRACKER.completeSubtask()
                self._AssignEffectiveHeadway()
                self.TRACKER.completeSubtask()
                for i in range(0, len(self.ClassNames)):
                    WalkPerceptionArray = self._ParsePerceptionString(i)
                    self._AssignWalkPerception(WalkPerceptionArray, self.WalkAttributeIdList[i])
                self.TRACKER.completeSubtask()
                if self.NodeLogitScale is not False:
                    network = self.Scenario.get_network()
                    for node in network.regular_nodes():
                        node.data1 = 0
                        agency_counter = 0
                        agencies = set()
                        if node.number > 99999:
                            continue
                        for link in node.incoming_links():
                            if link.i_node.is_centroid is True:
                                node.data1 = -1
                            if link.i_node.number > 99999:
                                agency_counter += 1
                        for link in node.outgoing_links():
                            if link.j_node.is_centroid is True:
                                node.data1 = -1
                            '''if link.j_node.number > 99999:
                                agency_counter += 1'''
                        if agency_counter > 1:
                            node.data1 = -1
                            for link in node.incoming_links():
                                if link.i_node.number > 99999:
                                    link.i_node.data1 = -1
                            for link in node.outgoing_links():
                                if link.j_node.number > 99999:
                                    link.j_node.data1 =-1
                    self.Scenario.publish_network(network)
                with _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE') as stsu_att, self._tempStsuTTFs() as ttf_map:
                    if self.SurfaceTransitSpeed != False:
                        self._GenerateBaseSpeed(stsu_att)
                    if self.xtmf_congestedAssignment == True:
                        self.usedFunctions = self._AddCongTermToFunc()
                        with _trace(name = "TMG Congested Transit Assignment", attributes = self._GetAttsCongested()) as trace:
                            with _dbUtils.congested_transit_temp_funcs(self.Scenario, self.usedFunctions, False, 'us3'):
                                with _dbUtils.backup_and_restore(self.Scenario, {'TRANSIT_SEGMENT': ['data3']}):
                                    self.ttfDict = self._ParseExponentString()
                                    for iteration in range(0, self.Iterations + 1):
                                        with _trace("Iteration %d" %iteration):
                                            print "Starting Iteration %d" %iteration
                                            if iteration == 0:
                                                self._PrepStrategyFiles()
                                                zeroes = [0.0]*_bank.dimensions['transit_segments']
                                                setattr(self.Scenario._net.segment,'data3',zeroes)
                                                self._RunExtendedTransitAssignment(iteration)
                                                self.alphas = [1.0]
                                                assignedClassDemand = self._ComputeAssignedClassDemand()
                                                assignedTotalDemand = sum(assignedClassDemand)
                                                network = self._PrepareNetwork(stsu_att)
                                                if self.SurfaceTransitSpeed != False:
                                                    network = self._SurfaceTransitSpeedUpdate(network, 1, stsu_att, False)
                                                averageMinTripImpedence = self._ComputeMinTripImpedence(assignedClassDemand)
                                                congestionCosts = self._GetCongestionCosts(network,assignedTotalDemand)
                                                previousAverageMinTripImpedence = averageImpedence = averageMinTripImpedence + congestionCosts
                                                if self.CSVFile is not None:
                                                    self._WriteCSVFiles(iteration, network, '', '', '')
                                            else:
                                                excessKM = self._ComputeSegmentCosts(network)
                                                self._RunExtendedTransitAssignment(iteration)
                                                network = self._UpdateNetwork(network)
                                                averageMinTripImpedence = self._ComputeMinTripImpedence(assignedClassDemand)
                                                lambdaK = self._FindStepSize(network, averageMinTripImpedence, averageImpedence, assignedTotalDemand)
                                                if self.SurfaceTransitSpeed != False:
                                                    network = self._SurfaceTransitSpeedUpdate(network, lambdaK, stsu_att, False)
                                                self._UpdateVolumes(network, lambdaK)
                                                averageImpedence, cngap, crgap, normGapDifference, netCosts = self._ComputeGaps(assignedTotalDemand, lambdaK, averageMinTripImpedence, averageImpedence, network)
                                                previousAverageMinTripImpedence = averageImpedence
                                                if self.CSVFile is not None:
                                                    self._WriteCSVFiles(iteration, network, cngap, crgap, normGapDifference)
                                                if crgap < self.RelGap or normGapDifference >= 0:
                                                    break
                            self._SaveResults(network, stsu_att)
                            trace.write(name="TMG Congested Transit Assignment", attributes={'assign_end_time': self.Scenario.transit_assignment_timestamp})
                    else:
                        if self.SurfaceTransitSpeed is False:
                            for i in range(0, len(self.ClassNames)):
                                specUncongested = self._GetBaseAssignmentSpecUncongested(i)
                                self.TRACKER.runTool(extendedAssignmentTool, specification=specUncongested, class_name=self.ClassNames[i], scenario=self.Scenario, add_volumes=(i!=0))
                        else:
                            for iterations in range(0, self.Iterations):
                                for i in range(0, len(self.ClassNames)):
                                    specUncongested = self._GetBaseAssignmentSpecUncongested(i)
                                    self.TRACKER.runTool(extendedAssignmentTool, specification=specUncongested, class_name=self.ClassNames[i], scenario=self.Scenario, add_volumes=(i!=0))
                                network = self.Scenario.get_network()
                                network = self._SurfaceTransitSpeedUpdate(network, 1, stsu_att, True)

                self._ExtractOutputMatrices()
                _MODELLER.desktop.refresh_needed(True)
    def _GetAtts(self):
        atts = {'Scenario': '%s - %s' % (self.Scenario, self.Scenario.title),
         'Version': self.version,
         'Wait Perception': self.ClassWaitPerceptionList,
         'Fare Perception': self.ClassFarePerceptionList,
         'Boarding Perception': self.ClassBoardPerceptionList,
         'Congestion':self.xtmf_congestedAssignment,
         'self': self.__MODELLER_NAMESPACE__}
        return atts

    def _HealTravelTimeFunctions(self):
        changes = 0
        for function in _bank.functions():
            if function.type != 'TRANSIT_TIME':
                continue
            cleanedExpression = function.expression.replace(' ', '')
            if 'us3' in cleanedExpression:
                if cleanedExpression.endswith('*(1+us3)'):
                    index = cleanedExpression.find('*(1+us3)')
                    newExpression = cleanedExpression[:index]
                    function.expression = newExpression
                    print 'Detected function %s with existing congestion term.' % function
                    print "Original expression= '%s'" % cleanedExpression
                    print "Healed expression= '%s'" % newExpression
                    print ''
                    _m.logbook_write('Detected function %s with existing congestion term.' % function)
                    _m.logbook_write("Original expression= '%s'" % cleanedExpression)
                    _m.logbook_write("Healed expression= '%s'" % newExpression)
                    changes += 1
                else:
                    raise Exception('Function %s already uses US3, which is reserved for transit' % function + ' segment congestion values. Please modify the expression ' + 'to use different attributes.')

        return changes

    def _InitMatrices(self):
        for i in range(0, len(self.DemandMatrixList)):
                if self.InVehicleTimeMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.InVehicleTimeMatrixList[i], description='Transit in-vehicle travel times for %s' % self.ClassNames[-1])
                else:
                    self.InVehicleTimeMatrixList[i] = None
                if self.CongestionMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.CongestionMatrixList[i], description='Transit in-vehicle congestion for %s' % self.ClassNames[-1])
                else:
                    self.CongestionMatrixList[i] = None
                if self.WalkTimeMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.WalkTimeMatrixList[i], description='Transit total walk times for %s' % self.ClassNames[-1])
                else:
                    self.WalkTimeMatrixList[i] = None
                if self.WaitTimeMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.WaitTimeMatrixList[i], description='Transit total wait times for %s' % self.ClassNames[-1])
                else:
                    self.WaitTimeMatrixList[i] = None
                if self.FareMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.FareMatrixList[i], description='Transit total fares for %s' % self.ClassNames[-1])
                else:
                    self.FareMatrixList[i] = None
                if self.PenaltyMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.PenaltyMatrixList[i], description='Transit total boarding penalties for %s' % self.ClassNames[-1])
                else:
                    self.PenaltyMatrixList[i] = None
                if self.ImpedanceMatrixList[i] != 'mf0':
                    _util.initializeMatrix(id=self.ImpedanceMatrixList[i], description='Transit Perceived Travel times for %s' % self.ClassNames[-1])
                else:
                    self.ImpedanceMatrixList[i] = None

    def _ChangeWalkSpeed(self):
        with _trace('Setting walk speeds to %s' % self.WalkSpeed):
            if EMME_VERSION >= (4, 1):
                self._ChangeWalkSpeed4p1()
            else:
                self._ChangeWalkSpeed4p0()

    def _ChangeWalkSpeed4p0(self):
        changeModeTool = _MODELLER.tool('inro.emme.data.network.mode.change_mode')
        for mode in self.Scenario.modes():
            if mode.type != 'AUX_TRANSIT':
                continue
            changeModeTool(mode, mode_speed=self.WalkSpeed, scenario=self.Scenario)

    def _ChangeWalkSpeed4p1(self):
        partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
        for mode in partialNetwork.modes():
            if mode.type != 'AUX_TRANSIT':
                continue
            mode.speed = self.WalkSpeed
            _m.logbook_write('Changed mode %s' % mode.id)

        baton = partialNetwork.get_attribute_values('MODE', ['speed'])
        self.Scenario.set_attribute_values('MODE', ['speed'], baton)

    def _AssignHeadwayFraction(self):
        exatt = self.Scenario.extra_attribute(self.HeadwayFractionAttributeId)
        exatt.initialize(0.5)

    def _AssignEffectiveHeadway(self):
        exatt = self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId)
        exatt.initialize(0.0)
        smallHeadwaySpec = {'result': self.EffectiveHeadwayAttributeId,
         'expression': 'hdw',
         'aggregation': None,
         'selections': {'transit_line': 'hdw=0,15'},
         'type': 'NETWORK_CALCULATION'}
        largeHeadwaySpec = {'result': self.EffectiveHeadwayAttributeId,
         'expression': '15+2*' + str(self.EffectiveHeadwaySlope) + '*(hdw-15)',
         'aggregation': None,
         'selections': {'transit_line': 'hdw=15,999'},
         'type': 'NETWORK_CALCULATION'}
        networkCalcTool(smallHeadwaySpec, self.Scenario)
        networkCalcTool(largeHeadwaySpec, self.Scenario)

    def _AssignWalkPerception(self, perceptionArray, WalkAttributeId):
        exatt = self.Scenario.extra_attribute(WalkAttributeId)
        exatt.initialize(1.0)

        def applySelection(val, selection):
            spec = {'result': WalkAttributeId,
             'expression': str(val),
             'aggregation': None,
             'selections': {'link': selection},
             'type': 'NETWORK_CALCULATION'}
            networkCalcTool(spec, self.Scenario)

        with _trace('Assigning perception factors'):
            for i in range(0, len(perceptionArray)):
                applySelection(perceptionArray[i][0], perceptionArray[i][1])

    def _GetAttsCongested(self):
        attributes = {
        'Scenario':'%s - %s' % (self.Scenario, self.Scenario.title),
        'Assignment Period' :  self.AssignmentPeriod,
        'Iterations' : self.Iterations,
        'Normalized Gap' : self.NormGap,
        'Relative Gap' : self.RelGap,
        'congestion function' : self._GetFuncSpec(),
        'spec' : self._GetBaseAssignmentSpec()
        }
        return attributes

    def _GenerateBaseSpeed(self, stsu_att):
        if self.Scenario.extra_attribute('@doors') is None:
            print "No Transit Vehicle door information is present in the network. Default assumption will be 2 doors per surface vehicle."
        if self.Scenario.extra_attribute("@boardings") is None:
            self.Scenario.create_extra_attribute("TRANSIT_SEGMENT", "@boardings")
        if self.Scenario.extra_attribute("@alightings") is None:
            self.Scenario.create_extra_attribute("TRANSIT_SEGMENT", "@alightings")
        if self.Scenario.extra_attribute("@erow_speed") is None:
            erow_defined = False
            print "No segment specific exclusive ROW speed attribute is defined in the network. Global erow speed will be used."
        else:
            erow_defined = True
        self.models = self._SetUpLineAttributes(stsu_att)
        network = self.Scenario.get_network()
        for line in network.transit_lines():
            if line[stsu_att.id] != 0.0:
                index = int(line[str(stsu_att.id)])-1
                default_duration = self.models[index]['default_duration']
                correlation = self.models[index]['correlation']
                erow_speed_global = self.models[index]['erow_speed']
            else:
                continue
            segments = line.segments()
            number_of_segments = segments.__length_hint__()
            for segment in segments:
                if segment.allow_alightings == True and segment.allow_boardings == True:
                    segment.dwell_time = 0.01
                else:
                    segment.dwell_time = 0.0

                if segment.j_node is None:
                    continue

                segment_number = segment.number
                segment.transit_time_func = self.stsu_ttf_map[segment.transit_time_func]                    
                time = segment.link["auto_time"]

                if time > 0.0:
                    if segment.transit_time_func in self.ttfs_xrow:
                        if erow_defined == True and segment["@erow_speed"] > 0.0:
                                segment.data1 = segment["@erow_speed"]
                        else:
                            segment.data1 = erow_speed_global
                    else:
                        segment.data1 = (segment.link.length * 60.0)/(time*correlation)

                if time <= 0.0:
                    if erow_defined == True and segment["@erow_speed"] > 0.0:
                        segment.data1 = segment["@erow_speed"]
                    else:
                        if segment_number <= 1 or segment_number >= (number_of_segments-1):
                            segment.data1 = 20
                        else:
                            segment.data1 = erow_speed_global
                if segment_number == 0:
                    continue
                segment.dwell_time = (segment["@tstop"]*default_duration)/60
        data = network.get_attribute_values('TRANSIT_SEGMENT', ['dwell_time', 'transit_time_func', 'data1'])
        self.Scenario.set_attribute_values('TRANSIT_SEGMENT', ['dwell_time', 'transit_time_func', 'data1'], data)
        self.ttfs_changed = True

    def _AddCongTermToFunc(self):
        usedFunctions = set()
        anyNonZero = False
        for segment in self.Scenario.get_network().transit_segments():
            if segment.transit_time_func != 0:
                usedFunctions.add('ft'+str(segment.transit_time_func))    
                anyNonZero = True
        if not anyNonZero:
            raise Exception("All segments have a TTF of 0!")
        return list(usedFunctions)

    def _PrepStrategyFiles(self):
        # TODO: Investigate this code
        strategies = self.Scenario.transit_strategies
        strategies.clear()
        _time.sleep(0.05)
        data = {'type': 'CONGESTED_TRANSIT_ASSIGNMENT',
                 'namespace': str(self),
                 'custom_status': True,
                 'per_strat_attributes': {'TRANSIT_SEGMENT': ['transit_time']}}
        mode_int_ids = self.Scenario.get_attribute_values('MODE', [])[0]

        def format_modes(modes):
            if '*' in modes:
                modes = [m for m in self.Scenario.modes() if m.type in ('TRANSIT','AUX_TRANSIT')]
            modes = [str(m) for m in modes]
            return ''.join(modes)

        classData = []
        for i in range(0,len(self.ClassNames)):
            name = self.ClassNames[i]
            demand =  _MODELLER.matrix_snapshot(_bank.matrix(self.DemandMatrixList[i]))
            modes = self.ClassModeList[i]
            classData.append({'name':name,
                              'modes':format_modes(modes),
                              'demand':demand,
                              'strat_files':[]})
        data['classes'] = classData
        data['multi_class'] = True
        strategies.data = data
        self.strategies = strategies

    def _GetTransitAssignmentSpec(self, index):
        if self.ClassFarePerceptionList[index] == 0.0:
                farePerception = 0.0
        else:
                farePerception = 60.0 / self.ClassFarePerceptionList[index]
        baseSpec = {
                'modes': self.ClassModeList[index],
                'demand': self.DemandMatrixList[index].id,
                'waiting_time': {
                    'headway_fraction': self.HeadwayFractionAttributeId,
                    'effective_headways': self.EffectiveHeadwayAttributeId,
                    'spread_factor': 1,
                    'perception_factor': self.ClassWaitPerceptionList[index]
                    },
                'boarding_time': {
                    'at_nodes': None,
                    'on_lines': {
                        'penalty': 'ut3',
                        'perception_factor': self.ClassBoardPerceptionList[index]
                        },
                    'global': None,
                    'on_segments': None
                    },
                'boarding_cost': {
                    'at_nodes': None,
                    'on_lines': None,
                    'global': {
                        'penalty': 0,
                        'perception_factor': 1
                        },
                    },
                'in_vehicle_time': {
                    'perception_factor': 'us2'
                    },
                'in_vehicle_cost': {
                    'penalty': self.SegmentFareAttributeIdList[index],
                    'perception_factor': farePerception
                    },
                'aux_transit_time': {
                    'perception_factor': self.WalkAttributeIdList[index]
                    },
                'aux_transit_cost': {
                    'penalty': self.LinkFareAttributeIdList[index],
                    'perception_factor': farePerception
                    },
                'connector_to_connector_path_prohibition': None,
                'od_results': {
                    'total_impedance': self.ImpedenceMatrices[index].id
                    },
                'flow_distribution_between_lines': {
                    'consider_total_impedance': self._considerTotalImpedance
                    },
                'save_strategies': True,
                'type': 'EXTENDED_TRANSIT_ASSIGNMENT'
                }
        if self._useLogitConnectorChoice:
            baseSpec['flow_distribution_at_origins'] = {'choices_at_origins': {
                    'choice_points':'ALL_ORIGINS', 
                    'choice_set': 'ALL_CONNECTORS',
                    'logit_parameters': {
                        'scale': self.xtmf_OriginDistributionLogitScale,
                        'truncation': self._connectorLogitTruncation}},
                 'fixed_proportions_on_connectors': None}
        
        if EMME_VERSION >= (4, 1):
            baseSpec['performance_settings'] = {'number_of_processors': self.NumberOfProcessors}
        if self.NodeLogitScale is not False:
            baseSpec['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {
                'choices_at_regular_nodes': {
                    'choice_points': 'ui1',
                    'aux_transit_choice_set': 'ALL_POSSIBLE_LINKS',
                    'logit_parameters': {
                        'scale': self.NodeLogitScale,
                        'truncation': self._connectorLogitTruncation}
                    }
                }
        else:
            baseSpec['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {
                'choices_at_regular_nodes':'OPTIMAL_STRATEGY'
                }
        if EMME_VERSION >= (4,2,1):
            modeList = []
            partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
            #if all modes are selected for class, get all transit modes for journey levels
            if self.ClassModeList[index] == ['*']:
                for mode in partialNetwork.modes():
                    if mode.type == 'TRANSIT': 
                        modeList.append({"mode": mode.id, "next_journey_level": 1})
            baseSpec["journey_levels"] = [
                    {
                        "description": "Walking",
                        "destinations_reachable": self.WalkAllWayFlag,
                        "transition_rules": modeList,
                        "boarding_time": None,
                        "boarding_cost": None,
                        "waiting_time": None
                    },
                    {
                        "description": "Transit",
                        "destinations_reachable": True,
                        "transition_rules": modeList,
                        "boarding_time": None,
                        "boarding_cost": None,
                        "waiting_time": None
                    }
            ]
        return baseSpec
 
    def _RunExtendedTransitAssignment(self, iteration):
        if iteration == 0:
            msg = "Prepare Initial Assignment"
        else:
            msg = "Prepare Transit Assignment"
        assignmentTool = extendedAssignmentTool
        assignmentTool.iterative_transit_assignment = True
        with _trace(msg):
            for i in range(0,len(self.DemandMatrixList)):
                spec = self._GetTransitAssignmentSpec(i)
                if i == 0:
                    self.TRACKER.runTool(assignmentTool, specification = spec, scenario = self.Scenario, add_volumes = False)
                else:
                    self.TRACKER.runTool(assignmentTool, specification = spec, scenario = self.Scenario, add_volumes = True)
                strategiesName = 'Iteration %s %s' %(iteration, self.ClassNames[i])
                strategiesFile = self.strategies.add_strat_file(strategiesName)
                classData = _dbUtils.get_multi_class_strat(self.strategies, self.ClassNames[i])
                classData['strat_files'].append(strategiesName)
                values = self.Scenario.get_attribute_values('TRANSIT_SEGMENT', ['transit_time'])
                strategiesFile.add_attr_values('TRANSIT_SEGMENT', 'transit_time', values[1])


    def _ComputeAssignedClassDemand(self):
        assignedDemand = []
        for i in range(0,len(self.ClassNames)):
            matrixCalcSpec = {'type': 'MATRIX_CALCULATION',
                              'expression': str(self.DemandMatrixList[i])+' * (p.ne.q)',
                              'aggregation': {
                                'origins':'+',
                                'destinations':'+'
                                }
                             }
            report = matrixCalcTool(specification = matrixCalcSpec, scenario = self.Scenario, num_processors = self.NumberOfProcessors)
            trips = report['result']
            if trips <= 0:
                raise Exception("Invalid number of trips assigned")
            assignedDemand.append(trips)
        return assignedDemand

    def _PrepareNetwork(self, stsu_att):
        #network = self.Scenario.get_network()
        network = self.Scenario.get_partial_network(['LINK', 'TRANSIT_SEGMENT', 'TRANSIT_LINE','TRANSIT_VEHICLE'], include_attributes=False)
        attributes_to_copy = {
            'TRANSIT_VEHICLE': ['total_capacity'],
            'NODE': ['initial_boardings', 'final_alightings'],
            'LINK': ['length', 'aux_transit_volume', 'auto_time'],
            'TRANSIT_LINE': ['headway', str(stsu_att.id), 'data2', '@doors'],
            'TRANSIT_SEGMENT': ['dwell_time', 'transit_volume', 'transit_time', 'transit_boardings', 'transit_time_func', '@tstop']
            }
        if self.Scenario.extra_attribute('@tstop') is None:
            if self.SurfaceTransitSpeed == False:
                attributes_to_copy['TRANSIT_SEGMENT'].remove('@tstop')
            else:
                raise Exception("@tstop attribute needs to be defined. @tstop is an integer that shows how many transit stops are on each transit segment.")
        if 'auto_time' not in self.Scenario.attributes('LINK'):
            if self.SurfaceTransitSpeed == False:
                attributes_to_copy['LINK'].remove('auto_time')
            else:
                raise Exception("An auto assignment needs to be present on the scenario")
        if self.Scenario.extra_attribute('@doors') is None:
            attributes_to_copy['TRANSIT_LINE'].remove('@doors') 

        for type, atts in attributes_to_copy.iteritems():
            atts = list(atts)
            data = self.Scenario.get_attribute_values(type, atts)
            network.set_attribute_values(type, atts, data)
        for type, mapping in self._AttributeMapping().iteritems():
            for source, dest in mapping.iteritems():
                network.copy_attribute(type, source, dest)
        network.create_attribute('TRANSIT_SEGMENT', 'current_voltr')
        network.create_attribute('TRANSIT_SEGMENT', 'cost')
        network.create_attribute('TRANSIT_LINE', 'total_capacity')
        network.copy_attribute('TRANSIT_SEGMENT', 'transit_time', 'uncongested_time')
        network.copy_attribute('TRANSIT_SEGMENT', 'dwell_time', 'base_dwell_time')
        for line in network.transit_lines():
            line.total_capacity = 60.0*self.AssignmentPeriod*line.vehicle.total_capacity/line.headway
        return network


    def _ComputeMinTripImpedence(self, classAssignedDemand):
        averageMinTripImpedence = 0.0
        classImped = []
        for i in range(0, len(classAssignedDemand)):
            matrixCalcSpec = {
                'type': 'MATRIX_CALCULATION',
                'expression': str(self.ImpedenceMatrices[i].id)+'*'+str(self.DemandMatrixList[i])+'/'+str(classAssignedDemand[i]),
                'aggregation': {
                    'origins':'+',
                    'destinations':'+'
                    }
                }
            report = matrixCalcTool(specification = matrixCalcSpec, scenario = self.Scenario, num_processors = self.NumberOfProcessors)
            classImped.append(float(report['result']))
        for i in range(0, len(classAssignedDemand)):
            averageMinTripImpedence += (classImped[i]*classAssignedDemand[i])
        averageMinTripImpedence = averageMinTripImpedence/sum(classAssignedDemand)
        return averageMinTripImpedence
    
    def _GetCongestionCosts(self, network, assignedDemand):
        congestionCost = 0.0
        for line in network.transit_lines():
            capacity = float(line.total_capacity)
            for segment in line.segments():
                flowXtime = float(segment.voltr) * (float(segment.timtr) - float(segment.dwell_time))
                congestion = self._CalculateSegmentCost(float(segment.voltr), capacity, segment)
                congestionCost += flowXtime*congestion
        return congestionCost/assignedDemand
    
    def _WriteCSVFiles(self, iteration, network, cngap, crgap, normgapdiff):
        if iteration == 0:
            with open (self.CSVFile, 'wb') as iterationFile:
                writer = csv.writer(iterationFile)
                header = ["iteration", "line", "capacity", "boardings", "max v/c", "average v/c", "line speed w congestion", "line speed"]
                writer.writerow(header)
        with open (self.CSVFile, 'ab') as iterationFile:
            writer = csv.writer(iterationFile)
            for line in network.transit_lines():
                boardings = 0.0
                capacity = 0.0
                maxVC = float("-inf")
                avgVC = 0.0
                lineSpeed = 0.0
                totalLength = 0.0
                totalTime = 0.0
                tT = 0.0
                capacity = float(line.total_capacity)
                i = 0
                for segment in line.segments():
                    boardings += segment.board
                    VC = float(segment.voltr)/capacity
                    if VC > maxVC:
                        maxVC = VC
                    if segment.j_node is None:
                        segmentLength = 0.0
                    else:
                        segmentLength = float(segment.link.length)
                    totalLength += segmentLength
                    avgVC += (VC * segmentLength)
                    baseTime = float(segment.uncongested_time) - float(line.segment(i+1).base_dwell_time)
                    if iteration == 0:
                        cost = 0
                    else:
                        cost = self._CalculateSegmentCost(segment.voltr, capacity, segment)
                    dwell_time = float(segment.dwell_time)
                    travel_time =  (baseTime+float(line.segment(i+1).dwell_time))*(1+cost)
                    tt = baseTime+dwell_time
                    totalTime += travel_time
                    tT += tt
                    i += 1
                lineSpeed = totalLength/totalTime*60
                ls = totalLength/tT*60
                avgVC /= totalLength
                row = [iteration, str(line.id), capacity, boardings, maxVC, avgVC, lineSpeed, ls]
                writer.writerow(row)
            row = [iteration, "GAPS", cngap, crgap, normgapdiff]
            writer.writerow(row)

    def _SurfaceTransitSpeedUpdate(self, network, lambdaK, stsu_att, final):
        if 'transit_alightings' not in network.attributes('TRANSIT_SEGMENT'):
            network.create_attribute('TRANSIT_SEGMENT', 'transit_alightings', 0.0)
        for line in network.transit_lines():
            prevVolume = 0.0
            headway = line.headway
            number_of_trips = self.AssignmentPeriod*60.0/headway

            # Get the STSU model to use
            if line[str(stsu_att.id)] != 0.0:
                model = self.models[int(line[str(stsu_att.id)])-1]
            else:
                continue

            boarding_duration = model['boarding_duration']
            alighting_duration  = model['alighting_duration']
            default_duration = model['default_duration']
            correlation = model['correlation']
            mode_filter = model['mode_filter']

            try:
                doors = segment.line["@doors"]
                if doors == 0.0:
                    number_of_door_pairs = 1.0
                else:
                    number_of_door_pairs = doors/2.0
            except:
                number_of_door_pairs = 1.0

            for segment in line.segments(include_hidden=True):
                segment_number = segment.number
                if segment_number > 0 and segment.j_node is not None:
                    segment.transit_alightings = max(prevVolume + segment.transit_boardings - segment.transit_volume, 0.0)
                else:
                    continue
                # prevVolume is used above for the previous segments volume, the first segment is always ignored.
                prevVolume = segment.transit_volume
                
                boarding = segment.transit_boardings/number_of_trips/number_of_door_pairs
                alighting = segment.transit_alightings/number_of_trips/number_of_door_pairs

                old_dwell = segment.dwell_time
                segment_dwell_time =(boarding_duration*boarding) + (alighting_duration*alighting) + (segment["@tstop"]*default_duration) #seconds
                segment_dwell_time /= 60 #minutes
                if segment_dwell_time >= 99.99:
                    segment_dwell_time = 99.98
                
                alpha = 1-lambdaK
                segment.dwell_time = old_dwell * alpha + segment_dwell_time * lambdaK
        data = network.get_attribute_values('TRANSIT_SEGMENT', ['dwell_time', 'transit_time_func'])
        self.Scenario.set_attribute_values('TRANSIT_SEGMENT', ['dwell_time', 'transit_time_func'], data)
        return network


    def _ComputeSegmentCosts(self, network):
        excessKM = 0.0
        for line in network.transit_lines():
            capacity = line.total_capacity
            for segment in line.segments():
                volume = segment.current_voltr = segment.voltr
                length = segment.link.length
                if volume >= capacity:
                    excess = volume-capacity
                    excessKM += excess*length
                segment.cost = self._CalculateSegmentCost(segment.voltr,capacity,segment)

        values = network.get_attribute_values('TRANSIT_SEGMENT', ['cost'])
        self.Scenario.set_attribute_values('TRANSIT_SEGMENT', ['data3'], values)
        return excessKM

    def _UpdateNetwork(self, network):
        attributeMapping = self._AttributeMapping()
        attributeMapping['TRANSIT_SEGMENT']['dwell_time'] = 'dwell_time'
        for type, mapping in attributeMapping.iteritems():
            attributes = mapping.keys()
            data = self.Scenario.get_attribute_values(type, attributes)
            network.set_attribute_values(type, attributes, data)
        return network

    def _FindStepSize(self, network, averageMinTripImpedence, averageImpedence, assignedTotalDemand):
        approx1 = 0.0
        approx2 = 0.5
        approx3 = 1.0
        grad1 = averageMinTripImpedence - averageImpedence
        grad2 = self._ComputeGradient(assignedTotalDemand, approx2, network)
        grad2 += averageMinTripImpedence - averageImpedence
        grad3 = self._ComputeGradient(assignedTotalDemand, approx3, network)
        grad3 += averageMinTripImpedence - averageImpedence
        for m_steps in range(0, 21):
            h1 = approx2 - approx1
            h2 = approx3 - approx2
            delta1 = (grad2 - grad1) / h1
            delta2 = (grad3 - grad2) / h2
            d = (delta2 - delta1) / (h1 + h2)
            b = h2 * d + delta2
            t1 = grad3 * d * 4
            t2 = b ** 2
            if t2 > t1:
                temp = math.sqrt(t2 - t1) 
            else:
                temp = 0.0
            if abs(b - temp) < abs(b + temp):
                temp = b + temp
            else:
                temp = b - temp
            if temp == 0.0:
                raise Exception("Congested transit assignment cannot be applied to this transit network, please use Capacitated transit assignment instead.")
            temp = -2 * grad3 / temp
            lambdaK = approx3 + temp
            temp = abs(temp) * 100000.0
            if temp < 100:
                break
            grad = self._ComputeGradient(assignedTotalDemand, lambdaK, network)
            grad += averageMinTripImpedence - averageImpedence
            approx1 = approx2
            approx2 = approx3
            approx3 = lambdaK
            grad1 = grad2
            grad2 = grad3
            grad3 = grad

        lambdaK = max(0.0, min(1.0, lambdaK))
        self.alphas = [ a * (1-lambdaK) for a in self.alphas ]
        self.alphas.append(lambdaK)
        return lambdaK

    def _UpdateVolumes(self, network, lambdaK):
        alpha = 1-lambdaK
        for node in network.regular_nodes():
                node.inboa = node.inboa * alpha + node.initial_boardings * lambdaK
                node.fiali = node.fiali * alpha + node.final_alightings * lambdaK
        for link in network.links():
            link.volax = link.volax * alpha + link.aux_transit_volume * lambdaK
        for line in network.transit_lines():
            capacity = float(line.total_capacity)
            congested = False
            for segment in line.segments():
                segment.voltr = segment.voltr * alpha + segment.transit_volume * lambdaK
                segment.board = segment.board * alpha + segment.transit_boardings * lambdaK
        return

    def _ComputeGaps(self, assignedTotalDemand, lambdaK, averageMinTripImpedence, previousAverageMinTripImpedence, network):
        cngap = previousAverageMinTripImpedence - averageMinTripImpedence
        netCosts = self._ComputeNetworkCosts(assignedTotalDemand, lambdaK, network)
        averageImpedence = lambdaK * averageMinTripImpedence + (1 - lambdaK) * previousAverageMinTripImpedence + netCosts
        crgap = cngap / averageImpedence
        normGapDifference = (self.NormGap - cngap) * 100000.0
        return (averageImpedence,cngap,crgap,normGapDifference, netCosts)



    def _SaveResults(self, network, stsu_att):
        if self.Scenario.extra_attribute('@ccost') is not None:
            ccost = self.Scenario.extra_attribute('@ccost')
            self.Scenario.delete_extra_attribute('@ccost')
            network.delete_attribute(ccost.type, '@ccost')
        type = 'TRANSIT_SEGMENT'
        congestionAttribute = self.Scenario.create_extra_attribute(type, '@ccost')
        congestionAttribute.description = 'congestion cost'
        network.create_attribute(type, '@ccost')
        for line in network.transit_lines():
            capacity = float(line.total_capacity)
            i = 0
            for segment in line.segments():
                volume = float(segment.voltr)
                congestionTerm = self._CalculateSegmentCost(volume, capacity, segment)
                baseTime = float(segment.uncongested_time) - float(line.segment(i+1).base_dwell_time)
                segment.transit_time = (baseTime+float(line.segment(i+1).dwell_time))*(1+congestionTerm)
                segment['@ccost'] = segment.transit_time - baseTime
                i += 1
        attributeMapping = self._AttributeMapping()
        attributeMapping['TRANSIT_SEGMENT']['@ccost'] = '@ccost'
        attributeMapping['TRANSIT_SEGMENT']['transit_time'] = 'transit_time'
        for type, mapping in attributeMapping.iteritems():
            data = network.get_attribute_values(type, mapping.values())
            self.Scenario.set_attribute_values(type, mapping.keys(), data)
        if self.SurfaceTransitSpeed != False:
            data = self.Scenario.get_attribute_values('TRANSIT_SEGMENT', ['transit_volume', 'transit_boardings'])
            network.set_attribute_values('TRANSIT_SEGMENT', ['transit_volume', 'transit_boardings'], data)
            _netEdit.createSegmentAlightingsAttribute(network)
            network = self._SurfaceTransitSpeedUpdate(network, 1, stsu_att, True)
            data = network.get_attribute_values('TRANSIT_SEGMENT', ['transit_boardings','transit_alightings'])
            self.Scenario.set_attribute_values('TRANSIT_SEGMENT', ['@boardings', '@alightings'], data)
        self.strategies.data['alphas'] = self.alphas
        self.strategies._save_config()

    def _GetBaseAssignmentSpec(self):
        farePerception = []
        baseSpec = []
        for i in range(0, len(self.DemandMatrixList)):
            
            if self.ClassFarePerceptionList[i] == 0.0:
                farePerception.append(0.0)
            else:
                farePerception.append( 60.0 / self.ClassFarePerceptionList[i])
            baseSpec.append({
                'modes': self.ClassModeList[i],
                'demand': self.DemandMatrixList[i].id,
                'waiting_time': {
                'headway_fraction': self.HeadwayFractionAttributeId,
                'effective_headways': self.EffectiveHeadwayAttributeId,
                'spread_factor': 1,
                'perception_factor': self.ClassWaitPerceptionList[i]},
                'boarding_time': {
                    'at_nodes': None,
                    'on_lines': {
                        'penalty': 'ut3',
                        'perception_factor': self.ClassBoardPerceptionList[i]}},
                'boarding_cost': {
                    'at_nodes': {
                        'penalty': 0,
                        'perception_factor': 1},
                    'on_lines': None},
            'in_vehicle_time': {
                'perception_factor': 'us2'},
            'in_vehicle_cost': {
                'penalty': self.SegmentFareAttributeIdList[i],
                'perception_factor': farePerception[i]},
            'aux_transit_time': {
                'perception_factor': self.WalkAttributeIdList[i]},
            'aux_transit_cost': {
                'penalty': self.LinkFareAttributeIdList[i],
                'perception_factor': farePerception[i]},
            'connector_to_connector_path_prohibition': None,
            'od_results': {
                'total_impedance': self.ImpedenceMatrices[i].id},
            'flow_distribution_between_lines': {
                'consider_total_impedance': self._considerTotalImpedance},
            'save_strategies': True,
            'type': 'EXTENDED_TRANSIT_ASSIGNMENT'})
        for i in range(0, len(baseSpec)):
            if self._useLogitConnectorChoice:
                '''baseSpec[i]['flow_distribution_at_origins'] = {'by_time_to_destination': {'logit': {'scale': self.xtmf_OriginDistributionLogitScale,
                                                      'truncation': self._connectorLogitTruncation}},
                 'by_fixed_proportions': None}'''
                baseSpec[i]['flow_distribution_at_origins'] = {'choices_at_origins': {
                    'choice_points':'ALL_ORIGINS', 
                    'choice_set': 'ALL_CONNECTORS',
                    'logit_parameters': {
                        'scale': self.xtmf_OriginDistributionLogitScale,
                        'truncation': self._connectorLogitTruncation}},
                 'fixed_proportions_on_connectors': None}
            if EMME_VERSION >= (4, 1):
                baseSpec[i]['performance_settings'] = {'number_of_processors': self.NumberOfProcessors}
                '''if self._useLogitAuxTrChoice:
                    raise NotImplementedError()'''
                if self.Scenario.extra_attribute("@node_logit") != None:
                    baseSpec[i]['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {'choices_at_regular_nodes': {'choice_points': '@node_logit',
                                                  'aux_transit_choice_set': 'ALL_POSSIBLE_LINKS',
                                                  'logit_parameters': {'scale': 0.2,
                                                                       'truncation': 0.05}}}
                else:
                    baseSpec[i]['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {
                        'choices_at_regular_nodes':'OPTIMAL_STRATEGY'
                        }
                modeList = []

                partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
                #if all modes are selected for class, get all transit modes for journey levels
                if self.ClassModeList[i] == ['*']:
                    for mode in partialNetwork.modes():
                        if mode.type == 'TRANSIT': 
                            modeList.append({"mode": mode.id, "next_journey_level": 1})
                else:
                    for modechar in self.ClassModeList[i]:
                        mode = partialNetwork.mode(modechar)
                        if mode.type == 'TRANSIT':
                            modeList.append({"mode": mode.id, "next_journey_level": 1})

                baseSpec[i]["journey_levels"] = [
                {
                    "description": "Walking",
                    "destinations_reachable": self.WalkAllWayFlag,
                    "transition_rules": modeList,
                    "boarding_time": None,
                    "boarding_cost": None,
                    "waiting_time": None
                },
                {
                    "description": "Transit",
                    "destinations_reachable": True,
                    "transition_rules": modeList,
                    "boarding_time": None,
                    "boarding_cost": None,
                    "waiting_time": None
                }
            ]
            
        return baseSpec
    def _GetBaseAssignmentSpecUncongested(self, index):
        if self.ClassFarePerceptionList[index] == 0.0:
                farePerception = 0.0
        else:
                farePerception = 60.0 / self.ClassFarePerceptionList[index]
        baseSpec = {
                'modes': self.ClassModeList[index],
                'demand': self.DemandMatrixList[index].id,
                'waiting_time': {
                'headway_fraction': self.HeadwayFractionAttributeId,
                'effective_headways': self.EffectiveHeadwayAttributeId,
                'spread_factor': 1,
                'perception_factor': self.ClassWaitPerceptionList[index]},
                'boarding_time': {
                    'at_nodes': None,
                    'on_lines': {
                        'penalty': 'ut3',
                        'perception_factor': self.ClassBoardPerceptionList[index]}},
                'boarding_cost': {
                    'at_nodes': {
                        'penalty': 0,
                        'perception_factor': 1},
                    'on_lines': None},
            'in_vehicle_time': {
                'perception_factor': 'us2'},
            'in_vehicle_cost': {
                'penalty': self.SegmentFareAttributeIdList[index],
                'perception_factor': farePerception},
            'aux_transit_time': {
                'perception_factor': self.WalkAttributeIdList[index]},
            'aux_transit_cost': {
                'penalty': self.LinkFareAttributeIdList[index],
                'perception_factor': farePerception},
            'connector_to_connector_path_prohibition': None,
            'od_results': {
                'total_impedance': self.ImpedenceMatrices[index].id},
            'flow_distribution_between_lines': {
                'consider_total_impedance': self._considerTotalImpedance},
            'save_strategies': True,
            'type': 'EXTENDED_TRANSIT_ASSIGNMENT'}
        if self._useLogitConnectorChoice:
            baseSpec['flow_distribution_at_origins'] = {'choices_at_origins': {
                    'choice_points':'ALL_ORIGINS', 
                    'choice_set': 'ALL_CONNECTORS',
                    'logit_parameters': {
                        'scale': self.xtmf_OriginDistributionLogitScale,
                        'truncation': self._connectorLogitTruncation}},
                 'fixed_proportions_on_connectors': None}
        if EMME_VERSION >= (4, 1):
            baseSpec['performance_settings'] = {'number_of_processors': self.NumberOfProcessors}
            '''if self._useLogitAuxTrChoice:
                raise NotImplementedError()'''
        if self.NodeLogitScale is not False:
            baseSpec['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {
                'choices_at_regular_nodes': {
                    'choice_points': 'ui1',
                    'aux_transit_choice_set': 'ALL_POSSIBLE_LINKS',
                    'logit_parameters': {
                        'scale': self.NodeLogitScale,
                        'truncation': self._connectorLogitTruncation}
                    }
                }
        else:
                baseSpec['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {
                    'choices_at_regular_nodes':'OPTIMAL_STRATEGY'
                    }
        if EMME_VERSION >= (4,2,1):
            modeList = []
            partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
            #if all modes are selected for class, get all transit modes for journey levels
            if self.ClassModeList[index] == ['*']:
                for mode in partialNetwork.modes():
                    if mode.type == 'TRANSIT': 
                        modeList.append({"mode": mode.id, "next_journey_level": 1})
            baseSpec["journey_levels"] = [
                    {
                        "description": "Walking",
                        "destinations_reachable": self.WalkAllWayFlag,
                        "transition_rules": modeList,
                        "boarding_time": None,
                        "boarding_cost": None,
                        "waiting_time": None
                    },
                    {
                        "description": "Transit",
                        "destinations_reachable": True,
                        "transition_rules": modeList,
                        "boarding_time": None,
                        "boarding_cost": None,
                        "waiting_time": None
                    }
            ]
        return baseSpec

    def _ExtractOutputMatrices(self):
        for i, demand in enumerate(self.DemandMatrixList):
            if self.WalkTimeMatrixList[i] or self.WaitTimeMatrixList[i] or self.PenaltyMatrixList[i]:
                self._ExtractTimesMatrices(i)
            if self.InVehicleTimeMatrixList[i] is not None:
                with _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_SEGMENT') as TempInVehicleTimesAttribute:
                    if self.CalculateCongestedIvttFlag == True:
                        self._ExtractInVehicleTimes(TempInVehicleTimesAttribute, True, i)
                    else:
                        self._ExtractInVehicleTimes(TempInVehicleTimesAttribute, False, i)
            if self.xtmf_congestedAssignment==True:
                if self.CongestionMatrixList[i] is not None:
                    self._ExtractCongestionMatrix(self.CongestionMatrixList[i], i)
            '''if self.xtmf_congestedAssignment==True:
                if not self.CongestionMatrixList[i] and self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag:

                    def congestionMatrixManager():
                        return _util.tempMatrixMANAGER()

                else:

                    @contextmanager
                    def congestionMatrixManager():
                        try:
                            yield _bank.matrix(self.CongestionMatrixList[i])
                        finally:
                            pass

            
                if self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag or self.CongestionMatrixList[i]:
                    with congestionMatrixManager() as congestionMatrix:
                        self._ExtractCongestionMatrix(congestionMatrix.id, i)
                    if self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag:
                        self._FixRawIVTT(congestionMatrix.id, i)'''
            if self.FareMatrixList[i]:
                self._ExtractCostMatrix(i)

    ################################# SUB TASK METHODS ###########################


    def _ParsePerceptionString(self, index):
        perceptionList = []
        zoneValues = self.WalkPerceptionList[index].splitlines()
        for zoneValue in zoneValues:
            if zoneValue.isspace():
                continue
            parts = zoneValue.split(':')
            if len(parts) < 2:
                msg = 'Error parsing perception string'
                msg += '. [%s]' % zoneValue
                raise SyntaxError(msg)
            strippedParts = [ item.strip() for item in parts ]
            try:
                perception = float(strippedParts[0])
            except:
                msg = 'Perception value must be a number'
                msg += '. [%s]' % zoneValue
                raise SyntaxError(msg)

            try:
                zone = str(strippedParts[1])
            except:
                msg = 'Filter value must be a string'
                msg += '. [%s]' % zoneValue
                raise SyntaxError(msg)

            perceptionList.append(strippedParts[0:2])
        return perceptionList

    def _ParseExponentString(self):
        exponentList = {}
        components = self.CongestionExponentString.split(',')
        for component in components:
            if component.isspace():
                continue
            parts = component.split(':')
            if len(parts) !=3 :
                msg = 'Error parsing penalty and filter string: Separate ttf, perception and exponent with colons ttf:perception:exponent'
                msg += '. [%s]' % component
                raise SyntaxError(msg)
            strippedParts = [ item.strip() for item in parts ]
            try:
                ttf = int(strippedParts[0])
            except:
                msg = 'ttf value must be an integer'
                msg += '. [%s]' % component
                raise SyntaxError(msg)

            try:
                perception = float(strippedParts[1])
            except:
                msg = 'Perception value must be a number'
                msg += '. [%s]' % component
                raise SyntaxError(msg)

            try:
                exponent = float(strippedParts[2])
            except:
                msg = 'Exponent value must be a number'
                msg += '. [%s]' % component
                raise SyntaxError(msg)
            strippedParts[0] = int(strippedParts[0])
            strippedParts[1] = float(strippedParts[1])
            strippedParts[2] = float(strippedParts[2])
            exponentList[strippedParts[0]] = strippedParts[0:3]
        return exponentList

    def _GetFuncSpec(self):
        parameterList = self._ParseExponentString()
        partialSpec = 'import math \ndef calc_segment_cost(transit_volume, capacity, segment):\n    cap_period = '+str(self.AssignmentPeriod)
        i = 0
        for ttf, item in parameterList.iteritems():
            ttf = str(ttf)
            alpha = float(item[2])
            beta = (2 * alpha - 1) / (2 * alpha - 2)
            alphaSquare = alpha ** 2
            betaSquare = beta ** 2
            if i == 0:
                partialSpec += '\n    if segment.transit_time_func == ' + ttf + ': \n        return max(0,(' + str(item[1]) + ' * (1 + math.sqrt(' + str(alphaSquare) + ' * \n            (1 - transit_volume / capacity) ** 2 + ' + str(betaSquare) + ') - ' + str(alpha) + ' \n            * (1 - transit_volume / capacity) - ' + str(beta) + ')))'
            else:
                partialSpec += '\n    elif segment.transit_time_func == ' + ttf + ': \n        return max(0,(' + str(item[1]) + ' * (1 + math.sqrt(' + str(alphaSquare) + ' *  \n            (1 - transit_volume / capacity) ** 2 + ' + str(betaSquare) + ') - ' + str(alpha) + ' \n            * (1 - transit_volume / capacity) - ' + str(beta) + ')))'
            i += 1
        partialSpec += '\n    else: \n        raise Exception("ttf=%s congestion values not defined in input" %segment.transit_time_func)'
        funcSpec = {'type': 'CUSTOM',
         'assignment_period': self.AssignmentPeriod,
         'orig_func': False,
         'congestion_attribute': 'us3',
         'python_function': partialSpec}
        return funcSpec

    def _SetUpLineAttributes(self, stsu_att):
        models = []
        for i, model in enumerate(self.SurfaceTransitSpeed):
            models.append({})
            model = model.split(":")
            models[i]['boarding_duration'] = float(model[0])
            models[i]['alighting_duration']  = float(model[1])
            models[i]['default_duration'] = float(model[2])
            models[i]['correlation'] = float(model[3])
            models[i]['mode_filter'] = str(model[4]).strip(" ")
            models[i]['line_filter'] = str(model[5]).strip(" ")
            models[i]['erow_speed'] = float(model[6])
            spec = {
                "type":"NETWORK_CALCULATION",
                "result": str(stsu_att.id),
                "expression": str(i+1),
                "selections": {
                    "transit_line": "mode = " + models[i]['mode_filter']
                }
            }
            if models[i]['line_filter'] == "" and models[i]['mode_filter'] != "":
                spec["selections"]["transit_line"] = "mode = " + models[i]['mode_filter']
            elif  models[i]['line_filter'] != "" and models[i]['mode_filter'] != "":
                spec["selections"]["transit_line"] = models[i]['line_filter'] + " and mode = " + models[i]['mode_filter']
            elif models[i]['line_filter'] != "" and models[i]['mode_filter'] == "":
                spec["selections"]["transit_line"] = models[i]['line_filter']
            elif models[i]['line_filter'] == "" and models[i]['mode_filter'] == "":
                spec["selections"]["transit_line"] = "all"
            else:
                raise Exception("Please enter a correct mode filter and/or line filter in Surface Transit Speed Module %d" %(i+1))
            report = networkCalcTool(spec, scenario = self.Scenario)
        return models



    def _CalculateSegmentCost(self, transit_volume, capacity, segment):
        ttf = segment.transit_time_func
        entry = self.ttfDict[ttf]
        alpha = entry[2]
        beta = (2 * alpha - 1) / (2 * alpha - 2)
        alphaSquare = alpha ** 2
        betaSquare = beta ** 2
        cost = entry[1] * (1 + math.sqrt(alphaSquare * (1 - transit_volume / capacity) ** 2 + betaSquare) - alpha * (1 - transit_volume / capacity) - beta)
        return max(0,cost)

    def _GetStopSpec(self):
        stopSpec = {'max_iterations': self.Iterations,
         'normalized_gap': self.NormGap,
         'relative_gap': self.RelGap}
        return stopSpec

    def _ComputeGradient(self, assignedTotalDemand, lambdaK, network):
        value = 0.0
        for line in network.transit_lines():
            capacity = float(line.total_capacity)
            for segment in line.segments():
                assignedVolume = float(segment.current_voltr)
                cumulativeVolume = float(segment.transit_volume)
                t0 = (segment.transit_time - segment.dwell_time) / (1 + segment.cost)
                volumeDifference = cumulativeVolume - assignedVolume
                if lambdaK == 1:
                    adjustedVolume = cumulativeVolume
                else:
                    adjustedVolume = assignedVolume + lambdaK * (cumulativeVolume - assignedVolume)
                costDifference = self._CalculateSegmentCost(adjustedVolume, capacity, segment) - self._CalculateSegmentCost(assignedVolume, capacity, segment)
                value += t0 * costDifference * volumeDifference
        return value / assignedTotalDemand

    def _ComputeNetworkCosts(self, assignedTotalDemand, lambdaK, network):
        value = 0.0
        for line in network.transit_lines():
            capacity = float(line.total_capacity)
            for segment in line.segments():
                assignedVolume = segment.current_voltr
                cumulativeVolume = segment.transit_volume
                t0 = (segment.transit_time - segment.dwell_time) / (1 + segment.cost)
                volumeDifference = assignedVolume + lambdaK * (cumulativeVolume - assignedVolume)
                adjustedVolume = assignedVolume + lambdaK * (cumulativeVolume - assignedVolume)
                costDifference = self._CalculateSegmentCost(adjustedVolume, capacity, segment) - self._CalculateSegmentCost(assignedVolume, capacity, segment)
                value += t0 * costDifference * volumeDifference
        return value / assignedTotalDemand

    def _ExtractTimesMatrices(self, i):
        spec = {'by_mode_subset': {'modes': ['*'],
                            'actual_aux_transit_times': self.WalkTimeMatrixList[i],
                            'actual_total_boarding_times': self.PenaltyMatrixList[i]},
         'type': 'EXTENDED_TRANSIT_MATRIX_RESULTS',
         'actual_total_waiting_times': self.WaitTimeMatrixList[i]}
        self.TRACKER.runTool(matrixResultsTool, spec, scenario=self.Scenario, class_name=self.ClassNames[i])

    def _ExtractCostMatrix(self, i):
        spec = {'trip_components': {
                    'boarding': None,
                    'in_vehicle': self.SegmentFareAttributeIdList[i],
                    'aux_transit': self.LinkFareAttributeIdList[i],
                    'alighting': None},
                'sub_path_combination_operator': '+',
                'sub_strategy_combination_operator': 'average',
                'selected_demand_and_transit_volumes': {
                    'sub_strategies_to_retain': 'ALL',
                    'selection_threshold': {
                        'lower': -999999,
                        'upper': 999999}},
                'analyzed_demand': self.DemandMatrixList[i].id,
                'constraint': None,
                'results': {
                    'strategy_values': self.FareMatrixList[i],
                    'selected_demand': None,
                    'transit_volumes': None,
                    'aux_transit_volumes': None,
                    'total_boardings': None,
                    'total_alightings': None},
                'type': 'EXTENDED_TRANSIT_STRATEGY_ANALYSIS'}
        if EMME_VERSION >= (4,3,2):
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario=self.Scenario, class_name=self.ClassNames[i], num_processors=self.NumberOfProcessors)
        else:
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario, class_name=self.ClassNames[i])
            
    def _ExtractInVehicleTimes(self, attribute, congested, i):
        if congested == True or self.xtmf_congestedAssignment == False:
            spec = {
                    "result": str(attribute.id),
                    "expression": "timtr",
                    "aggregation": None,
                    "selections": {
                        "link": "all",
                        "transit_line": "all"
                    },
                    "type": "NETWORK_CALCULATION"
                }
            self.TRACKER.runTool(networkCalcTool, spec, scenario=self.Scenario)
        else:
            spec = {
                    "result": str(attribute.id),
                    "expression": "timtr-@ccost",
                    "aggregation": None,
                    "selections": {
                        "link": "all",
                        "transit_line": "all"
                    },
                    "type": "NETWORK_CALCULATION"
                }
            self.TRACKER.runTool(networkCalcTool, spec, scenario=self.Scenario)
        spec = {'trip_components': {'boarding': None,
                             'in_vehicle': str(attribute.id),
                             'aux_transit': None,
                             'alighting': None},
         'sub_path_combination_operator': '+',
         'sub_strategy_combination_operator': 'average',
         'selected_demand_and_transit_volumes': {'sub_strategies_to_retain': 'ALL',
                                                 'selection_threshold': {'lower': -999999,
                                                                         'upper': 999999}},
         'analyzed_demand': self.DemandMatrixList[i].id,
         'constraint': None,
         'results': {'strategy_values': self.InVehicleTimeMatrixList[i],
                     'selected_demand': None,
                     'transit_volumes': None,
                     'aux_transit_volumes': None,
                     'total_boardings': None,
                     'total_alightings': None},
         'type': 'EXTENDED_TRANSIT_STRATEGY_ANALYSIS'}
        if EMME_VERSION >= (4,3,2):
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario=self.Scenario, class_name=self.ClassNames[i], num_processors=self.NumberOfProcessors)
        else:
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario, class_name=self.ClassNames[i])        

    def _ExtractCongestionMatrix(self, congestionMatrixId, i):
        spec = {'trip_components': {'boarding': None,
                             'in_vehicle': '@ccost',
                             'aux_transit': None,
                             'alighting': None},
         'sub_path_combination_operator': '+',
         'sub_strategy_combination_operator': 'average',
         'selected_demand_and_transit_volumes': {'sub_strategies_to_retain': 'ALL',
                                                 'selection_threshold': {'lower': -999999,
                                                                         'upper': 999999}},
         'analyzed_demand': self.DemandMatrixList[i].id,
         'constraint': None,
         'results': {'strategy_values': congestionMatrixId,
                     'selected_demand': None,
                     'transit_volumes': None,
                     'aux_transit_volumes': None,
                     'total_boardings': None,
                     'total_alightings': None},
         'type': 'EXTENDED_TRANSIT_STRATEGY_ANALYSIS'}
        if EMME_VERSION >= (4,3,2):
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario=self.Scenario, class_name=self.ClassNames[i], num_processors=self.NumberOfProcessors)
        else:
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario, class_name=self.ClassNames[i])

    def _FixRawIVTT(self, congestionMatrix, i):
        expression = '{mfivtt} - {mfcong}'.format(mfivtt=self.InVehicleTimeMatrixList[i], mfcong=congestionMatrix)
        matrixCalcSpec = {'expression': expression,
         'result': self.InVehicleTimeMatrixList[i],
         'constraint': {'by_value': None,
                        'by_zone': None},
         'aggregation': {'origins': None,
                         'destinations': None},
         'type': 'MATRIX_CALCULATION'}
        matrixCalcTool(matrixCalcSpec, scenario=self.Scenario)

    def short_description(self):
        return 'MultiClass transit assignment tool for GTAModel V4'

    def _AttributeMapping(self):
        atts = {
            'NODE': {
                'initial_boardings': 'inboa',
                'final_alightings': 'fiali'
                },
            'LINK': {
                'aux_transit_volume': 'volax'
                },
            'TRANSIT_SEGMENT': {
                'transit_time': 'timtr',
                'transit_volume': 'voltr',
                'transit_boardings': 'board'
                }
            }
        return atts

    @contextmanager
    def _getImpendenceMatrices(self):
        self.ImpedenceMatrices = []
        created = {}
        for i in range(0,len(self.DemandMatrixList)):
            matrixCreated = False
            if self.ImpedanceMatrixList[i] == None:
                matrixCreated = True
                _m.logbook_write("Creating temporary Impendence Matrix for class %s" %self.ClassNames[i])
                mtx = _util.initializeMatrix(default=0.0, description= 'Temporary Impedence for class %s' %self.ClassNames[i], \
                           matrix_type='FULL')
                self.ImpedenceMatrices.append(mtx)
            else:
                mtx = _bank.matrix(self.ImpedanceMatrixList[i])
                self.ImpedenceMatrices.append(mtx)
            created[mtx.id] = matrixCreated
        try:
            yield self.ImpedenceMatrices
        finally:
            for key in created:
                if created[key] == True:
                    _bank.delete_matrix(key)

    @contextmanager
    def _tempStsuTTFs(self):
        self.orig_ttf_values = self.Scenario.get_attribute_values('TRANSIT_SEGMENT',['transit_time_func'])
        self.ttfs_changed = False
        self.stsu_ttf_map = {}
        ttfs = self._ParseExponentString()
        self.stsu_ttf_map = {}
        created = {}
        for ttf, items in ttfs.iteritems():
            for i in range(1,100):
                func = "ft"+str(i)
                if self.Scenario.emmebank.function(func) is None:
                    self.Scenario.emmebank.create_function(func, "(length*60/us1)")
                    self.stsu_ttf_map[int(ttf)] = int(func[2:])
                    if ttf in self.ttfs_xrow:
                        self.ttfs_xrow.add(int(func[2:]))
                    self.CongestionExponentString = self.CongestionExponentString+",%s:%s:%s" %(str(func[2:]),str(items[1]), str(items[2]))
                    #self.stsu_ttf = func
                    created[func] = True
                    break
        try:
            yield self.stsu_ttf_map
        finally:
            for func in created:
                if created[func] == True:
                    self.Scenario.emmebank.delete_function(func)
            if self.ttfs_changed == True:
                self.Scenario.set_attribute_values('TRANSIT_SEGMENT',['transit_time_func'], self.orig_ttf_values)

    @_m.method(return_type=unicode)
    def get_scenario_node_attributes(self):
        options = ["<option value='-1'>None</option>"]
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'NODE':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=unicode)
    def get_scenario_link_attributes(self, include_none = True):
        options = []
        if include_none:
            options.append("<option value='-1'>None</option>")
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'LINK':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=unicode)
    def get_scenario_segment_attribtues(self):
        options = []
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'TRANSIT_SEGMENT':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg