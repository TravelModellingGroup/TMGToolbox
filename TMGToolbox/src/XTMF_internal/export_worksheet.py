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
[TITLE]

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-10-31 by pkucirek
    
'''

import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from json import loads as parse_json

from inro.emme.desktop.printer import Settings as PrinterSettings
from inro.emme.desktop.types import Box
from inro.emme.desktop.exception import InvalidParameterNameError
import inro.modeller as _m
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

def load_emme_view(filepath):
    '''
    This function will load an Emme View File (*.emv) and return a Box
    type (required by Worksheet to set the current view).
    
    This code was provided directly by INRO. Thanks to Kevin Bragg for this!
    '''
    with open(filepath) as reader:
        reader.readline() #Toss the header
        contents = {}
        for line in reader:
            if not line.startswith("#"):
                tokens = line.split('=', 1)
                if len(tokens) <= 1:
                   tokens = line.split(':', 1)
                if len(tokens) > 1:
                   contents[tokens[0].strip()] = tokens[1].strip()
    if "BoundingBox" in contents:
        x1, y1, x2, y2 = [float(x) for x in contents["BoundingBox"].split(";")]
    elif "XMin" in contents:
        x1 = float(contents["XMin"]) 
        y1 = float(contents["YMin"])
        x2 = float(contents["XMax"])
        y2 = float(contents["YMax"])
    else:
        raise Exception("file %s: not a valid Emme view file" % file_name)
    
    return Box(x1, y1, x2, y2)


class ExportWorksheet(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    
    xtmf_WorksheetPath = _m.Attribute(str)
    xtmf_ExportPath = _m.Attribute(str)
    
    xtmf_ViewConfig = _m.Attribute(str)
    xtmf_PrinterConfig = _m.Attribute(str)
    xtmf_ParameterConfig = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    #PARAMETERS
    [{'LayerType': 'Link base',
       'ParName': 'Offset',
       'Value': '3',
       'Index': '0'}]
    
    #PAPER SIZES
    {'Type': 'NamedSize',
     'Name': 'LETTER'}
    
    {'Type': 'CustomSize',
     'Width': '8.5',
      'Height': '11',
      'Units': 'INCHES'}
    
    #VIEWS
    {'Type': 'NamedView',
     'Named': 'SomeViewName'}
    
    {'Type': 'FileView',
     'Path': 'D:/somefolder/somefile.emv'}
    
    {'Type': 'CustomView',
     'X0': '1.2',
     'Y0': '3.4',
     'X1': '5.6',
     'Y1': '7.8'}
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="[TOOL NAME] v%s" %self.version,
                     description="[DESCRIPTION]",
                     branding_text="- TMG Toolbox",
                     runnable= False)
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        return pb.render()
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def short_description(self):
        return "<em>Tool is under construction.</em>"
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber):
        
        raise NotImplementedError()
        
        #---1 Set up scenario
        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if (self.Scenario == None):
            raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
        return
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            desktop = _MODELLER.desktop
            
            #Set the primary scenario
            data_explorer = desktop.data_explorer()
            sc = data_explorer.scenario_by_number(self.xtmf_ScenarioNumber)
            data_explorer.replace_primary_scenario(sc)
            
            #Open the worksheet
            ws = desktop.open_worksheet(self.xtmf_WorksheetPath)
            
            

    ##########################################################################################################
    
    #----Sub functions
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadView(self):
        pass
    
    def _LoadCustomView(self, config):
        x0 = config['X0']
        y0 = config['Y0']
        x1 = config['X1']
        y1 = config['Y1']
        
        return Box(x0, y0, x1, y1)
    
    def _LoadViewFile(self):
        pass
    
    def _LoadPrinterSetting(self):
        config = parse_json(self.xtmf_PrinterConfig)
        
        ps = PrinterSettings()
        ps.orientation = config['Orientation']
        
        config_type = config['Type']
        if config_type == "NamedSize":
            ps.set_standard_paper(config['Name'])
        elif config_type == "CustomSize":
            w = config['Width']
            h = config['Height']
            units = config['Units']
            ps.set_custom_paper(w, h, units)
        else:
            raise IOError("Unreocgnized printer config type '%s'" %config_type)
        
        return ps
    
    def _SetParameter(self, worksheet, layer_type, layer_name, parameter_name, value):
        '''
        One of layer_type or layer_name CAN be None, but not both. Alternatively,
        both can be specified.
        '''
        try:
            layer = worksheet.layer(layer_type, layer_name)
        except TypeError:            raise Exception("Cannot load layer from worksheet. Either a layer name or layer type must be specified.")
        except AssertionError:
            raise Exception("Could not find a layer with the name '%s' of the type '%s'" %(layer_name, layer_type))
        
        parameter = layer.par(parameter_name)
        try:
            param_type = type(parameter.get())
            new_value = param_type(value) #Cast the value, which comes as a string, to the correct type
            parameter.set(new_value)
        except InvalidParameterNameError:
            tup = (parameter_name, layer_name, layer_type)
            raise Exception("Could not find a parameter with the name '%s' in layer '%s' of type '%s'" %tup)
        