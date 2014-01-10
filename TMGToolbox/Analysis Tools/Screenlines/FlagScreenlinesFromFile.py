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

from os import path as _p
import inro.modeller as _m
import traceback as _traceback
_slc = _m.Modeller().module('TMG2.Common.Screenline')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')
_util = _m.Modeller().module('TMG2.Common.Utilities')

class FlagScreenlinesFromFile(_m.Tool()):
    
    version = '0.1.1'
    tool_run_msg = ""
    _warnings = ""
    
    ScreenlineFile = _m.Attribute(str)
    ScenarioNumber = _m.Attribute(int)
    OverwriteConflictedAttributes = _m.Attribute(bool)
    
    scenario = _m.Attribute(_m.InstanceType)
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Flag Screenlines as Attribute",
                     description="Loads a screenlines file (as a shapefile) and saves its \
                         links to an extra attribute. Each screenline gets its own attribute, \
                         based on the 'Id' attribute contained in the shapefile; with links \
                         crossing in the positive direction being flagged as '1', and links \
                         crossing in the negative direction being flagged as '-1'.\
                         \
                         <br><br>As this tool creates multiple attributes (one for each \
                         screenline defined), it is import to ensure that <b>the databank contains \
                         enough space</b> for the number of screenlines to be loaded.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name='scenario',
                               title="Select scenario:")
        
        pb.add_select_file(tool_attribute_name="ScreenlineFile",
                           window_type="file", file_filter="*.shp",
                           title="Select screenlines file to open.")
        
        pb.add_checkbox(tool_attribute_name="OverwriteConflictedAttributes",
                        title="Overwrite Conflicted Attributes?",
                        note="If checked, this tool will overwrite values of \
                        link attributes with the same id as a screenline in \
                        the file.")
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        #Fix the checkbox problem
        if self.OverwriteConflictedAttributes == None: #If the checkbox hasn't been clicked, this variable will be set to None by Modeller
            self.OverwriteConflictedAttributes = False
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    def __call__(self, ScreenlineFile, OverwriteConflictedAttributes):
        #Set up scenario
        self.scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        self.ScreenlineFile = ScreenlineFile
        self.OverwriteConflictedAttributes = OverwriteConflictedAttributes
        
        self.isRunningFromXTMF = True
        
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
    
    def _execute(self):
        with _m.logbook_trace(name="Flag Screenlines from File v%s" %self.version,
                                     attributes={
                                                 "Scenario" : str(self.scenario.id),
                                                 "Screenlines File" : self.ScreenlineFile,
                                                 "Overwriting Conflicting Attributes?" : str(self.OverwriteConflictedAttributes),
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
            
            if self.scenario.modify_protected:
                raise Exception("Scenario %s is protected against modification." %self.scenario.id)
            
            network = self.scenario.get_network()
            lines = _slc.openShp(self.ScreenlineFile, network)

            _m.logbook_write("%s screenlines loaded." %len(lines))
            
            for line in lines.itervalues():
                try:
                    network = self._flagScreenline(network, line)
                except Exception, e:
                    self.scenario.publish_network(network)
                    raise
            
            #---3. Publish network
            self.scenario.publish_network(network)
            self.tool_run_msg = _m.PageBuilder.format_info("Done. %s screenlines were flagged. See logbook \
                                            for a report on attributes created." %len(lines))
    
    def _flagScreenline(self, network, screenline):
        attrId = "@s%s" %screenline.id 
        attrId = _util.truncateString(attrId, 6)
        
        attr = self.scenario.extra_attribute(attrId)
        if attr == None:
            #Attribute does not exist
            attr = self.scenario.create_extra_attribute('LINK', attrId)
            
        elif self.OverwriteConflictedAttributes:
            #Attribute exists, and the overwrite flag is flagged
            attr.initialize(value=0)
            
        else:
            #Attribute exists, but overwrite flag is unflagged
            raise Exception("Attribute '%s' already exists and is not being allowed to be \
                    overwritten. Either enable overwriting or delete this attribute." %attrId)
        
        attr.description = _util.truncateString("SL {0}: {1}".\
                                                format(screenline.id, screenline.name), 40)
        
        network = screenline.saveFlaggedLinksToAttribute(network, attr)
        _m.logbook_write("Flagged Screenline {0} ({1}) as attribute '{2}'".\
                         format(screenline.id, screenline.name, attrId))
        
        return network
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    