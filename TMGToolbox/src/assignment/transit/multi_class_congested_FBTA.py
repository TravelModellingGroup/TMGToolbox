#Embedded file name: C:/Users/Monika/Documents/Visual Studio 2013/Projects/PythonApplication1/PythonApplication1/PythonApplication1.py
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
from contextlib import contextmanager
from multiprocessing import cpu_count
from re import split as _regex_split
import inro.modeller as _m
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
congestedAssignmentTool = _MODELLER.tool('inro.emme.transit_assignment.congested_transit_assignment')
extendedAssignmentTool =_MODELLER.tool('inro.emme.transit_assignment.extended_transit_assignment')
networkCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
matrixResultsTool = _MODELLER.tool('inro.emme.transit_assignment.extended.matrix_results')
strategyAnalysisTool = _MODELLER.tool('inro.emme.transit_assignment.extended.strategy_based_analysis')
matrixCalcTool = _MODELLER.tool('inro.emme.matrix_calculation.matrix_calculator')
NullPointerException = _util.NullPointerException
EMME_VERSION = _util.getEmmeVersion(tuple)
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

class MultiClassTransitAssignment(_m.Tool()):
    version = '1.0.0'
    tool_run_msg = ''
    number_of_tasks = 7

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

    xtmf_OriginDistributionLogitScale = _m.Attribute(float)
    xtmf_WalkDistributionLogitScale = _m.Attribute(float)


    if EMME_VERSION >= (4, 1):
        NumberOfProcessors = _m.Attribute(int)

    def __init__(self):
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)
        self.Scenario = _MODELLER.scenario
        self.DemandMatrixList = [_MODELLER.emmebank.matrix('mf91')]
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
            nest = (manager1, manager2, manager3)
            (headwayAttribute, walkAttribute, effectiveHeadwayAttribute) = nest
            with headwayAttribute, walkAttribute, effectiveHeadwayAttribute:
                headwayAttribute.initialize(0.5)
                walkAttribute.initialize(1.0)
                effectiveHeadwayAttribute.initialize(0.0)
                self.HeadwayFractionAttributeId = headwayAttribute.id
                self.WalkAttributeIdList = walkAttribute.id
                self.EffectiveHeadwayAttributeId = effectiveHeadwayAttribute.id
                self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc())
            raise 

        self.tool_run_msg = _m.PageBuilder.format_info('Done.')

    def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixString, xtmf_NameString,\
        WalkSpeed, xtmf_WalkPerceptionString, xtmf_WalkPerceptionAttributeIdString, \
        xtmf_ClassWaitPerceptionString, xtmf_ClassBoardPerceptionString, xtmf_ClassFarePerceptionString, xtmf_ClassModeList,\
        HeadwayFractionAttributeId, xtmf_LinkFareAttributeIdString, xtmf_SegmentFareAttributeIdString, \
        EffectiveHeadwayAttributeId, EffectiveHeadwaySlope,  AssignmentPeriod, \
        Iterations, NormGap, RelGap, \
        xtmf_InVehicleTimeMatrixString, xtmf_WaitTimeMatrixString, xtmf_WalkTimeMatrixString, xtmf_FareMatrixString, xtmf_CongestionMatrixString, xtmf_PenaltyMatrixString, xtmf_ImpedanceMatrixString, \
        xtmf_OriginDistributionLogitScale, CalculateCongestedIvttFlag, CongestionExponentString, xtmf_congestedAssignment):
        
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
        
        #class-specific inputs
        self.ClassWaitPerceptionList = [float (x) for x in xtmf_ClassWaitPerceptionString.split(',')]
        self.ClassBoardPerceptionList = [float (x) for x  in xtmf_ClassBoardPerceptionString.split(',')]
        self.ClassFarePerceptionList = [float(x) for x in xtmf_ClassFarePerceptionString.split(',')]
        

        self.LinkFareAttributeIdList = xtmf_LinkFareAttributeIdString.split(',')
        self.SegmentFareAttributeIdList = xtmf_SegmentFareAttributeIdString.split(',')


        if xtmf_WalkPerceptionString is not None:
            xtmf_WalkPerceptionString = xtmf_WalkPerceptionString.replace('::', '\n')
            self.WalkPerceptionList = xtmf_WalkPerceptionString.split(';')
        if xtmf_WalkPerceptionAttributeIdString is not None:
            self.WalkAttributeIdList = xtmf_WalkPerceptionAttributeIdString.split(',')

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if self.Scenario is None:
            raise Exception('Scenario %s was not found!' % xtmf_ScenarioNumber)

        aux_mode_chars = ''
        for mode in self.Scenario.modes():
            if mode.type == 'AUX_TRANSIT':
                aux_mode_chars += mode.id   

        self.ClassModeList = [["*"] if  "*" in x else list(set(x + aux_mode_chars) ) for x in xtmf_ClassModeList.split(',')]

        self.DemandMatrixList = []
        for demandMatrix in xtmf_DemandMatrixString.split(','):
            if _MODELLER.emmebank.matrix(demandMatrix) is None:
                raise Exception('Matrix %s was not found!' % demandMatrix)
            else:
                self.DemandMatrixList.append(_MODELLER.emmebank.matrix(demandMatrix))

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
        print('Running Multi-Class Transit Assignment')
        self._Execute()
        print('Done running transit assignment')

    def _Execute(self):
        with _m.logbook_trace(name='{classname} v{version}'.format(classname=self.__class__.__name__, version=self.version), attributes=self._GetAtts()):
            with _m.logbook_trace('Checking travel time functions'):
                changes = self._HealTravelTimeFunctions()
                if changes == 0:
                    _m.logbook_write('No problems were found')
            self._ChangeWalkSpeed()
            #self.ClassNames = []
            for i in range(0, len(self.DemandMatrixList)):
                #self.ClassNames.append(str(self.DemandMatrixList[i].name))
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

            with _util.tempMatrixMANAGER('Temp impedances') as impedanceMatrix:
                self.TRACKER.startProcess(3)
                self._AssignHeadwayFraction()
                self.TRACKER.completeSubtask()
                self._AssignEffectiveHeadway()
                self.TRACKER.completeSubtask()
                for i in range(0, len(self.ClassNames)):
                    WalkPerceptionArray = self._ParsePerceptionString(i)
                    self._AssignWalkPerception(WalkPerceptionArray, self.WalkAttributeIdList[i])

                self.TRACKER.completeSubtask()
                spec = self._GetBaseAssignmentSpec()

                if self.xtmf_congestedAssignment==True:
                    self.TRACKER.runTool(congestedAssignmentTool, transit_assignment_spec=spec, congestion_function=self._GetFuncSpec(), stopping_criteria=self._GetStopSpec(), class_names=self.ClassNames, scenario=self.Scenario)
                else:
                    for i in range(0, len(self.ClassNames)):
                        specUncongested = self._GetBaseAssignmentSpecUncongested(i)
                        self.TRACKER.runTool(extendedAssignmentTool, specification=specUncongested, class_name=self.ClassNames[i], scenario=self.Scenario, add_volumes=(i!=0))
                self._ExtractOutputMatrices()

    def _GetAtts(self):
        atts = {'Scenario': '%s - %s' % (self.Scenario, self.Scenario.title),
         'Version': self.version,
         'Wait Perception': self.ClassWaitPerceptionList,
         'Fare Perception': self.ClassFarePerceptionList,
         'Assignment Period': self.AssignmentPeriod,
         'Boarding Perception': self.ClassBoardPerceptionList,
         'Iterations': self.Iterations,
         'Normalized Gap': self.NormGap,
         'Relative Gap': self.RelGap,
         'self': self.__MODELLER_NAMESPACE__}
        return atts

    def _HealTravelTimeFunctions(self):
        changes = 0
        for function in _MODELLER.emmebank.functions():
            if function.type != 'TRANSIT_TIME':
                continue
            cleanedExpression = function.expression.replace(' ', '')
            if 'us3' in cleanedExpression:
                if cleanedExpression.endswith('*(1+us3)'):
                    index = cleanedExpression.find('*(1+us3)')
                    newExpression = cleanedExpression[:index][1:-1]
                    function.expression = newExpression
                    print('Detected function %s with existing congestion term.' % function)
                    print("Original expression= '%s'" % cleanedExpression)
                    print("Healed expression= '%s'" % newExpression)
                    print('')
                    _m.logbook_write('Detected function %s with existing congestion term.' % function)
                    _m.logbook_write("Original expression= '%s'" % cleanedExpression)
                    _m.logbook_write("Healed expression= '%s'" % newExpression)
                    changes += 1
                else:
                    raise Exception('Function %s already uses US3, which is reserved for transit' % function + ' segment congestion values. Please modify the expression ' + 'to use different attributes.')

        return changes

    def _ChangeWalkSpeed(self):
        with _m.logbook_trace('Setting walk speeds to %s' % self.WalkSpeed):
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
        exponentList = []
        components = _regex_split('\n|,', self.CongestionExponentString)
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

            exponentList.append(strippedParts[0:3])

        return exponentList

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

        with _m.logbook_trace('Assigning perception factors'):
            for i in range(0, len(perceptionArray)):
                applySelection(perceptionArray[i][0], perceptionArray[i][1])

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
                'total_impedance': self.ImpedanceMatrixList[i]},
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
                    "destinations_reachable": False,
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
                'total_impedance': self.ImpedanceMatrixList[index]},
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
            if self.Scenario.extra_attribute("@node_logit") is not None:
                baseSpec['flow_distribution_at_regular_nodes_with_aux_transit_choices'] = {'choices_at_regular_nodes': {'choice_points': '@node_logit',
                                                  'aux_transit_choice_set': 'ALL_POSSIBLE_LINKS',
                                                  'logit_parameters': {'scale': 0.2,
                                                                       'truncation': 0.05}}}
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
                        "destinations_reachable": False,
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
    def _GetFuncSpec(self):
        parameterList = self._ParseExponentString()
        partialSpec = 'import math \ndef calc_segment_cost(transit_volume, capacity, segment): '
        for count, item in enumerate(parameterList):
            alpha = float(item[2])
            beta = (2 * alpha - 1) / (2 * alpha - 2)
            alphaSquare = alpha ** 2
            betaSquare = beta ** 2
            if count == 0:
                partialSpec += '\n    if segment.transit_time_func == ' + item[0] + ': \n        return (' + item[1] + ' * (1 + math.sqrt(' + str(alphaSquare) + ' * \n            (1 - transit_volume / capacity) ** 2 + ' + str(betaSquare) + ') - ' + str(alpha) + ' \n            * (1 - transit_volume / capacity) - ' + str(beta) + '))'
            else:
                partialSpec += '\n    elif segment.transit_time_func == ' + item[0] + ': \n        return (' + item[1] + ' * (1 + math.sqrt(' + str(alphaSquare) + ' *  \n            (1 - transit_volume / capacity) ** 2 + ' + str(betaSquare) + ') - ' + str(alpha) + ' \n            * (1 - transit_volume / capacity) - ' + str(beta) + '))'

        partialSpec += '\n    else: \n        raise Exception("ttf=%s congestion values not defined in input" %segment.transit_time_func)'
        funcSpec = {'type': 'CUSTOM',
         'assignment_period': self.AssignmentPeriod,
         'orig_func': False,
         'congestion_attribute': 'us3',
         'python_function': partialSpec}
        return funcSpec

    def _GetStopSpec(self):
        stopSpec = {'max_iterations': self.Iterations,
         'normalized_gap': self.NormGap,
         'relative_gap': self.RelGap}
        return stopSpec

    def _ExtractOutputMatrices(self):
        for i, demand in enumerate(self.DemandMatrixList):
            if self.InVehicleTimeMatrixList[i] or self.WalkTimeMatrixList[i] or self.WaitTimeMatrixList[i] or self.PenaltyMatrixList[i]:
                self._ExtractTimesMatrices(i)
            if not self.CongestionMatrixList[i] and self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag:

                def congestionMatrixManager():
                    return _util.tempMatrixMANAGER()

            else:

                @contextmanager
                def congestionMatrixManager():
                    try:
                        yield _MODELLER.emmebank.matrix(self.CongestionMatrixList[i])
                    finally:
                        pass

            if self.xtmf_congestedAssignment==True:
                if self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag or self.CongestionMatrixList[i]:
                    with congestionMatrixManager() as congestionMatrix:
                        self._ExtractCongestionMatrix(congestionMatrix.id, i)
                    if self.InVehicleTimeMatrixList[i] and not self.CalculateCongestedIvttFlag:
                        self._FixRawIVTT(congestionMatrix.id, i)
            if self.FareMatrixList[i]:
                self._ExtractCostMatrix(i)

    def _ExtractTimesMatrices(self, i):
        spec = {'by_mode_subset': {'modes': ['*'],
                            'actual_in_vehicle_times': self.InVehicleTimeMatrixList[i],
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

    @_m.method(return_type=six.u)
    def get_scenario_node_attributes(self):
        options = ["<option value='-1'>None</option>"]
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'NODE':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=six.u)
    def get_scenario_link_attributes(self, include_none = True):
        options = []
        if include_none:
            options.append("<option value='-1'>None</option>")
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'LINK':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=six.u)
    def get_scenario_segment_attribtues(self):
        options = []
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'TRANSIT_SEGMENT':
                options.append('<option value="%s">%s - %s</option>' % (exatt.id, exatt.id, exatt.description))

        return '\n'.join(options)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg