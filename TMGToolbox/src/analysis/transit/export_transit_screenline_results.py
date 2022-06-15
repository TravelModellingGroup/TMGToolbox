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
[TITLE]

    Authors: pkucirek, mattaustin222

    Latest revision by: mattaustin222
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-09-19 by pkucirek
    
    1.0.0 Published on 2014-11-19
    
    1.1.0 Added functionality for XTMF

    2.0.0 Forked from base Export Screenline Results tool
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
netCalc = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ExportTransitScreenlineResults(_m.Tool()):
    
    version = '2.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    CountpostFlagAttribute = _m.Attribute(str)
    AlternateFlagAttribute = _m.Attribute(str)

    PedestrianFlag = _m.Attribute(bool)
    
    ScreenlineFile = _m.Attribute(str)
    ExportFile = _m.Attribute(str)

    LineFilterExpression = _m.Attribute(str)

    RepresentativeHourFactor = _m.Attribute(float)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.CountpostFlagAttribute = "@stn1"
        self.AlternateFlagAttribute = "@stn2"
        self.LineFilterExpression = "all"
        self.RepresentativeHourFactor = 2.04
        self.PedestrianFlag = False
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Transit Screenline Results v%s" %self.version,
                     description="Aggregates transit volumes for a specified line filter based on a \
                         given screenline aggregation file. A screenline is defined as a collection \
                         of count stations, where a count station is encoded in a link extra \
                         attribute. Count stations can belong to multiple screenlines. \
                         <br><br>The screenline definition file structure assumes a header line, \
                         followed by lines, one for each screenline: station pair, stored in \
                         at least two columns.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        keyval1 = []
        keyval2 = [(-1, 'None - No attribute')]
        for att in _MODELLER.scenario.extra_attributes():
            if att.type == 'LINK':
                text = "%s - %s" %(att.id, att.description)
                keyval1.append((att.id, text))
                keyval2.append((att.id, text))
        
        pb.add_select(tool_attribute_name='CountpostFlagAttribute',
                      keyvalues=keyval1,
                      title="Countpost Attribute",
                      note="LINK attribute containing countpost id numbers")
        
        pb.add_select(tool_attribute_name='AlternateFlagAttribute',
                      keyvalues=keyval2,
                      title="Alternate Countpost Attribute",
                      note="<font color='green'><b>Optional:</b></font> Alternate countpost attribute \
                      for multiple post per link")

        pb.add_checkbox(tool_attribute_name= 'PedestrianFlag',
                        label= "Count pedestrians instead of transit?")

        pb.add_text_box(tool_attribute_name='LineFilterExpression',
                        title="Line Filter Expression",
                        size=100, multi_line=True)

        pb.add_text_box(tool_attribute_name='RepresentativeHourFactor',
                        title="Representative Hour Factor",
                        size=40)
        
        pb.add_select_file(tool_attribute_name='ScreenlineFile',
                           window_type='file',
                           file_filter="*.csv",
                           title="Screenline Definitions File")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           file_filter="*.csv",
                           title="Export File")
        
        #---JAVASCRIPT
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            
            $("#CountpostFlagAttribute")
                .empty()
                .append(tool.preload_scenario_attributes())
            inro.modeller.page.preload("#CountpostFlagAttribute");
            $("#CountpostFlagAttribute").trigger('change');
            
            $("#AlternateFlagAttribute")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#AlternateFlagAttribute");
            $("#AlternateFlagAttribute").trigger('change');
        });
        
        if (tool.check_ped_flag())
        {
            $("#LineFilterExpression").prop('disabled', true);
        } else {
            $("#LineFilterExpression").prop('disabled', false);
        }

        $("#PedestrianFlag").bind('change', function()
        {
            $(this).commit();
            var flag = tool.check_ped_flag();
            
            $("#LineFilterExpression").prop('disabled', flag);
        });

        /*
        $("#ScreenlineFile").bind('change', function()
        {
            $(this).commit();
            var infoString = tool.preload_screenline_definitions();
            alert(infoString);
        });
        */

        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    @_m.method(return_type= bool)
    def check_ped_flag(self):
        return self.PedestrianFlag
    
    def short_description(self):
        return "<em>Exports transit results for screenlines defined by multiple count posts.</em>"
    
    @_m.method(return_type=six.u)
    def preload_screenline_definitions(self):
        atts = [self.CountpostFlagAttribute]
        if self.AlternateFlagAttribute: atts.append(self.AlternateFlagAttribute)
        
        countposts = set()
        for linkId, attributes in six.iteritems(_util.fastLoadLinkAttributes(self.Scenario, atts)):
            post1 = attributes[self.CountpostFlagAttribute]
            post2 = 0
            if self.AlternateFlagAttribute: post2 = attributes[self.AlternateFlagAttribute]
            
            if post1: countposts.add(int(post1))
            if post2: countposts.add(int(post2))
        
        lines = []
        screenlines = {}
        with open(self.ScreenlineFile) as reader:
            try:
                reader.readline()
                for line in reader:
                    cells = line.strip().split(',')
                    if len(cells) < 2: continue
                    screenlineID = cells[0]
                    countpostID = int(cells[1])
                    if not screenlineID in screenlines:
                        screenlines[screenlineID] = set([countpostID])
                    else:
                        screenlines[screenlineID].add(countpostID)
            except Exception as e:
                return "Error while parsing screenline defintion file: %s" %e
                    
        for screenlineID, stations in six.iteritems(screenlines):
            nStations = len(stations)
            nMissing = 0
            for station in stations:
                if not station in countposts: nMissing += 1
            
            status = "OK"
            if nMissing == nStations:
                status = "Missing"
            elif nMissing > 0:
                status = "Check"
            
            lines.append("\t".join([screenlineID, str(nStations), str(nMissing), status]))
        lines.sort()
        lines.insert(0, "Screenline ID\tnStations\tnMissing\tStatus")
        return "\n".join(lines)
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, CountpostFlagAttribute, AlternateFlagAttribute, ScreenlineFile, ExportFile, 
                 LineFilterExpression, RepresentativeHourFactor, PedestrianFlag):
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)

        linkAtts = set([att.id for att in self.Scenario.extra_attributes() if att.type == 'LINK'])
        
        if not CountpostFlagAttribute in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %CountpostFlagAttribute)
        if not AlternateFlagAttribute in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %AlternateFlagAttribute)

        #---2 Set up parameters
        self.CountpostFlagAttribute = CountpostFlagAttribute
        self.AlternateFlagAttribute = AlternateFlagAttribute
        self.ScreenlineFile = ScreenlineFile
        self.ExportFile = ExportFile
        self.LineFilterExpression = LineFilterExpression
        self.RepresentativeHourFactor = RepresentativeHourFactor
        self.PedestrianFlag = PedestrianFlag
        
        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
        return
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            screenlines = self._LoadScreenlinesFile()
            
            with _util.tempExtraAttributeMANAGER(self.Scenario, 'LINK', description= "Link Volumes") \
                as linkSumAtt:

                self._ProcessLinkAtt(linkSumAtt.id)

                counts = self._LoadResults(linkSumAtt.id)
            
                self._ExportResults(screenlines, counts)
            

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadScreenlinesFile(self):        
        screenlines = {}
        with open(self.ScreenlineFile) as reader:
            reader.readline()
            for line in reader:
                try:
                    cells = line.strip().split(',')
                    if len(cells) < 2: continue
                    screenlineID = cells[0]
                    countpostID = int(cells[1])
                    if not screenlineID in screenlines:
                        screenlines[screenlineID] = set([countpostID])
                    else:
                        screenlines[screenlineID].add(countpostID)
                except:
                    continue
        return screenlines
    
    def _ProcessLinkAtt(self, linkSumAttId):
        if self.PedestrianFlag:
            spec = {
                "result": linkSumAttId,
                "expression": "volax",
                "selections": {
                    "link": "all"
                },
                "type": "NETWORK_CALCULATION"
            }
        else:
            spec = {
                "result": linkSumAttId,
                "expression": "voltr",
                "aggregation": "+",
                "selections": {
                    "transit_line": self.LineFilterExpression,
                    "link": "all"
                    },
                "type": "NETWORK_CALCULATION"
            }
        
        netCalc(spec, scenario=self.Scenario)
    
    def _LoadResults(self, linkSumAttId):
        linkAtts = [self.CountpostFlagAttribute, linkSumAttId]
        if self.AlternateFlagAttribute: linkAtts.append(self.AlternateFlagAttribute)
        
        linkAttributes = _util.fastLoadLinkAttributes(self.Scenario, linkAtts)
        
        counts = {}
        for attributes in linkAttributes.itervalues():
            voltrLink = attributes[linkSumAttId]
                        
            post1 = int(attributes[self.CountpostFlagAttribute])
            post2 = 0
            if self.AlternateFlagAttribute: post2 = int(attributes[self.AlternateFlagAttribute])
            
            if post1:
                if not post1 in counts:
                    counts[post1] = voltrLink
                else:
                    counts[post1] += voltrLink
            if post2:
                if not post2 in counts:
                    counts[post2] = voltrLink
                else:
                    counts[post2] += voltrLink
        return counts
    
    def _ExportResults(self, screenlines, counts):
        with open(self.ExportFile, 'w') as writer:
            if self.PedestrianFlag:
                writer.write("Screenline,nStations,nMissing,PedVolume")
            else:
                writer.write("Screenline,nStations,nMissing,TransitVolume")
            
            orderedLines = [item for item in six.iteritems(screenlines)]
            orderedLines.sort()
            
            for screenlineID, stations in orderedLines:
                totalVoltr = 0
                nStations = len(stations)
                nMissing = 0
                
                for station in stations:
                    if not station in counts:
                        nMissing += 1
                        continue
                    voltrLink = counts[station]
                    totalVoltr += voltrLink

                totalVoltr /= self.RepresentativeHourFactor
                
                writer.write("\n" + ",".join([screenlineID, str(nStations), str(nMissing), \
                                              str(totalVoltr)]))
                    
                
        