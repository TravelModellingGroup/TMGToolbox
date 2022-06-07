#---LICENSE----------------------
'''
    Copyright 2014-2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
Export Countpost Results

    Authors: byusuf

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-16 by pkucirek
    
    0.0.2 Modified to properly append the file extension.
    
    1.0.0 Upgraded for release: Now works with util.fastLoadLinkAttributes.
    
    1.1.0 Added new feature to optionally select an alternate countpost attribute.
            Also, now countpost results will be reported in increasing order.
    
    1.1.1 Fixed a bug in the tool page Javascript

    1.1.2 Added additional functionality for XTMF
    
    1.1.3 Added checks to make sure the alternative countpost attribute is not used form XTMF if
          there is a blank string.
'''

import inro.modeller as _m
import traceback as _traceback
import csv
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
NullPointerException = _util.NullPointerException
# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ExportCountpostResults(_m.Tool()):
    
    version = '1.1.3'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    
    CountpostAttributeId = _m.Attribute(str)
    AlternateCountpostAttributeId = _m.Attribute(str)
    TrafficClassAttributeId = _m.Attribute(str)
    SumPostFile = _m.Attribute(str)
    ExportFile = _m.Attribute(str)
    version = '1.1.2'
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
        self.CountpostAttributeId = "@stn1"
        self.AlternateCountpostAttributeId = "@stn2"        
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Countpost Results v%s" %self.version,
                     description="Exports traffic assignment results on links flagged with \
                         a countpost number.",
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
        
        pb.add_select(tool_attribute_name='CountpostAttributeId',
                      keyvalues=keyval1,
                      title="Countpost Attribute",
                      note="LINK attribute containing countpost id numbers")
        
        pb.add_select(tool_attribute_name='AlternateCountpostAttributeId',
                      keyvalues=keyval2,
                      title="Alternate Countpost Attribute",
                      note="<font color='green'><b>Optional:</b></font> Alternate countpost attribute \
                      for multiple post per link")
        pb.add_select(tool_attribute_name='TrafficClassAttributeId',
                      keyvalues=keyval2,
                      title="Volume Attribute to Use",
                      note="<font color='green'><b>Optional:</b></font> Alternate countpost attribute \
                      for multiple post per link")

        pb.add_select_file(tool_attribute_name='SumPostFile',
                           window_type='file',
                           file_filter="*.csv",
                           title="File with the Posts to Sum",
                           note = "<font color='green'><b>Optional:</b></font> If more than one link has the \
                           same count post number, the default behaviour is to take the maximum volume of all the links.\
                           Use this file to specify the countposts that should be summed in order to obtain \
                           the correct volume for the station")
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           window_type='save_file',
                           file_filter="*.csv",
                           title="Export File")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            
            $("#CountpostAttributeId")
                .empty()
                .append(tool.preload_scenario_attributes())
            inro.modeller.page.preload("#CountpostAttributeId");
            $("#CountpostAttributeId").trigger('change');
            
            $("#AlternateCountpostAttributeId")
                .empty()
                .append("<option value='-1'>None - No attribute</option>")
                .append(tool.preload_scenario_attributes())
            inro.modeller.page.preload("#AlternateCountpostAttributeId");
            $("#AlternateCountpostAttributeId").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        
        return pb.render()
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
       
    @_m.method(return_type=six.u)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    @_m.method(return_type=six.u)
    def preload_scenario_attributes(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            label = "{id} - {name}".format(id=att.name, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        try:
            if not self.Scenario.has_traffic_results:
                raise Exception("Scenario %s has no traffic assignment results" %self.Scenario.number)
            
            if self.CountpostAttributeId is None: raise NullPointerException("Countpost Attribute not specified")
            if self.ExportFile is None: raise NullPointerException("Export File not specified")
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise    
        
        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc())
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
                
    def __call__(self, xtmf_ScenarioNumber, CountpostAttributeId, AlternateCountpostAttributeId, TrafficClassAttributeId, SumPostFile,
                 ExportFile):
        
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario is None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        if not self.Scenario.has_traffic_results:
            raise Exception("Scenario %s has no traffic assignment results" %self.Scenario.number)
        
        linkAtts = set([att.id for att in self.Scenario.extra_attributes() if att.type == 'LINK'])
        
        if not CountpostAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %CountpostAttributeId)
        if AlternateCountpostAttributeId != "" and not AlternateCountpostAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %AlternateCountpostAttributeId)
        if TrafficClassAttributeId != "" and str(TrafficClassAttributeId).strip().lower() != "none" and not TrafficClassAttributeId in linkAtts:
            raise NullPointerException("'%s' is not a valid link attribute" %TrafficClassAttributeId)
        if TrafficClassAttributeId == "" or str(TrafficClassAttributeId).strip().lower() == "none":
            self.TrafficClassAttributeId = None
        else:
            self.TrafficClassAttributeId = TrafficClassAttributeId
        if SumPostFile == "" or str(SumPostFile).strip().lower() == "none":
            self.SumPostFile = None
        else:
            self.SumPostFile = SumPostFile
        self.CountpostAttributeId = CountpostAttributeId
        self.AlternateCountpostAttributeId = AlternateCountpostAttributeId
        self.ExportFile = ExportFile
        
        try:
            self._Execute()
        except Exception as e:
            msg = str(e) + "\n" + _traceback.format_exc()
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            self.TRACKER.reset()
            if self.TrafficClassAttributeId != None:
                linkResults = _util.fastLoadLinkAttributes(self.Scenario, [self.CountpostAttributeId,
                                                                           self.TrafficClassAttributeId,
                                                                       'auto_volume',
                                                                       'additional_volume',
                                                                       'auto_time'])
            else:
                linkResults = _util.fastLoadLinkAttributes(self.Scenario, [self.CountpostAttributeId,
                                                                       'auto_volume',
                                                                       'additional_volume',
                                                                       'auto_time'])
            
            alternateLinkResults = {}
            if self.AlternateCountpostAttributeId and self.AlternateCountpostAttributeId != "":
                alternateLinkResults = _util.fastLoadLinkAttributes(self.Scenario, 
                                                                    [self.AlternateCountpostAttributeId])
            
            #Remove entries not flagged with a countpost
            self._CleanResults(linkResults, alternateLinkResults)
            
            #Get the countpost data, sorted
            lines = self._ProcessResults(linkResults, alternateLinkResults)
            
            #Write countpost data to file
            self._WriteReport(lines)
            

    ##########################################################################################################
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Countpost Attribute": self.CountpostAttributeId,
                "Alternate Countpost Attribute": self.AlternateCountpostAttributeId,
                "Export File": self.ExportFile,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _CleanResults(self, linkResults, alternateLinkResults):
        idsToRemove = []
        for linkId, attributes in six.iteritems(linkResults):
            post1 = attributes[self.CountpostAttributeId]
            post2 = 0
            if linkId in alternateLinkResults:
                post2 = alternateLinkResults[linkId][self.AlternateCountpostAttributeId] 
            
            if not post1 and not post2:
                idsToRemove.append(linkId)
        for key in idsToRemove:
            linkResults.pop(key) 
    
    def _ProcessResults(self, linkResults, alternateLinkResults):
        #lines = []
        lines = {}
        posts = 0
        self.TRACKER.startProcess(len(linkResults))

        for linkIdTuple, attributes in six.iteritems(linkResults):
            linkId = "%s-%s" %linkIdTuple

            post1 = attributes[self.CountpostAttributeId]
            post2 = 0
            if linkIdTuple in alternateLinkResults:
                post2 = alternateLinkResults[linkIdTuple][self.AlternateCountpostAttributeId]
            volau = attributes['auto_volume']
            volad = attributes['additional_volume']
            timau = attributes['auto_time']
            if self.TrafficClassAttributeId is not None:
                class_volume = attributes[self.TrafficClassAttributeId]
            
            data = [linkId, volau, volad, timau, class_volume]
            
            #if post1:
            #    lines.append((post1, linkId, volau, volad, timau))
            #if post2:
            #    lines.append((post2, linkId, volau, volad, timau))
            sumPosts = []
            if self.SumPostFile is not None:
                with open(self.SumPostFile) as sumPostFile:
                    reader = csv.reader(sumPostFile)
                    firstRow = six.next(reader)
                    for row in reader:
                        sumPosts.append(int(row[0]))
            if post1:
                if post1 in lines.keys():
                    if post1 in sumPosts:
                        if self.TrafficClassAttributeId is not None: 
                            lines[post1] += class_volume
                        else:
                            lines[post1] += volau
                    else:
                        if self.TrafficClassAttributeId is not None: 
                            max_vol = max(lines[post1], class_volume)
                            lines[post1] = max_vol
                        else:
                            max_vol = max(lines[post1], volau)
                            lines[post1] = max_vol

                else:
                    if self.TrafficClassAttributeId is not None:
                        lines[post1] = class_volume
                    else:
                        lines[post1] = volau
            if post2:
                if post2 in lines.keys():
                    if post2 in sumPosts:
                        if self.TrafficClassAttributeId is not None: 
                            lines[post2] += class_volume
                        else:
                            lines[post2] += volau
                    else:
                        if self.TrafficClassAttributeId is not None: 
                            max_vol = max(lines[post2], class_volume)
                            lines[post2] = max_vol
                        else:
                            max_vol = max(lines[post2], volau)
                            lines[post2] = max_vol

                else:
                    if self.TrafficClassAttributeId is not None:
                        lines[post2] = class_volume
                    else:
                        lines[post2] = volau

            self.TRACKER.completeSubtask()
        _m.logbook_write("Found %s countposts in network" %posts)
        #lines.sort()
        return lines
    
    def _WriteReport(self, lines):
        with open(self.ExportFile, 'w', newline='') as csv_file:
            writer = csv.writer(csv_file, delimiter = ',')
            #writer.writerow("Countpost,Link,Auto Volume,Additional Volume,Auto Time")
            #for line in lines:
            #    line = [str(c) for c in line]
            #    writer.writerow(line)'''
            writer.writerow(["Countpost","Auto Volume"])
            for post in sorted(six.iterkeys(lines)):
                post = int(post)
                volau = float(lines[post])
                writer.writerow([post, volau])
        _m.logbook_write("Wrote report to %s" %self.ExportFile)