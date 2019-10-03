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

import os
import time
import math
import inro.modeller as _m
import traceback as _traceback

class CalculateStationFrequency(_m.Tool()):
    
    Scenario = _m.Attribute(_m.InstanceType)
    ScenarioId = _m.Attribute(str)
    Mode= _m.Attribute(str)
    ModeType = _m.Attribute(_m.InstanceType)
    FileName = _m.Attribute(str)
    tool_run_msg = ""
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="CalculateStationFrequency",
                     description="Calculates the number of transit vehicles passing by station centroids.",
                            branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select scenario",
                               allow_none=False)
        
        pb.add_select_mode(tool_attribute_name="ModeType",
                           title="Select mode",
                           filter=["TRANSIT"],
                           note="Select a mode with station centroids (e.g., subway)",
                           allow_none=False)
        
        pb.add_select_file(tool_attribute_name="FileName",
                            window_type="save_file",
                            file_filter="*.txt",
                            start_path="C:/",
                            title="Save file",
                            note="Select a text file to save.")
        #_m.Modeller().desktop.project_file_name()
        
        return pb.render()
                    
    
    def run(self):
        self.tool_run_msg = ""
        
        try:
            s = self(self.Scenario.id, self.ModeType.id, self.FileName)
            self.tool_run_msg = _m.PageBuilder.format_info(s)
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    def __call__(self, ScenarioId, Mode, FileName):
        
        #---TODO: Validate variables!
        
        Scenario = _m.Modeller().emmebank.scenario(ScenarioId)
        if (Scenario is None):
            raise Exception("Could not find scenario %s" %ScenarioId)
        
        Network = Scenario.get_network()
        
        #---Primary logic
        _i = 0 #Selected lines
        _total_lines = 0
        StationFrequency = {} #blank dictionary.
        ParkingCapacity = {} #blank dictionary.
        FreqAttribute = {}
        for Line in Network.transit_lines():
            _total_lines += 1
            if (Line.mode.id == Mode):
                _i += 1
                # Line is of the selected mode
                Freq = (60.0 / Line.headway)
                Frequency = 0
                if (Freq - int(Freq)) > 0:
                    Frequency = int(Freq) + 1
                else:
                    Frequency = Freq  
                
                # Loop through all stops served by this line
                for Stop in Line.itinerary():
                    Station = None
                    for Link in Stop.outgoing_links():
                        if (Link.j_node.is_centroid):
                            Station = Link.j_node
                    
                    # Stop has a corresponding station centroid
                    if (not Station is None):
                        # Add this line's number of trains to the existing map.
                        if (Station.id in StationFrequency):
                            StationFrequency[Station.id] = StationFrequency[Station.id] + Frequency
                        else:
                            StationFrequency[Station.id] = Frequency
                            ParkingCapacity[Station.id] = Station["@pkcap"]
                            FreqAttribute[Station.id] = Station["@freq"]
                        
        #---Save results
        File = open(FileName, "w")
        File.write("Zone,frequency,@freq,@pkcap")
        for key, value in StationFrequency.iteritems():
            _pkcap = ParkingCapacity[key]
            _freq = FreqAttribute[key]
            File.write("\n%s,%s,%s,%s"% (key, value, _freq, _pkcap))
        File.close()
        
        return "Tool complete. %i out of %i lines were selected." %(_i, _total_lines)
        
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        
        
        