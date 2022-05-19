#---LICENSE----------------------
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
V4 Transit Assignment

    Authors: pkucirek

    Latest revision by: mattaustin222
    
    
    Transit Assignment Tool created for GTAModel Version 4.0
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-02-04 by pkucirek
    
    0.0.2 Added a temporary impedance matrix for compatibility with Emme 4.0.8
    
    0.0.3 Added distributed walk time perception attribute; removed singular
            walk perception parameter. Also adds a new parameter to temporarily
            increase the capacity of streetcars by a specified factor.
    
    0.0.4 Removed the "Station & Transfer Perception" parameter. Walk perception
            on station centroid connectors will be set to 0, while transfer link
            walk perception will take the value of the region it is in (Toronto
            or Non-Toronto).
    
    2.0.0 Branched to create a FBTA procedure
    
    2.1.0 Added new parameters:
        - Toronto Connector Walk Perception
        - Non-Toronto Connector Walk Perception
    
    2.2.0 New features: save standard output matrices
    
    2.2.1 Exposed some private parameters (e.g. logit scale param for distribution
            among origin connectors). Added the private option to use logit
            distribution among auxiliary transit links at stops.
    
    2.2.2 Tool now initializes the output matrices before running the analyses.
    
    2.3.0 Added new feature to add the congestion term to the IVTT output matrix.
    
    2.3.1 Added new feature to try to heal the travel time functions, which can be
            left in an inappropriate state if Python is exited before finishing the
            assignment.
            
    2.3.2 Added in re-calibrated default parameter values
    
    2.4.0 Major bug fix: By default, IVTT already includes the congestion term. Prior
            versions produce a 'double counted' matrix of IVTT + 2C instead of the 
            intended IVTT + C. The tool now subtracts the congestion matrix to produce
            'raw' times.
    
    3.0.0 Changed to use CONICAL delay function
    
    3.1.0 Added walking perception for PD1 (links with type 101).
    
    3.2.0 Added estimable congestion exponent term (not yet available from Modeller)
    
    3.3.0 Changed to apply a 1.0 walking perception to subway-to-subway links.
    
    3.4.0 Added new feature to optionally export congestion matrix.

    3.4.1 Fixed bug causing congestion matrix number to not be passed in from XTMF.

    3.5.0 Removed all mention of GO Transit. Now applying a global 0.5 headway fraction 
            and using a global function to apply effective headways, resulting in
            an equivalent wait time of applying a 0.5 fraction up to 15 minute
            headways and a 0.2 fraction for all additional headway beyond 15 minutes.

    3.5.1 Added new feature to optionally export boarding penalty matrix.

    4.0.0 Changed to use custom congestion functions. Allows for different conical
        weights and exponents based on ttf value of segment. Tool no longer available
        for < 4.1.5
    
    4.0.1 Congestion function will now raise an Exception if a used ttf value is
        not assigned congestion parameters.

    4.0.2 Updated to allow for multi-threaded matrix calcs in 4.2.1+

    5.0.0 Forked

