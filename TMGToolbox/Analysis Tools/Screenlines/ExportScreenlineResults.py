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

'''
Export Screenline Results TOOL
This tool is intended to export the results of the methods in Screenline Library to a CSV file.
CSV Output format:
Id, Name, Direction, Mode 1, Mode 2...
@author: matthew
@author: pkucirek
'''

import inro.modeller as _m
import traceback as _traceback
import csv as _csv
_s = _m.Modeller().module('TMG2.Common.Screenline')
 
class ExportScreenlineResults(_m.Tool()):
    
    version = '0.1.1'
    
    ## Var Def
    Scenario = _m.Attribute(_m.InstanceType) #scenario
    OpenPath = _m.Attribute(_m.InstanceType) #file open dialog
    SavePath = _m.Attribute(_m.InstanceType) #save location
    
    ModesList = _m.Attribute(_m.ListType)
    
    # XTMF-only vars
    ModesStr = _m.Attribute(_m.InstanceType)
    ScrenarioNumner = _m.Attribute(int)
    
    tool_run_msg = "" #message
    screenlines = {}
    
    def __init__(self):
        pass
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title='Export Screenline Results',
                                description="This tool loads Screenlines from a shapefile and then determines \
                                which links intersect the screenline's geometry. This tool then exports the volume \
                                crossing each element of the screenline and in each direction on that link into a \
                                CSV file. The shapefile's attribute table must contain fields labeled 'Id', 'Descr' \
                                'PosDirName' and 'NegDirName'. Results are written to a text file.",
                                branding_text="TMG")
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        pb.add_select_scenario(tool_attribute_name="Scenario", title='Select a Scenario')
        pb.add_select_file(tool_attribute_name="OpenPath", window_type="file", file_filter="*.shp", title='Select Shape File')
        pb.add_select_file(tool_attribute_name="SavePath", window_type="save_file", title='Select a File to Output Results (CSV)')
        pb.add_select_mode(tool_attribute_name="ModesList", title="Select Specific Modes To Report")
        return pb.render()   
    
                        
    def run(self):
        
        self.tool_run_msg = ""
        
        '''Run is called from Modeller.'''
        self.isRunningFromXTMF = False
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Analysis complete. Results exported to '%s'" %str(self.SavePath))        
    
    def __call__(self, ScrenarioNumner, ModesStr, OpenPath, SavePath):
        #---1 Set up scenario
        self.Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %ScenarioNumber)
        
        #---2 Get modes
        self.ModesList = set()
        net = self.Scenario.get_network()
        for i in range(0, len(ModesStr)):
            m = net.mode(ModesStr[i])
            if m != None:
                self.ModesList.add(m)
        
        #---3 Pass in remaining args
        self.OpenPath = OpenPath
        self.SavePath = SavePath
        
        self.isRunningFromXTMF = True
        
        #---4 Execute the tool
        try:
            self._execute()
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
                
    def _execute(self):
        
        with _m.logbook_trace(name="Export Screenline Results v%s" %self.version,
                                     attributes={
                                                 "Scenario" : str(self.Scenario.id),
                                                 "ModeString" : str(self.ModesList),
                                                 "Screenlines File" : str(self.OpenPath),
                                                 "Results File" : str(self.SavePath),
                                                 "Is running from XTMF?" : str(self.isRunningFromXTMF),
                                                 "self": self.__MODELLER_NAMESPACE__}):
        
            _m.logbook_write("Loading shapefile:'%s'" %self.OpenPath)
            
            network = self.Scenario.get_network()
            screenlines = _s.openShp(self.OpenPath, network)
                              
            with open(self.SavePath, 'wb') as f:
                #---Write metadata
                f.write("SCREENLINE RESULTS")
                f.write("\nScenario: %s" %self.Scenario.id)
                f.write("\nScreenline File: '%s'" %self.OpenPath)
                
                iter = self.ModesList.__iter__()
                s = iter.next().id
                for m in iter:
                    s += ", %s" %m.id
                f.write("\nModes: %s" %s)
                
                #---Summary of auto + transit volumes across screenlines
                f.write("\n\n--Screenline Summary--")
                f.write("\n,DIRECTION 1,,,DIRECTION 2")
                f.write("\nID,DIR,AUTO,TRANSIT,DIR,AUTO,TRANSIT")
                f.write("\n----,----,-------,-------,----,-------,-------")
                for line in screenlines.itervalues():
                    autoVolP = 0.0
                    transVolP= 0.0
                    autoVolN = 0.0
                    transVolN= 0.0
                    for m in self.ModesList:
                        if m.type == "AUTO":
                            autoVolP += line.getPositiveVolume(network, m)
                            autoVolN += line.getNegativeVolume(network, m)
                        elif m.type == "TRANSIT":
                            transVolP += line.getPositiveVolume(network, m)
                            transVolN += line.getNegativeVolume(network, m)
                    f.write("\n{0},{1},{2},{3},{4},{5},{6}\
                            ".format(line.id, line.plusName, autoVolP, transVolP,
                                     line.minusName, autoVolN, transVolN))
                    
                #---Per-line mode-by-mode breakdown
                f.write("\n\n\n--Screenline Details--")
                f.write("\n-------------------------")
                
                for line in screenlines.itervalues():
                    f.write("\n\nScreenline {0}: {1}".format(line.id, line.name))
                    f.write("\n\nMODE,TYPE,{0},{1}".format(line.plusName, line.minusName))
                    f.write("\n------------,----------,----,----")
                    for m in self.ModesList:
                        f.write("\n{0}-{1},{2},{3},{4}\
                                ".format(m.id, m.description, m.type,
                                         line.getPositiveVolume(network, m),
                                         line.getNegativeVolume(network, m)))
                           
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg