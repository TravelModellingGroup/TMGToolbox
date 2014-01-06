#---METADATA---------------------
'''
Import Network Package

    Authors: Peter Kucirek
 
    Latest revision by: pkucirek 
    
    
    Imports a compressed network package file.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created
    
    0.2.0 Added the ability to read in exported extra attributes
    
    0.2.1 Set up small javascript to suggest a scenario description based on the network
            package file name
            
    0.1.1 Downgraded from 2.1  to work with the EMME/3 Modeller Beta
    
    0.1.2 Updated to import NWP v2 files (see the main branch)
    
    0.1.3 Minor update to check for null export file
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import zipfile as _zipfile
from os import path as _path
import os as _os
import shutil as _shutil
import tempfile as _tf
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')


##########################################################################################################

class ImportNetworkPackage(_m.Tool()):
    
    version = '0.1.3'
    tool_run_msg = ""
    number_of_tasks = 8 # For progress reporting, enter the integer number of tasks here
    
    __components = ['modes.201', 'vehicles.202', 'base.211', 'transit.221', 'turns.231', 'shapes.251']
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    ScenarioId = _m.Attribute(int) # common variable or parameter
    NetworkPackageFile = _m.Attribute(str)
    ScenarioDescription = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.ScenarioId = -1
        self.ScenarioDescription = ""
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Import Network Package v%s" %self.version,
                     description="Imports a new scenario from a compressed network package \
                             (*.nwp) file.\
                             <br><br><font color='red'>\
                             This version is downgraded to work with the Modeller Beta Release \
                             in Emme 3.4.2</font>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_file(tool_attribute_name='NetworkPackageFile',
                           window_type='file',
                           title="Network Pasckage File",
                           file_filter='*.nwp',
                           start_path=_path.dirname(_MODELLER.desktop.project_file_name()))
        
        pb.add_new_scenario_select(tool_attribute_name='ScenarioId',
                                  title="New Scenario Number",
                                  note="'Next' picks the next available scenario.")
        
        pb.add_text_box(tool_attribute_name='ScenarioDescription',
                        size=60,
                        title="Scenario description")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if self.NetworkPackageFile == None:
            raise IOError("Import file not specified")
        
        if self.ScenarioId < 0:
            self.ScenarioId = _util.getAvailableScenarioNumber()
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done. Scenario %s created." %self.ScenarioId)
    
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            #Only need the EMME/3 namespaces
            importModeTool = _MODELLER.tool('inro.emme.standard.data.network.mode.mode_transaction')
            importVehicleTool = _MODELLER.tool('inro.emme.standard.data.network.transit.vehicle_transaction')
            importBaseNetworkTool = _MODELLER.tool('inro.emme.standard.data.network.base.base_network_transaction')
            importLinkShapeTool = _MODELLER.tool('inro.emme.standard.data.network.base.link_shape_transaction')
            importTransitTool = _MODELLER.tool('inro.emme.standard.data.network.transit.transit_line_transaction')
            importTurnTool = _MODELLER.tool('inro.emme.standard.data.network.turn.turn_transaction')
            
            with nested(self._zipFileMANAGER(), self._TempDirectoryMANAGER()) as (zf, tempFolder):
                
                self._CheckNetworkPackage(zf) #Check the file format.
                
                baseName = _path.splitext(_path.basename(self.NetworkPackageFile))[0] # Get the base name for file contents
                
                scenario = _MODELLER.emmebank.create_scenario(self.ScenarioId)
                scenario.title = self.ScenarioDescription
                
                _m.logbook_write("Created new scenario %s" %self.ScenarioId)
                self.TRACKER.completeTask()
                
                with _m.logbook_trace("Reading modes"):
                    zf.extract(self.__components[0], tempFolder)
                    self.TRACKER.runTool(importModeTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[0]),
                                         scenario=scenario)
                
                with _m.logbook_trace("Reading vehicles"):
                    zf.extract(self.__components[1], tempFolder)
                    self.TRACKER.runTool(importVehicleTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[1]),
                                         scenario=scenario)
                
                with _m.logbook_trace("Reading base network"):
                    zf.extract(self.__components[2], tempFolder)
                    self.TRACKER.runTool(importBaseNetworkTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[2]),
                                         scenario=scenario)
                
                with _m.logbook_trace("Reading link shapes"):
                    zf.extract(self.__components[5], tempFolder)
                    self.TRACKER.runTool(importLinkShapeTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[5]),
                                         scenario=scenario)
                    
                with _m.logbook_trace("Reading transit lines"):
                    zf.extract(self.__components[3], tempFolder)
                    self.TRACKER.runTool(importTransitTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[3]),
                                         scenario=scenario)
                
                with _m.logbook_trace("Reading turns"):
                    zf.extract(self.__components[4], tempFolder)
                    self.TRACKER.runTool(importTurnTool,
                                         transaction_file="%s/%s" %(tempFolder, self.__components[4]),
                                         scenario=scenario)
                        

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _zipFileMANAGER(self):
        # Code here is executed upon entry {
        zf = _zipfile.ZipFile(self.NetworkPackageFile)
        # }
        try:
            yield zf
        finally:
            zf.close()
    
    @contextmanager
    def _TempDirectoryMANAGER(self):
        foldername = _tf.mkdtemp()
        _m.logbook_write("Created temporary directory at '%s'" %foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            #_os.removedirs(foldername)
            _m.logbook_write("Deleted temporary directory at '%s'" %foldername)
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _CheckNetworkPackage(self, package):
        contents = package.namelist()
        
        if 'version.txt' in contents:
            self.__components = ['modes.201', 'vehicles.202', 'base.211', 'transit.221', 'turns.231', 'shapes.251']
        
        renumberCount = 0
        for component in contents:
            if component.endswith(".201"):
                self.__components[0] = component
                renumberCount += 1
            elif component.endswith(".202"):
                self.__components[1] = component
                renumberCount += 1
            elif component.endswith(".211"):
                self.__components[2] = component
                renumberCount += 1
            elif component.endswith(".221"):
                self.__components[3] = component
                renumberCount += 1
            elif component.endswith(".231"):
                self.__components[4] = component
                renumberCount += 1
            elif component.endswith(".251"):
                self.__components[5] = component
                renumberCount += 1
        if renumberCount != 6:
            raise IOError("File appears to be missing some components. Please contact TMG for assistance.")
    
    def _GetAtts(self):
        atts = {
                "Scenario" : self.ScenarioId,
                "Import File": self.NetworkPackageFile, 
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _LoadExtraAttributes(self, zf, tempFolder, scenario):
        zf.extract("exatts.241", tempFolder)
        types = set()
        with open(tempFolder + "/exatts.241") as reader:
            reader.readline() #toss first line
            for line in reader.readlines():
                cells = line.split(',',3)
                att = scenario.create_extra_attribute(cells[1], cells[0], default_value=float(cells[2]))
                att.description = cells[3].strip().strip("'") 
                #strip called twice: once to remove the '\n' character, and once to remove both ' characters
                types.add(att.type)
        
        return types
            

    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    
    
    