'''
import traceback as _traceback
from contextlib import contextmanager
from multiprocessing import cpu_count
from re import split as _regex_split

import inro.modeller as _m

_MODELLER = _m.Modeller() #Instantiate Modeller once.

_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

congestedAssignmentTool = _MODELLER.tool('inro.emme.transit_assignment.congested_transit_assignment')
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

##########################################################################################################

@contextmanager
def blankManager(obj):
    try:
        yield obj
    finally:
        pass

####

class V4_FareBaseTransitAssignment(_m.Tool()):
    
    version = '5.0.0'
    tool_run_msg = ""
    number_of_tasks = 7 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    DemandMatrix = _m.Attribute(_m.InstanceType)
    xtmf_DemandMatrixNumber = _m.Attribute(int)
    RunTitle = _m.Attribute(str)
    
    WalkAttributeId = _m.Attribute(str)
    HeadwayFractionAttributeId = _m.Attribute(str)
    EffectiveHeadwayAttributeId = _m.Attribute(str)
    LinkFareAttributeId = _m.Attribute(str)
    SegmentFareAttributeId = _m.Attribute(str)
    
    InVehicleTimeMatrixId = _m.Attribute(str)
    WaitTimeMatrixId = _m.Attribute(str)
    WalkTimeMatrixId = _m.Attribute(str)
    FareMatrixId = _m.Attribute(str)
    CongestionMatrixId = _m.Attribute(str)
    PenaltyMatrixId = _m.Attribute(str)
    ImpedanceMatrixId = _m.Attribute(str)
    DistanceMatrixId = _m.Attribute(str)
    
    xtmf_InVehicleTimeMatrixNumber = _m.Attribute(int)
    xtmf_WaitTimeMatrixNumber = _m.Attribute(int)
    xtmf_WalkTimeMatrixNumber = _m.Attribute(int)
    xtmf_FareMatrixNumber = _m.Attribute(int)
    xtmf_CongestionMatrixNumber = _m.Attribute(int)
    xtmf_PenaltyMatrixNumber = _m.Attribute(int)
    xtmf_ImpedanceMatrixNumber = _m.Attribute(int)
    xtmf_DistanceMatrixNumber = _m.Attribute(int)
    
    CalculateCongestedIvttFlag = _m.Attribute(bool)
    UseBoardingLevelFlag = _m.Attribute(bool) 
    
    WalkSpeed = _m.Attribute(float)
    WalkPerceptionToronto = _m.Attribute(float)
    WalkPerceptionNonToronto = _m.Attribute(float)
    WalkPerceptionTorontoConnectors = _m.Attribute(float)
    WalkPerceptionNonTorontoConnectors = _m.Attribute(float)
    WalkPerceptionPD1 = _m.Attribute(float)
    
    CongestionExponentString = _m.Attribute(str)

    EffectiveHeadwaySlope = _m.Attribute(float)
    
    WaitPerception = _m.Attribute(float)
    BoardPerception = _m.Attribute(float)
    FarePerception = _m.Attribute(float)
    AssignmentPeriod = _m.Attribute(float)
    
    xtmf_OriginDistributionLogitScale = _m.Attribute(float)
    xtmf_WalkDistributionLogitScale = _m.Attribute(float)
    
    Iterations = _m.Attribute(int)
    NormGap = _m.Attribute(float)
    RelGap = _m.Attribute(float)
    
    if EMME_VERSION >= (4,1):
        NumberOfProcessors = _m.Attribute(int)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.DemandMatrix = _MODELLER.emmebank.matrix('mf15')
        
        self.LinkFareAttributeId = "@lfare"
        self.SegmentFareAttributeId = "@sfare"
        self.HeadwayFractionAttributeId = "@frac"
        self.EffectiveHeadwayAttributeId = "@ehdw"
        self.WalkAttributeId = "@walkp"
        
        self.CalculateCongestedIvttFlag = True
        self.UseBoardingLevelFlag = True
        
        self.WalkSpeed = 0.00
        self.WaitPerception = 0.00
        self.WalkPerceptionToronto = 0.00
        self.WalkPerceptionNonToronto = 0.00
        self.WalkPerceptionTorontoConnectors = 0.00
        self.WalkPerceptionNonTorontoConnectors = 0.00
        self.WalkPerceptionPD1 = 0.00
        self.BoardPerception = 0.00
        
        lines = [""]

        self.CongestionExponentString = "\n".join(lines)

        self.EffectiveHeadwaySlope = 0.00
        
        self.FarePerception = 0.00
        
        self.AssignmentPeriod = 0.00 
        self.NormGap = 0
        self.RelGap = 0
        self.Iterations = 5
        
        if EMME_VERSION >= (4,1):
            self.NumberOfProcessors = cpu_count()
        
        #---Private flags for calibration purposes only
        self._useLogitConnectorChoice = True
        self.xtmf_OriginDistributionLogitScale = 0.2
        self._connectorLogitTruncation = 0.05
        
        self._useLogitAuxTrChoice = False
        self.xtmf_WalkDistributionLogitScale = 0.2
        self._auxTrLogitTruncation = 0.05
        
        self._useMultiCore = False
        self._congestionFunctionType = "CONICAL" #"BPR" 
        self._considerTotalImpedance = True
    
    def page(self):        

        if EMME_VERSION < (4,1,5):
            raise ValueError("Tool not compatible. Please upgrade to version 4.1.5+")

        pb = _tmgTPB.TmgToolPageBuilder(self, title="V4 Fare-Based Transit Assignment v%s" %self.version,
                     description="Executes a congested transit assignment procedure \
                        for GTAModel V4.0. \
                        <br><br>Hard-coded assumptions: \
                        <ul><li> Boarding penalties are assumed stored in <b>UT3</b></li>\
                        <li> The congestion term is stored in <b>US3</b></li>\
                        <li> In-vehicle time perception is 1.0</li>\
                        <li> All available transit modes will be used.</li>\
                        </ul>\
                        <font color='red'>This tool is only compatible with Emme 4.1.5 and later versions</font>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)            
        
        pb.add_header("SCENARIO INPUTS")
        
        pb.add_select_scenario(tool_attribute_name= 'Scenario',
                               title= 'Scenario:',
                               allow_none= False)
        
        pb.add_select_matrix(tool_attribute_name= 'DemandMatrix',
                             filter= ['FULL'], 
                             title= "Demand Matrix",
                             note= "A full matrix of OD demand")
        
        keyval1 = [(-1, 'None')]
        keyval2 = [(-1, 'None')]
        keyval3 = []
        keyval4 = []
        keyval5 = [(-1, 'None')]
        for exatt in self.Scenario.extra_attributes():
            tup = (exatt.id, "%s - %s" %(exatt.id, exatt.description))
            if exatt.type == 'NODE':
                keyval1.append(tup)
            elif exatt.type == 'LINK':
                keyval2.append(tup)
                keyval3.append(tup)
            elif exatt.type == 'TRANSIT_SEGMENT':
                keyval4.append(tup)
            elif exatt.type == 'TRANSIT_LINE':
                keyval5.append(tup)
        
        pb.add_select(tool_attribute_name='HeadwayFractionAttributeId',
                      keyvalues= keyval1, title= "Headway Fraction Attribute",
                      note= "NODE extra attribute to store headway fraction value. \
                          Select NONE to create a temporary attribute. \
                          <br><font color='red'><b>Warning:</b></font>\
                          using a temporary attribute causes an error with \
                          subsequent strategy-based analyses.")

        pb.add_select(tool_attribute_name='EffectiveHeadwayAttributeId',
                      keyvalues= keyval5, title= "Effective Headway Attribute",
                      note= "TRANSIT_LINE extra attribute to store effective headway value. \
                          Select NONE to create a temporary attribute. \
                          <br><font color='red'><b>Warning:</b></font>\
                          using a temporary attribute causes an error with \
                          subsequent strategy-based analyses.")
        
        pb.add_select(tool_attribute_name='WalkAttributeId',
                      keyvalues= keyval2, title= "Walk Perception Attribute",
                      note= "LINK extra attribute to store walk perception value. \
                          Select NONE to create a temporary attribute.\
                          <br><font color='red'><b>Warning:</b></font>\
                          using a temporary attribute causes an error with \
                          subsequent strategy-based analyses.")
        
        pb.add_select(tool_attribute_name= 'LinkFareAttributeId',
                      keyvalues = keyval3, 
                      title= "Link Fare Attribute",
                      note= "LINK extra attribute containing actual fare costs.")
        
        pb.add_select(tool_attribute_name= 'SegmentFareAttributeId',
                      keyvalues= keyval4,
                      title= "Segment Fare Attribute",
                      note= "SEGMENT extra attribute containing actual fare costs.")
        
        pb.add_header("OUTPUT MATRICES")
        
        pb.add_select_output_matrix(tool_attribute_name= 'InVehicleTimeMatrixId',
                                    include_existing= True,
                                    title= "In Vehicle Times Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save in-vehicle times")

        pb.add_checkbox(tool_attribute_name= 'CalculateCongestedIvttFlag',
                        label= "Include congestion in total in-vehicle times?")
        
        pb.add_select_output_matrix(tool_attribute_name= 'CongestionMatrixId',
                                    include_existing= True,
                                    title= "Congestion Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to congestion values.")
        
        pb.add_select_output_matrix(tool_attribute_name= 'WaitTimeMatrixId',
                                    include_existing= True,
                                    title= "Wait Times Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save wait times")
        
        pb.add_select_output_matrix(tool_attribute_name= 'WalkTimeMatrixId',
                                    include_existing= True,
                                    title= "Walk Times Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save walk times")
        
        pb.add_select_output_matrix(tool_attribute_name= 'FareMatrixId',
                                    include_existing= True,
                                    title= "Fares Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save fares.")

        pb.add_select_output_matrix(tool_attribute_name= 'PenaltyMatrixId',
                                    include_existing= True,
                                    title= "Boarding Penalties Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save accrued boarding penalties.")

        pb.add_select_output_matrix(tool_attribute_name= 'ImpedanceMatrixId',
                                    include_existing= True,
                                    title= "Impendance Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save impedance values.")

        pb.add_select_output_matrix(tool_attribute_name= 'DistanceMatrixId',
                                    include_existing= True,
                                    title= "Distance Matrix",
                                    note= "<font color='green'><b>Optional.</b></font> Select \
                                        a matrix in which to save transit distances.")
        
        pb.add_header("PARAMETERS")
        with pb.add_table(False) as t:

            with t.table_cell():
                 pb.add_html("<b>Effective Headway Function Slope:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'EffectiveHeadwaySlope', size= 10)
            with t.table_cell():
                pb.add_html("Applies to headways greater than 15 minutes.")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Wait Time Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WaitPerception', size= 10)
            with t.table_cell():
                pb.add_html("Converts waiting minutes to impedance")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Walking Speed:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkSpeed', size= 4)
            with t.table_cell():
                pb.add_html("Walking speed, in km/hr. Applied to all walk modes.")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Toronto Access Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkPerceptionTorontoConnectors', size= 10)
            with t.table_cell():
                pb.add_html("Walk perception on Toronto centroid connectors")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Toronto Walk Time Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkPerceptionToronto', size= 10)
            with t.table_cell():
                pb.add_html("Walk perception on Toronto links")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Non-Toronto Access Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkPerceptionNonTorontoConnectors', size= 10)
            with t.table_cell():
                pb.add_html("Walk perception on non-Toronto centroid connectors")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Non-Toronto Walk Time Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkPerceptionNonToronto', size= 10)
            with t.table_cell():
                pb.add_html("Walk perception on non-Toronto links")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>PD1 Walk Time Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'WalkPerceptionPD1', size= 10)
            with t.table_cell():
                pb.add_html("Walk perception on links in PD1 (type == 101)")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Boarding Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'BoardPerception', size= 10)
            with t.table_cell():
                pb.add_html("Converts boarding impedance to impedance")
            t.new_row()  
            
            with t.table_cell():
                 pb.add_html("<b>Fare Perception:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'FarePerception', size= 10)
            with t.table_cell():
                pb.add_html("Converts fare costs to impedance. In $/hr.")
            t.new_row()
            
            with t.table_cell():
                 pb.add_html("<b>Assignment Period:</b>")
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'AssignmentPeriod', size= 10)
            with t.table_cell():
                pb.add_html("Multiple-hour demand is divided by this value to convert to a single assignment hour. <br>Typically equal to the number of hours in the assignment period.")
            t.new_row()

        pb.add_header("CONGESTION PARAMETERS")

        pb.add_text_box(tool_attribute_name='CongestionExponentString', 
            size= 500, multi_line=True,
            note= "List of congestion perceptions and exponents. \
            Applies different congestion parameter values based on a segment's ttf value.\
            <br><br><b>Syntax:</b> [<em>ttf</em>] : [<em>perception</em>] \
            : [<em>exponent</em>] ... \
            <br><br>Separate (ttf-perception-exponent) groups with a comma or new line.\
            <br><br>The ttf value must be an integer.\
            <br><br>Any segments with a ttf not specified above will be assigned the congestion \
            parameters of the final group in the list.")

        pb.add_header("CONVERGANCE CRITERIA")
        with pb.add_table(False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'Iterations', size= 4,
                                title= "Iterations")
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'NormGap', size= 12,
                                title= "Normalized Gap")
                
            with t.table_cell():
                pb.add_text_box(tool_attribute_name= 'RelGap', size= 12,
                                title= "Relative Gap")
        
        if EMME_VERSION >= (4,1):
            keyval3 = []
            for i in range(cpu_count()):
                if i == 0:
                    tup = 1, "1 processor"
                else:
                    tup = i + 1, "%s processors" %(i + 1)
                keyval3.insert(0, tup)
            
            pb.add_select(tool_attribute_name='NumberOfProcessors',
                          keyvalues= keyval3,
                          title= "Number of Processors")

        pb.add_checkbox(tool_attribute_name="UseBoardingLevelFlag",
                        label="Use boarding levels?",
                        note="This will force all trips to board at least <br>\
                            one transit vehicle (no walk-all-ways).")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {        
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#HeadwayFractionAttributeId")
                .empty()
                .append(tool.get_scenario_node_attributes())
            inro.modeller.page.preload("#HeadwayFractionAttributeId");
            $("#HeadwayFractionAttributeId").trigger('change');

            $(this).commit();
            $("#EffectiveHeadwayAttributeId")
                .empty()
                .append(tool.get_scenario_node_attributes())
            inro.modeller.page.preload("#EffectiveHeadwayAttributeId");
            $("#EffectiveHeadwayAttributeId").trigger('change');
            
            $("#WalkAttributeId")
                .empty()
                .append(tool.get_scenario_link_attributes())
            inro.modeller.page.preload("#WalkAttributeId");
            $("#WalkAttributeId").trigger('change');
            
            $("#LinkFareAttributeId")
                .empty()
                .append(tool.get_scenario_link_attributes(false))
            inro.modeller.page.preload("#LinkFareAttributeId");
            $("#LinkFareAttributeId").trigger('change');
            
            $("#SegmentFareAttributeId")
                .empty()
                .append(tool.get_scenario_segment_attribtues())
            inro.modeller.page.preload("#SegmentFareAttributeId");
            $("#SegmentFareAttributeId").trigger('change');
        });
        
        $("#InVehicleTimeMatrixId").bind('change', function()
        {
            $(this).commit();
            var opt = $(this).prop('value');
            if (opt == -1)
            {
                $("#CalculateCongestedIvttFlag").parent().parent().hide();
            } else {
                $("#CalculateCongestedIvttFlag").parent().parent().show();
            }
        });
        
        $("#InVehicleTimeMatrixId").trigger('change');

        $("#CongestionExponentString").css({height: '70px'});
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            if self.AssignmentPeriod is None: raise NullPointerException("Assignment period not specified")
            if self.WaitPerception is None: raise NullPointerException("Waiting perception not specified")
            if self.WalkPerceptionToronto is None: raise NullPointerException("Toronto walk perception not specified")
            if self.WalkPerceptionNonToronto is None: raise NullPointerException("Non-Toronto walk perception not specified")
            if self.BoardPerception is None: raise NullPointerException("Boarding perception not specified")
            if self.CongestionExponentString is None: raise NullPointerException("Congestion parameters not specified")
            if self.Iterations is None: raise NullPointerException("Maximum iterations not specified")
            if self.NormGap is None: raise NullPointerException("Normalized gap not specified")
            if self.RelGap is None: raise NullPointerException("Relative gap not specified")
            if self.EffectiveHeadwaySlope is None: raise NullPointerException("Effective headway slope not specified")
            if self.LinkFareAttributeId is None: raise NullPointerException("Link fare attribute not specified")
            if self.SegmentFareAttributeId is None: raise NullPointerException("Segment fare attribute not specified")
            
            
            '''
            Set up the context managers to create the temporary attributes only
            if the None option is selected.
            '''
            @contextmanager
            def blank(att):
                try:
                    yield att
                finally:
                    pass
            if self.HeadwayFractionAttributeId is None:
                manager1 = _util.tempExtraAttributeMANAGER(self.Scenario, 'NODE', default= 0.5)
            else: manager1 = blank(self.Scenario.extra_attribute(self.HeadwayFractionAttributeId))
            if self.WalkAttributeId is None:
                manager2 = _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK', default= 1.0)
            else: manager2 = blank(self.Scenario.extra_attribute(self.WalkAttributeId))
            if self.EffectiveHeadwayAttributeId is None:
                manager3 = _util.tempExtraAttributeMANAGER(self.Scenario, 'TRANSIT_LINE', default= 0.0)
            else: manager3 = blank(self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId))
            nest = (manager1, manager2, manager3)

            headwayAttribute, walkAttribute, effectiveHeadwayAttribute = nest
            with headwayAttribute, walkAttribute, effectiveHeadwayAttribute:
                # Set attributes to default values.
                headwayAttribute.initialize(0.5) 
                walkAttribute.initialize(1.0)
                effectiveHeadwayAttribute.initialize(0.0)
                                
                self.HeadwayFractionAttributeId = headwayAttribute.id
                self.WalkAttributeId = walkAttribute.id
                self.EffectiveHeadwayAttributeId = effectiveHeadwayAttribute.id
                
                self._Execute()
                
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixNumber, WaitPerception,
                 WalkSpeed, WalkPerceptionToronto, WalkPerceptionNonToronto, 
                 WalkPerceptionTorontoConnectors, WalkPerceptionNonTorontoConnectors,
                 WalkPerceptionPD1,
                 WalkAttributeId, HeadwayFractionAttributeId, LinkFareAttributeId,
                 SegmentFareAttributeId, EffectiveHeadwayAttributeId, EffectiveHeadwaySlope,
                 BoardPerception, FarePerception,
                 AssignmentPeriod, Iterations, NormGap, RelGap,
                 xtmf_InVehicleTimeMatrixNumber, xtmf_WaitTimeMatrixNumber, xtmf_WalkTimeMatrixNumber,
                 xtmf_FareMatrixNumber, xtmf_CongestionMatrixNumber, xtmf_PenaltyMatrixNumber, xtmf_DistanceMatrixNumber,
                 xtmf_OriginDistributionLogitScale, 
                 CalculateCongestedIvttFlag, CongestionExponentString, xtmf_ImpedanceMatrixNumber, UseBoardingLevelFlag):                 
        
        if EMME_VERSION < (4,1,5):
            raise Exception("Tool not compatible. Please upgrade to version 4.1.5+")
        
        #---4 Set up parameters
        self.EffectiveHeadwayAttributeId = EffectiveHeadwayAttributeId
                
        self.HeadwayFractionAttributeId = HeadwayFractionAttributeId
        self.WalkAttributeId = WalkAttributeId
        self.LinkFareAttributeId = LinkFareAttributeId
        self.SegmentFareAttributeId = SegmentFareAttributeId
        self.WalkSpeed = WalkSpeed
        self.WaitPerception = WaitPerception
        self.WalkPerceptionNonToronto = WalkPerceptionNonToronto
        self.WalkPerceptionToronto = WalkPerceptionToronto
        self.WalkPerceptionTorontoConnectors = WalkPerceptionTorontoConnectors
        self.WalkPerceptionNonTorontoConnectors = WalkPerceptionNonTorontoConnectors
        self.BoardPerception = BoardPerception
        self.WalkPerceptionPD1 = WalkPerceptionPD1
        self.CalculateCongestedIvttFlag = CalculateCongestedIvttFlag
        self.UseBoardingLevelFlag = UseBoardingLevelFlag
        self.EffectiveHeadwaySlope = EffectiveHeadwaySlope
        
        self.FarePerception = FarePerception
        self.CongestionExponentString = CongestionExponentString
        
        self.xtmf_OriginDistributionLogitScale = xtmf_OriginDistributionLogitScale
        
        self.AssignmentPeriod = AssignmentPeriod
        self.Iterations = Iterations
        self.NormGap = NormGap
        self.RelGap = RelGap

        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        #---2 Set up demand matrix
        assignIdentityMatrix = False
        if xtmf_DemandMatrixNumber == 0:
            manager = _util.tempMatrixMANAGER(matrix_type= 'FULL')
            assignIdentityMatrix = True
        else:
            demandMatrix = _MODELLER.emmebank.matrix("mf%s" %xtmf_DemandMatrixNumber)
            if demandMatrix is None:
                raise Exception("Matrix %s was not found!" %xtmf_DemandMatrixNumber)
            manager = blankManager(demandMatrix)
        
        if self.Scenario.extra_attribute(self.WalkAttributeId) is None:
            raise Exception("Walk perception attribute %s does not exist" %self.WalkAttributeId)
        
        if self.Scenario.extra_attribute(self.HeadwayFractionAttributeId) is None:
            raise Exception("Headway fraction attribute %s does not exist" %self.HeadwayFractionAttributeId)

        if self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId) is None:
            raise Exception("Effective headway attribute %s does not exist" %self.EffectiveHeadwayAttributeId)
        
        if self.Scenario.extra_attribute(self.LinkFareAttributeId) is None:
            raise Exception("Link fare attribute %s does not exist" %self.LinkFareAttributeId)
        
        if self.Scenario.extra_attribute(self.SegmentFareAttributeId) is None:
            raise Exception("Segment fare attribute %s does not exist" %self.SegmentFareAttributeId)
        
        #---3 Set up output matrices
        if xtmf_InVehicleTimeMatrixNumber:
            self.InVehicleTimeMatrixId = "mf%s" %xtmf_InVehicleTimeMatrixNumber
        if xtmf_WaitTimeMatrixNumber:
            self.WaitTimeMatrixId = "mf%s" %xtmf_WaitTimeMatrixNumber
        if xtmf_WalkTimeMatrixNumber:
            self.WalkTimeMatrixId = "mf%s" %xtmf_WalkTimeMatrixNumber
        if xtmf_FareMatrixNumber:
            self.FareMatrixId = "mf%s" %xtmf_FareMatrixNumber
        if xtmf_CongestionMatrixNumber:
            self.CongestionMatrixId = "mf%s" %xtmf_CongestionMatrixNumber
        if xtmf_PenaltyMatrixNumber:
            self.PenaltyMatrixId = "mf%s" %xtmf_PenaltyMatrixNumber
        if xtmf_ImpedanceMatrixNumber:
            self.ImpedanceMatrixId = "mf%s" %xtmf_ImpedanceMatrixNumber
        if xtmf_DistanceMatrixNumber:
            self.DistanceMatrixId = "mf%s" %xtmf_DistanceMatrixNumber
       
        
        print("Running V4 Transit Assignment")
        
        try:
            with manager as self.DemandMatrix:
                if assignIdentityMatrix == True:
                    demandMatrix = _MODELLER.emmebank.matrix(self.DemandMatrix.id)
                    demandMatrix.initialize(0.1)
                self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
        
        print("Done running transit assignment")
    
    ##########################################################################################################    
    

    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with _m.logbook_trace("Checking travel time functions"):
                changes = self._HealTravelTimeFunctions()
                if changes == 0: _m.logbook_write("No problems were found")
            
            self._ChangeWalkSpeed()
            
            if self.InVehicleTimeMatrixId:
                _util.initializeMatrix(id= self.InVehicleTimeMatrixId,
                                       description= "Transit in-vehicle travel times")
            if self.CongestionMatrixId:
                _util.initializeMatrix(id= self.CongestionMatrixId,
                                       description= "Transit in-vehicle congestion")
            if self.WalkTimeMatrixId:
                _util.initializeMatrix(id= self.WalkTimeMatrixId,
                                       description= "Transit total walk times")
            if self.WaitTimeMatrixId:
                _util.initializeMatrix(id= self.WaitTimeMatrixId,
                                       description= "Transit total wait times")
            if self.FareMatrixId:
                _util.initializeMatrix(id= self.FareMatrixId,
                                       description= "Transit total fare costs")
            if self.PenaltyMatrixId:
                _util.initializeMatrix(id= self.PenaltyMatrixId,
                                       description= "Transit total boarding penalties")
            if self.DistanceMatrixId:
                _util.initializeMatrix(id= self.DistanceMatrixId,
                                       description= "Transit distances")

            if self.ImpedanceMatrixId:
                _util.initializeMatrix(id= self.ImpedanceMatrixId,
                                       description= "Transit impedances")
                self.TRACKER.startProcess(3)
                
                self._AssignHeadwayFraction()
                self.TRACKER.completeSubtask()

                self._AssignEffectiveHeadway()
                self.TRACKER.completeSubtask()
                
                self._AssignWalkPerception()
                self.TRACKER.completeSubtask()
                
                spec = self._GetBaseAssignmentSpec()
                
                self.TRACKER.runTool(congestedAssignmentTool,
                                        transit_assignment_spec= spec,
                                        congestion_function= self._GetFuncSpec(),
                                        stopping_criteria= self._GetStopSpec(),
                                        impedances= _MODELLER.emmebank.matrix(self.ImpedanceMatrixId),
                                        scenario= self.Scenario)                
                
                self._ExtractOutputMatrices()

            else: 
                with _util.tempMatrixMANAGER('Temp impedances') as impedanceMatrix:
                                
                    self.TRACKER.startProcess(3)
                
                    self._AssignHeadwayFraction()
                    self.TRACKER.completeSubtask()

                    self._AssignEffectiveHeadway()
                    self.TRACKER.completeSubtask()
                
                    self._AssignWalkPerception()
                    self.TRACKER.completeSubtask()
                
                    spec = self._GetBaseAssignmentSpec()
                
                    self.TRACKER.runTool(congestedAssignmentTool,
                                            transit_assignment_spec= spec,
                                            congestion_function= self._GetFuncSpec(),
                                            stopping_criteria= self._GetStopSpec(),
                                            impedances= impedanceMatrix,
                                            scenario= self.Scenario)                
                
                    self._ExtractOutputMatrices()

    ##########################################################################################################
        
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : "%s - %s" %(self.Scenario, self.Scenario.title),
                "Version": self.version,
                "Demand Matrix": "%s - %s" %(self.DemandMatrix, self.DemandMatrix.description),
                "Wait Perception": self.WaitPerception,
                "Fare Perception": self.FarePerception,
                "Toronto Walk Perception": self.WalkPerceptionToronto,
                "Non-Toronto Walk Perception": self.WalkPerceptionNonToronto,
                "Toronto Access Perception": self.WalkPerceptionTorontoConnectors,
                "Non-Toronto Access Perception": self.WalkPerceptionNonTorontoConnectors,
                "Assignment Period": self.AssignmentPeriod,
                "Boarding Perception": self.BoardPerception,
                "Iterations": self.Iterations,
                "Normalized Gap": self.NormGap,
                "Relative Gap": self.RelGap,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _HealTravelTimeFunctions(self):
        changes = 0
        for function in _MODELLER.emmebank.functions():
            if function.type != 'TRANSIT_TIME': continue
            
            cleanedExpression = function.expression.replace(" ", '') #Remove all spaces from the expression
            if "us3" in cleanedExpression:
                if cleanedExpression.endswith("*(1+us3)"):
                    #Detected pattern of transit time function which includes a congestion term
                    #i.e., Python was exited before the context manager was able to restore the
                    #function's original form. Therefore we try to heal it here.
                    
                    #Example: ft1 = "((length*60/us1))*(1+us3)", where the original function
                    #is "(length*60/us1)"
                    index = cleanedExpression.find("*(1+us3)")
                    newExpression = cleanedExpression[:index][1:-1]
                    
                    function.expression = newExpression
                    
                    print("Detected function %s with existing congestion term." %function)
                    print("Original expression= '%s'" %cleanedExpression)
                    print("Healed expression= '%s'" %newExpression)
                    print("")
                    _m.logbook_write("Detected function %s with existing congestion term." %function)
                    _m.logbook_write("Original expression= '%s'" %cleanedExpression)
                    _m.logbook_write("Healed expression= '%s'" %newExpression)
                    
                    changes += 1
                else:
                    raise Exception("Function %s already uses US3, which is reserved for transit" %function + \
                                    " segment congestion values. Please modify the expression " +\
                                    "to use different attributes.")
        return changes
    
    def _ChangeWalkSpeed(self):
        with _m.logbook_trace("Setting walk speeds to %s" %self.WalkSpeed):
            if EMME_VERSION >= (4,1):
                self._ChangeWalkSpeed4p1()
            else:
                self._ChangeWalkSpeed4p0()
    
    def _ChangeWalkSpeed4p0(self):
        changeModeTool = _MODELLER.tool('inro.emme.data.network.mode.change_mode')
        for mode in self.Scenario.modes():
            if mode.type != 'AUX_TRANSIT': continue
            changeModeTool(mode,
                           mode_speed= self.WalkSpeed,
                           scenario= self.Scenario)
    
    def _ChangeWalkSpeed4p1(self):
        partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
        
        for mode in partialNetwork.modes():
            if mode.type != 'AUX_TRANSIT': continue
            mode.speed = self.WalkSpeed
            _m.logbook_write("Changed mode %s" %mode.id)
        
        baton = partialNetwork.get_attribute_values('MODE', ['speed'])
        self.Scenario.set_attribute_values('MODE', ['speed'], baton)
    
    def _ParseExponentString(self):
        exponentList = []
        components = _regex_split('\n|,', self.CongestionExponentString) #Supports newline and/or commas
        for component in components:
            if component.isspace(): continue #Skip if totally empty
            
            parts = component.split(':')
            if len(parts) != 3:
                msg = "Error parsing penalty and filter string: Separate ttf, perception and exponent with colons ttf:perception:exponent"
                msg += ". [%s]" %component 
                raise SyntaxError(msg)
            strippedParts = [item.strip() for item in parts]
            try:
                ttf = int(strippedParts[0])
            except:
                msg = "ttf value must be an integer"
                msg += ". [%s]" %component
                raise SyntaxError(msg)
            try:
                perception = float(strippedParts[1])
            except:
                msg = "Perception value must be a number"
                msg += ". [%s]" %component
                raise SyntaxError(msg)
            try:
                exponent = float(strippedParts[2])
            except:
                msg = "Exponent value must be a number"
                msg += ". [%s]" %component
                raise SyntaxError(msg)   
            exponentList.append(strippedParts)

        return exponentList
        
    def _AssignHeadwayFraction(self):
        exatt = self.Scenario.extra_attribute(self.HeadwayFractionAttributeId)
        exatt.initialize(0.5)

    def _AssignEffectiveHeadway(self):
        exatt = self.Scenario.extra_attribute(self.EffectiveHeadwayAttributeId)
        exatt.initialize(0.0)
        smallHeadwaySpec = {
                    "result": self.EffectiveHeadwayAttributeId,
                    "expression": "hdw",
                    "aggregation": None,
                    "selections": {
                        "transit_line": "hdw=0,15"
                    },
                    "type": "NETWORK_CALCULATION"
                }
        largeHeadwaySpec = {
                    "result": self.EffectiveHeadwayAttributeId,
                    "expression": "15+2*" + str(self.EffectiveHeadwaySlope) + "*(hdw-15)", 
                    "aggregation": None,
                    "selections": {
                        "transit_line": "hdw=15,999"
                    },
                    "type": "NETWORK_CALCULATION"
                }
        networkCalcTool(smallHeadwaySpec, self.Scenario)
        networkCalcTool(largeHeadwaySpec, self.Scenario)

    def _AssignWalkPerception(self):
        exatt = self.Scenario.extra_attribute(self.WalkAttributeId)
        exatt.initialize(1.0)
        
        def applySelection(val, selection):
            spec = {
                    "result": self.WalkAttributeId,
                    "expression": str(val),
                    "aggregation": None,
                    "selections": {
                        "link": selection
                    },
                    "type": "NETWORK_CALCULATION"
                }
            networkCalcTool(spec, self.Scenario)
        
        with _m.logbook_trace("Assigning walk time perception factors"):
            applySelection(self.WalkPerceptionToronto, "i=10000,19999 or j=10000,19999 or i=97000,98000 or j=97000,98000")
            applySelection(self.WalkPerceptionNonToronto, "i=20000,91999 or j=20000,91999")
            applySelection(self.WalkPerceptionPD1, "type=101")
            applySelection(self.WalkPerceptionTorontoConnectors, "i=0,1000 or j=0,1000")
            applySelection(self.WalkPerceptionNonTorontoConnectors, "i=1001,7000 or j=1001,7000")
            applySelection(1, "mode=t and i=97000,98000 and j=97000,98000")
            applySelection(0, "i=9700,9999 or j=9700,9999")
    
    def _GetBaseAssignmentSpec(self):
        
        if self.FarePerception == 0:
            farePerception = 0.0
        else:
            farePerception = 60.0 / self.FarePerception
        
        baseSpec = {
                "modes": ["*"],
                "demand": self.DemandMatrix.id,
                "waiting_time": {
                    "headway_fraction": self.HeadwayFractionAttributeId,
                    "effective_headways": self.EffectiveHeadwayAttributeId,
                    "spread_factor": 1,
                    "perception_factor": self.WaitPerception
                },
                "boarding_time": {
                    "at_nodes": None,
                    "on_lines": {
                        "penalty": "ut3",
                        "perception_factor": self.BoardPerception
                    }
                },
                "boarding_cost": {
                    "at_nodes": {
                        "penalty": 0,
                        "perception_factor": 1
                    },
                    "on_lines": None
                },
                "in_vehicle_time": {
                    "perception_factor": "us2"
                },
                "in_vehicle_cost": {
                                    "penalty": self.SegmentFareAttributeId,
                                    "perception_factor": farePerception
                },
                "aux_transit_time": {
                                     "perception_factor": self.WalkAttributeId
                },
                "aux_transit_cost": {
                                    "penalty": self.LinkFareAttributeId,
                                    "perception_factor": farePerception
                },
                "connector_to_connector_path_prohibition": None,
                "od_results": {
                    "total_impedance": self.ImpedanceMatrixId
                },
                "flow_distribution_between_lines": {
                                        "consider_travel_time": self._considerTotalImpedance
                                        },
                "save_strategies": True,
                "type": "EXTENDED_TRANSIT_ASSIGNMENT"
            }
        
        if self._useLogitConnectorChoice:
            baseSpec["flow_distribution_at_origins"] = {
                                                "by_time_to_destination": {
                                                        "logit": {
                                                            "scale": self.xtmf_OriginDistributionLogitScale,
                                                            "truncation": self._connectorLogitTruncation
                                                        }
                                                    },
                                                    "by_fixed_proportions": None}
        
        if EMME_VERSION >= (4,1,0):
                    
            baseSpec["performance_settings"] = {
                    "number_of_processors": self.NumberOfProcessors
                }
            
            if self._useLogitAuxTrChoice:
                raise NotImplementedError()
                baseSpec["flow_distribution_at_regular_nodes_with_aux_transit_choices"] = {
                    "choices_at_regular_nodes": {
                        "choice_points": "ui1",
                        "aux_transit_choice_set": "BEST_LINK",
                        "logit_parameters": {
                            "scale": self.xtmf_WalkDistributionLogitScale,
                            "truncation": 0.05
                            }
                        }
                    }

        if EMME_VERSION >= (4,2,1):
            if self.UseBoardingLevelFlag:
                modeList = []
                partialNetwork = self.Scenario.get_partial_network(['MODE'], True)
        
                for mode in partialNetwork.modes():
                    if mode.type != 'TRANSIT': continue
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

        partialSpec = """import math 
def calc_segment_cost(transit_volume, capacity, segment): """

        for count, item in enumerate(parameterList):
            alpha = float(item[2])
            beta = (2 * alpha - 1) / (2 * alpha - 2)
            alphaSquare = alpha ** 2
            betaSquare = beta ** 2
            if count == 0:                
                partialSpec += """
    if segment.transit_time_func == """ + item[0] + """: 
        return (""" + item[1] + """ * (1 + math.sqrt(""" + str(alphaSquare) + """ * 
            (1 - transit_volume / capacity) ** 2 + """ + str(betaSquare) + """) - """ + str(alpha) + """ 
            * (1 - transit_volume / capacity) - """ + str(beta) + """))"""
            else: 
                partialSpec += """
    elif segment.transit_time_func == """ + item[0] + """: 
        return (""" + item[1] + """ * (1 + math.sqrt(""" + str(alphaSquare) + """ *  
            (1 - transit_volume / capacity) ** 2 + """ + str(betaSquare) + """) - """ + str(alpha) + """ 
            * (1 - transit_volume / capacity) - """ + str(beta) + """))"""
        
        partialSpec += """
    else: 
        raise Exception("ttf=%s congestion values not defined in input" %segment.transit_time_func)"""
            
        funcSpec = {
            "type": "CUSTOM",
            "assignment_period": self.AssignmentPeriod,
            "orig_func": False,
            "congestion_attribute": "us3", #Hard-coded to US3
            "python_function": partialSpec                     
            }
               
        return funcSpec
    
    def _GetStopSpec(self):
        stopSpec = {
                    "max_iterations": self.Iterations,
                    "normalized_gap": self.NormGap,
                    "relative_gap": self.RelGap
                    }
        return stopSpec
    
    def _ExtractOutputMatrices(self):
        
        #If any of the standard results matrices are required, extract them
        if self.InVehicleTimeMatrixId or self.WalkTimeMatrixId or self.WaitTimeMatrixId:
            self._ExtractTimesMatrices()
        
        #If extracting RAW IVTT and NOT also saving the congestion matrix,
        #we need to create a temporary matrix in which to store congestion
        #using a context manager
        if not self.CongestionMatrixId and self.InVehicleTimeMatrixId and \
                not self.CalculateCongestedIvttFlag:
            def congestionMatrixManager():
                return _util.tempMatrixMANAGER()
        else:
            @contextmanager
            def congestionMatrixManager():
                try:
                    yield _MODELLER.emmebank.matrix(self.CongestionMatrixId)
                finally:
                    pass
        
        #If the congestion matrix is required, or Raw IVTT matrix is required, extract the congestion matrix
        if self.InVehicleTimeMatrixId and not self.CalculateCongestedIvttFlag or self.CongestionMatrixId:
            with congestionMatrixManager() as congestionMatrix:
                self._ExtractCongestionMatrix(congestionMatrix.id)
            
                #If Raw IVTT is required, use the congestion matrix to fix it
                if self.InVehicleTimeMatrixId and not self.CalculateCongestedIvttFlag:
                    self._FixRawIVTT(congestionMatrix.id)
        
        #If the fares matrix is required, extract that.
        if self.FareMatrixId:
            self._ExtractCostMatrix()    
            
            

    def _ExtractTimesMatrices(self):
        spec = {
                "by_mode_subset": {
                    "modes": ["*"],
                    "actual_in_vehicle_times": self.InVehicleTimeMatrixId,
                    "actual_aux_transit_times": self.WalkTimeMatrixId
                },
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "actual_total_waiting_times": self.WaitTimeMatrixId
            }
        if self.PenaltyMatrixId:
            spec["by_mode_subset"]["actual_total_boarding_times"] = self.PenaltyMatrixId
        if self.DistanceMatrixId:
            spec["by_mode_subset"]["distance"] = self.DistanceMatrixId
        self.TRACKER.runTool(matrixResultsTool, spec, scenario= self.Scenario)
    
    def _ExtractCostMatrix(self):
        spec = {
                "trip_components": {
                    "boarding": None,
                    "in_vehicle": self.SegmentFareAttributeId,
                    "aux_transit": self.LinkFareAttributeId,
                    "alighting": None
                },
                "sub_path_combination_operator": "+",
                "sub_strategy_combination_operator": "average",
                "selected_demand_and_transit_volumes": {
                    "sub_strategies_to_retain": "ALL",
                    "selection_threshold": {
                        "lower": -999999,
                        "upper": 999999
                    }
                },
                "analyzed_demand": self.DemandMatrix.id,
                "constraint": None,
                "results": {
                    "strategy_values": self.FareMatrixId,
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        if EMME_VERSION >= (4,3,0):
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario, num_processors=self.NumberOfProcessors)
        else:
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario)           
    
    def _ExtractCongestionMatrix(self, congestionMatrixId):
        spec = {"trip_components": {
                    "boarding": None,
                    "in_vehicle": "@ccost",
                    "aux_transit": None,
                    "alighting": None
                },
                "sub_path_combination_operator": "+",
                "sub_strategy_combination_operator": "average",
                "selected_demand_and_transit_volumes": {
                    "sub_strategies_to_retain": "ALL",
                    "selection_threshold": {
                        "lower": -999999,
                        "upper": 999999
                    }
                },
                "analyzed_demand": self.DemandMatrix.id,
                "constraint": None,
                "results": {
                    "strategy_values":congestionMatrixId,
                    "selected_demand": None,
                    "transit_volumes": None,
                    "aux_transit_volumes": None,
                    "total_boardings": None,
                    "total_alightings": None
                },
                "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
            }
        if EMME_VERSION >= (4,3,0):
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario, num_processors=self.NumberOfProcessors)
        else:
            self.TRACKER.runTool(strategyAnalysisTool, spec, scenario= self.Scenario)           
    
    def _FixRawIVTT(self, congestionMatrixId):
        expression = "{mfivtt} - {mfcong}".format(mfivtt= self.InVehicleTimeMatrixId,
                                                 mfcong= congestionMatrixId)

        matrixCalcSpec = {
                "expression": expression,
                "result": self.InVehicleTimeMatrixId,
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
        if EMME_VERSION >= (4,2,1):
            matrixCalcTool(matrixCalcSpec, scenario= self.Scenario, num_processors=self.NumberOfProcessors)
        else:
            matrixCalcTool(matrixCalcSpec, scenario= self.Scenario)
    
    def _ExtractRawIvttMatrix(self):
        with _util.tempMatrixMANAGER("Congestion matrix") as congestionMatrix:
            analysisSpec = {
                         "trip_components": {
                                "boarding": None,
                                "in_vehicle": "@ccost",
                                "aux_transit": None,
                                "alighting": None
                            },
                            "sub_path_combination_operator": "+",
                            "sub_strategy_combination_operator": "average",
                            "selected_demand_and_transit_volumes": {
                                "sub_strategies_to_retain": "ALL",
                                "selection_threshold": {
                                    "lower": -999999,
                                    "upper": 999999
                                }
                            },
                            "analyzed_demand": self.DemandMatrix.id,
                            "constraint": None,
                            "results": {
                                "strategy_values":congestionMatrix.id,
                                "selected_demand": None,
                                "transit_volumes": None,
                                "aux_transit_volumes": None,
                                "total_boardings": None,
                                "total_alightings": None
                            },
                            "type": "EXTENDED_TRANSIT_STRATEGY_ANALYSIS"
                        }
            if EMME_VERSION >= (4,3,0):
                self.TRACKER.runTool(strategyAnalysisTool, analysisSpec, scenario= self.Scenario, num_processors=self.NumberOfProcessors)
            else:
                self.TRACKER.runTool(strategyAnalysisTool, analysisSpec, scenario= self.Scenario)           
            
            expression = "{mfivtt} - {mfcong}".format(mfivtt= self.InVehicleTimeMatrixId,
                                                             mfcong= congestionMatrix.id)
            matrixCalcSpec = {
                            "expression": expression,
                            "result": self.InVehicleTimeMatrixId,
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
            if EMME_VERSION >= (4,2,1):
                matrixCalcTool(matrixCalcSpec, scenario= self.Scenario, num_processors=self.NumberOfProcessors)
            else:
                matrixCalcTool(matrixCalcSpec, scenario= self.Scenario)
    
    #---MODELLER INTERFACE FUNCTIONS
    
    def short_description(self):
        return "Fare-based transit assignment tool for GTAModel V4"
    
    @_m.method(return_type=six.u)
    def get_scenario_node_attributes(self):
        options = ["<option value='-1'>None</option>"]
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'NODE':
                options.append('<option value="%s">%s - %s</option>' %(exatt.id, exatt.id, exatt.description))
        return "\n".join(options)
    
    @_m.method(return_type=six.u)
    def get_scenario_link_attributes(self, include_none= True):
        options = []
        if include_none:
            options.append("<option value='-1'>None</option>")
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'LINK':
                options.append('<option value="%s">%s - %s</option>' %(exatt.id, exatt.id, exatt.description))
        return "\n".join(options)
    
    @_m.method(return_type=six.u)
    def get_scenario_segment_attribtues(self):
        options = []
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'TRANSIT_SEGMENT':
                options.append('<option value="%s">%s - %s</option>' %(exatt.id, exatt.id, exatt.description))
        return "\n".join(options)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        
