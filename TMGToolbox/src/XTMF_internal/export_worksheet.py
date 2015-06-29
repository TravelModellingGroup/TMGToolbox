#---LICENSE----------------------
'''
    Copyright 2014-2015 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
from os import path as _path
import re as _re

from inro.emme.desktop.printer import Settings as PrinterSettings
from inro.emme.desktop.types import Box, Margins
from inro.emme.desktop.exception import InvalidParameterNameError
import inro.modeller as _m
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class ExportWorksheet(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    #---PARAMETERS
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    
    xtmf_WorksheetPath = _m.Attribute(str)
    xtmf_ExportPath = _m.Attribute(str)
    
    xtmf_ConfigString = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Emme Worksheet v%s" %self.version,
                     description="Cannot be called from Modeller",
                     branding_text="- TMG Toolbox",
                     runnable= False)
        
        return pb.render()
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def short_description(self):
        return "<em>Allows XTMF to export worksheets to file.</em>"
    
    #---
    #---XTMF INTERFACE METHODS
    
    def __call__(self, xtmf_ScenarioNumber, xtmf_WorksheetPath, xtmf_ExportPath, xtmf_ConfigString):
        
        #raise NotImplementedError()
        emme_desktop = _MODELLER.desktop        
        
        try:
            scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
            if scenario == None:
                raise Exception("Emme scenario %s not found." %xtmf_ScenarioNumber)
            
            worksheet = emme_desktop.open_worksheet(xtmf_WorksheetPath)
            export_path = xtmf_ExportPath
            
            #Replace single quotes with doubles and backslashes with forwardslashes
            modified_config = xtmf_ConfigString.replace("'", '"').replace('\\', '/')
            try:
                config = parse_json(modified_config)
            except:
                print modified_config
                raise
            
            self._execute(scenario, worksheet, export_path, config)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
        return
    
    ##########################################################################################################    
    
    #---
    #---MAIN EXECUTION CODE
    
    def _execute(self, scenario, worksheet, export_path, config):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._get_atts()):
            desktop = _MODELLER.desktop
            
            #---1. Set the primary scenario
            data_explorer = desktop.data_explorer()
            db = data_explorer.active_database()
            sc = db.scenario_by_number(scenario.number)
            data_explorer.replace_primary_scenario(sc)
            
            #---2. Load the view
            view_config = config['view']
            view_box = self._set_view(worksheet, view_config)
            
            #---3. Set any parameters This is performed AFTER setting the view, in case any parameters sync with the view
            for param_config in config['parameters']:
                par_name = param_config['par_name']
                
                layer_name = ''
                layer_type = ''
                if 'layer_name' in param_config: layer_name = param_config['layer_name']
                if 'layer_type' in param_config: layer_type = param_config['layer_type']
                
                val = param_config['value']
                index = int(param_config['index'])
                
                self._set_parameter(worksheet, layer_type, layer_name, par_name, val, index)
            
            #---4. Finally, export the worksheet
            export_config = config['export_type']
            export_type = export_config['type']
            
            image_types = {'JPEGType': '.jpg', 'PNGType':'.png', 'BMPType':'.bmp'}
            if export_type in image_types:
                export_path = _path.splitext(export_path)[0] + image_types[export_type]
                self._export_image(worksheet, export_config, export_path)
            elif export_type == 'PDFExportType':
                export_path = _path.splitext(export_path)[0] + '.pdf'
                self._export_pdf(worksheet, export_config, export_path)
            elif export_type == 'SVGExportType':
                export_path = _path.splitext(export_path)[0] + '.svg'
                self._export_svg(worksheet, export_config, export_path)
            else:
                raise NameError("Worksheet export type '%s' not recognized" %export_type)
            
            

    ##########################################################################################################
    
    #----Sub functions
    
    @staticmethod
    def _read_margin(cfg):
        '''
        Super lazy method for loading in margins from config dicts
        '''
        margins_data = [cfg['margin_%s' %key] for key in 'left,top,right,bottom'.split(',')]
        return Margins(margins_data)
    
    def _get_atts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _set_view(self, worksheet, config):
        if not config:
            worksheet.full_view()
            return
        
        view_type = config['type']
        if view_type == 'BOX': box = self._load_view_from_config(config)
        elif view_type == 'FILE': box = self._load_view_from_file(config)
        elif view_type == 'EXPLORER': box = self._load_View_from_project(config)
        else:
            raise TypeError("Unrecognized view type %s" %view_type)
        
        worksheet.set_view(box)
    
    def _load_view_from_config(self, config):
        x0, x1, y0, y1 = [config[att] for att in 'x0 x1 y0 y1'.split()]
        return Box(x0, y0, x1, y1)
    
    def _load_View_from_project(self, config):
        emme_application = _MODELLER.desktop
        explorer = emme_application.root_view_folder()
        
        path = _re.split(" *; *", config['parent_folders'])
        
        if len(path) == 1 and path[0] == '': path.pop() #If the pathstring is empty or whitespace, reset the path list to empty.
        
        path.append(config['name']) #Add the item name to the end of the list
        
        view_item = explorer.find_item(path)
        if type(view_item) ==  type(None): #For some reason the __eq__ operator overload for ViewItem doesn't support check against None
            raise IOError("Could not find a Named View within the project folder at path %s" %path)
        return view_item.get_box()
    
    def _load_view_from_file(self, config):
        '''
        This function will load an Emme View File (*.emv) and return a Box
        type (required by Worksheet to set the current view).
        
        This code was provided directly by INRO. Thanks to Kevin Bragg for this!
        '''
        
        filepath = config['file_path']
        
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
            raise Exception("file %s: not a valid Emme view file" % filepath)
        
        return Box(x1, y1, x2, y2)
    
    def _set_parameter(self, worksheet, layer_type, layer_name, parameter_name, value, index=0):
        '''
        One of layer_type or layer_name CAN be None. Alternatively,
        both can be specified.
        '''
        try:
            layer = worksheet.layer(layer_type, layer_name)
        except TypeError:            
            raise RuntimeError("Cannot load layer from worksheet. Either a layer name or layer type must be specified.")
        
        if layer is None:
            print type(worksheet)
            print type(layer)
            print layer_type, type(layer_type)
            print layer_name, type(layer_name)
            raise NameError("Could not find a layer of type '%s' with name '%s'" %(layer_type, layer_name))
        
        parameter = layer.par(parameter_name)
        try:
            original_value = parameter.get(index)
            param_type = type(original_value)
            new_value = param_type(value) #Cast the value, which comes as a string, to the correct type
            
            parameter.set(new_value, index)
        except InvalidParameterNameError:
            tup = (parameter_name, layer_name, layer_type)
            raise Exception("Could not find a parameter with the name '%s' in layer '%s' of type '%s'" %tup)
    
    def _export_image(self, worksheet, config, filepath):
        
        size = config['width'], config['height']
        detail = config['detail']
        
        margins = self._read_margin(config)
        
        if 'quality' in config: quality = config['quality']
        else: quality = 90
        
        worksheet.save_as_image(filepath, size, quality, detail, margins)
    
    def _export_pdf(self, worksheet, config, filepath):
        psettings = PrinterSettings()
        
        psettings.margins = self._read_margin(config)
        psettings.extend_to_margins = config['extend_to_margins']
        psettings.orientation = config['orientation']
        psettings.detail = config['detail']
        
        if config['paper_size'] == 'CUSTOM':
            w, h = config['width'], config['height']
            unit = config['unit']
            psettings.set_custom_paper(w, h, unit)
        else: psettings.set_standard_paper(config['paper_size'])
        
        worksheet.save_as_pdf(filepath, psettings)
    
    def _export_svg(self, worksheet, config, filepath):
        size = config['width'], config['height']
        unit = config['unit']
        margins = self._read_margin(config)
        detail = config['detail']
        
        worksheet.save_as_svg(filepath, size, unit, detail, margins)