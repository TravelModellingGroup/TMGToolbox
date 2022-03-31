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
Check Auto Network Integrity

    Authors: pkucirek

    Latest revision by: pkucirek
    
    Examines a network for data problems that might result in 
    road or transit assignment problems (such as infinite loops). 
    Checks for:
         - Non-existant function reference (links, turns, segments)
         - VDF = 0 for auto links
         - Lanes = 0 for auto links
         - UL2 (speed) = 0 for auto links
         - UL3 (capacity) = 0 for auto links
         - Speed = 0 for transit lines
         - US1 (segment speed) = 0 for transit segments with TTF = 1
    
        
'''
#---VERSION HISTORY
'''
    1.0.0 Created on 2014-01-20 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class CheckNetworkIntegrity(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 5 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    LinkFlagAttributeId = _m.Attribute(str)
    LineFlagAttributeId = _m.Attribute(str)
    SegmentFlagAttributeId = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Check Network Integrity v%s" %self.version,
                     description="Examines a network for data problems that might result in \
                         road or transit assignment problems (such as infinite loops). Checks \
                         for: \
                         <ul><li> Non-existant function reference (links, turns, segments)</li>\
                         <li> VDF = 0 for auto links</li>\
                         <li> Lanes = 0 for auto links</li>\
                         <li> UL2 (speed) = 0 for auto links</li>\
                         <li> UL3 (capacity) = 0 for auto links</li>\
                         <li> Speed = 0 for transit lines</li>\
                         <li> US1 (segment speed) = 0 for transit segments with TTF = 1</li></ul>",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_header("ATTRIBUTE FLAGS", 
                      note = "Optional extra attributes to flag elements with errors.")
        
        keyValLinks = {}
        keyValLines = {}
        keyValSegs = {}        
        for exatt in self.Scenario.extra_attributes():
            if exatt.type == 'LINK':
                keyValLinks[exatt.id] = "%s - %s" %(exatt.id, exatt.description)
            elif exatt.type == 'TRANSIT_LINE':
                keyValLines[exatt.id] = "%s - %s" %(exatt.id, exatt.description)
            elif exatt.type == 'TRANSIT_SEGMENT':
                keyValSegs[exatt.id] = "%s - %s" %(exatt.id, exatt.description)
        
        pb.add_select(tool_attribute_name = 'LinkFlagAttributeId',
                      keyvalues = keyValLinks,
                      title = "Link flag attribute")
        
        pb.add_select(tool_attribute_name = 'LineFlagAttributeId',
                      keyvalues = keyValLines,
                      title = "Transit line flag attributes")
        
        pb.add_select(tool_attribute_name = 'SegmentFlagAttributeId',
                      keyvalues = keyValSegs,
                      title = "Transit segment flag attributes")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        $("#LinkFlagAttributeId")
             .prepend(0,"<option value='-1' selected='selected'>None</option>")
             .prop("selectedIndex", 0)
             .trigger('change')
        //alert($("#LinkFlagAttributeId").selectedIndex);
        
        $("#LineFlagAttributeId")
             .prepend(0,"<option value='-1' selected='selected'>None</option>")
             .prop("selectedIndex", 0)
             .trigger('change')
        //alert($("#LineFlagAttributeId").selectedIndex);
        
        $("#SegmentFlagAttributeId")
             .prepend(0,"<option value='-1' selected='selected'>None</option>")
             .prop("selectedIndex", 0)
             .trigger('change')
        //alert($("#SegmentFlagAttributeId").selectedIndex);
        
        var tool = new inro.modeller.util.Proxy(%s) ;
        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            var linkOptions = tool._GetLinkExtraAttributes();
            var lineOptions = tool._GetLineExtraAttribute();
            var segmentOptions = tool._GetSegExtraAttributes();
            
            $("#LinkFlagAttributeId")
                .empty()
                .append("<option value='-1' selected='selected'>None</option>")
                .append(linkOptions)
                //.data("combobox")._refresh_width();
            inro.modeller.page.preload("#LinkFlagAttributeId");
            $("#LinkFlagAttributeId").trigger('change');
            
            $("#LineFlagAttributeId")
                .empty()
                .append("<option value='-1' selected='selected'>None</option>")
                .append(lineOptions)
                //.data("combobox")._refresh_width();
            inro.modeller.page.preload("#LineFlagAttributeId");
            $("#LineFlagAttributeId").trigger('change');
            
            $("#SegmentFlagAttributeId")
                .empty()
                .append("<option value='-1' selected='selected'>None</option>")
                .append(segmentOptions)
                //.data("combobox")._refresh_width();
            inro.modeller.page.preload("#SegmentFlagAttributeId");
            $("#SegmentFlagAttributeId").trigger('change');
        });
        
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            errCount = self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        if errCount > 0:
            s = " %s problems were identified (see logbook for details)." %errCount
        else:
            s = "Done. No problems were found."
        self.tool_run_msg = _m.PageBuilder.format_info(s)
    
    def __call__(self, xtmf_ScenarioNumber):
        '''
        Slightly different behaviour is executed from XTMF ModellerBridge.
        In addition to reporting the problems to the logbook, throw
        an exception to disrupt a model run. Also, disable the option
        to save element flags.
        '''
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            errCount = self._Execute()
            
            if errCount > 0:
                raise Exception("%s elements were flagged with problems. See Modeller" %errCount +
                                " logbook for details.")
            
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            network = self.Scenario.get_network()
            print ("Network loaded.")
            
            functions = set([func.id for func in _MODELLER.emmebank.functions()])
            autoModes = set([m for m in network.modes() if m.type == 'AUTO' or m.type == 'AUX_AUTO'])
            
            issues = []
            errCount = 0
            
            if self.LinkFlagAttributeId is not None:
                for link in network.links(): link[self.LinkFlagAttributeId] = 0
                print ("Reset link extra attribute '%s' to 0" %self.LinkFlagAttributeId)
            if self.LineFlagAttributeId is not None:
                for line in network.transit_lines(): link[self.LineFlagAttributeId] = 0
                print ("Reset transit line extra attribute '%s' to 0" %self.LineFlagAttributeId)
            if self.SegmentFlagAttributeId is not None:
                for seg in network.transit_segments(): seg[self.SegmentFlagAttributeId] = 0
                print ("Reset transit segment extra attribute '%s' to 0" %self.SegmentFlagAttributeId)
            
            print ("Checking links")
            self.TRACKER.startProcess(network.element_totals['links'])
            for link in network.links():
                errors = []
                
                if autoModes & link.modes: #If set intersection is empty, this is an auto link
                    if link.volume_delay_func == 0:
                        errors.append("Auto link VDF is 0.")
                        errCount += 1
                    else:
                        vdf = "fd%s" %link.volume_delay_func
                        if not vdf in functions:
                            errors.append("Auto link VDF not in databank: %s" %vdf)
                            errCount += 1
                    
                    if link.num_lanes == 0:
                        errors.append("Auto link lanes is 0.")
                        errCount += 1
                    if link.data2 == 0:
                        errors.append("Auto link speed (UL2) is 0.")
                        errCount += 1
                    if link.data3 == 0:
                        errors.append("Auto link capacity (UL3) is 0.")
                        errCount += 1
                
                if errors:
                    tup = ('LINK', str(link), errors)
                    issues.append(tup)
                    
                    if self.LinkFlagAttributeId is not None:
                        link[self.LinkFlagAttributeId] = 1
                    
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            print ("Checking transit lines")
            self.TRACKER.startProcess(network.element_totals['transit_lines'])
            for line in network.transit_lines():
                if line.speed == 0:
                    tup = ('TRANSIT_LINE', str(line), ["Line speed is 0."])
                    issues.append(tup)
                    errCount += 1
                    
                    if self.LineFlagAttributeId is not None:
                        line[self.LineFlagAttributeId] = 1
                    
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            print ("Checking transit segments")
            self.TRACKER.startProcess(network.element_totals['transit_segments'])
            for segment in network.transit_segments():
                errors = []
                
                ttf = "ft%s" %segment.transit_time_func
                if segment.transit_time_func != 0 and not ttf in functions:
                    errors.append("Segment TTF not in databank: %s" %ttf)
                    errCount += 1
                
                if segment.transit_time_func == 1 and segment.data1 == 0:
                    errors.append("ROW-A segment speed (US1) is 0.")
                    errCount += 1
                
                if errors:
                    tup = ('TRANSIT_SEGMENT', str(segment), errors)
                    issues.append(tup)
                    
                    if self.SegmentFlagAttributeId is not None:
                        segment[self.SegmentFlagAttributeId] = 1
                    
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            print ("Checking turns")
            self.TRACKER.startProcess(network.element_totals['turns'])
            for turn in network.turns():
                if turn.penalty_func > 0:
                    tpf = "fp%s" %turn.penalty_func
                    if not tpf in functions:
                        tup = ('TURN', str(turn), ["Turn TPF not in databank: %s" %tpf])
                        issues.append(tup)
                        errCount += 1
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            if errCount > 0:
                self._WriteReport(issues, errCount)
            
                if self.LineFlagAttributeId is not None or self.LinkFlagAttributeId is not None \
                        or self.SegmentFlagAttributeId is not None:
                    self.Scenario.publish_network(network)
                    print ("Saved network flags")
                
                return errCount
            return 0
            
    ##########################################################################################################    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version,
                "Link attribute": self.LinkFlagAttributeId,
                "Line attribute": self.LineFlagAttributeId,
                "Segment attribute": self.SegmentFlagAttributeId,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _WriteReport(self, issues, errCount):
        
        print ("Writing report to logbook")
        pb = _m.PageBuilder(title="Network Integrity Report for Scenario %s" %self.Scenario.number,
                            description="Tool found %s errors in the network for scenario %s. These \
                            errors are likely to cause infinite loops or division-by-zero errors \
                            when running road or transit assignments, so it is highly recommended \
                            that they are fixed before running any assignments." %(errCount, self.Scenario.number))
        
        doc = '''
        <table align="center">
            <tr>
                <th>Element Type</th>
                <th>ID</th>
                <th>Problem</th>
            </tr>
        '''
        
        self.TRACKER.startProcess(errCount)
        for type, id, list in issues:
            for problem in list:
                doc += '''
                <tr>
                    <td>{typ}</td>
                    <td>{id}</td>
                    <td>{prob}</td>
                </tr>
                '''.format(typ=type, id=id, prob=problem)
                self.TRACKER.completeSubtask()
        doc += '</table>'
        
        pb.wrap_html(body=doc)
        
        _m.logbook_write("%s problems found" %errCount, value= pb.render())
        print ("Done.")

    @_m.method(return_type=six.u)
    def _GetLinkExtraAttributes(self):
        keyvals = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'LINK':
                continue
            descr = "{id} - {desc}".format(id=att.id, desc=att.description)
            keyvals[att.id] = descr
        
        options = []
        for tuple in keyvals.iteritems():
            html = '<option value="%s">%s</option>' %tuple
            options.append(html)
            
        return "\n".join(options)

    @_m.method(return_type=six.u)
    def _GetLineExtraAttribute(self):
        keyvals = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'TRANSIT_LINE':
                continue
            descr = "{id} - {desc}".format(id=att.id, desc=att.description)
            keyvals[att.id] = descr
        
        options = []
        for tuple in keyvals.iteritems():
            html = '<option value="%s">%s</option>' %tuple
            options.append(html)
            
        return "\n".join(options)

    @_m.method(return_type=six.u)
    def _GetSegExtraAttributes(self):
        keyvals = {}
        for att in self.Scenario.extra_attributes():
            if att.type != 'TRANSIT_SEGMENT':
                continue
            descr = "{id} - {desc}".format(id=att.id, desc=att.description)
            keyvals[att.id] = descr
        
        options = []
        for tuple in keyvals.iteritems():
            html = '<option value="%s">%s</option>' %tuple
            options.append(html)
            
        return "\n".join(options)

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()

    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        