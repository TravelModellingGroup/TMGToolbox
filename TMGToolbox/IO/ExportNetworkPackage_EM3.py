#---METADATA---------------------
'''
Export Network Package

    Authors:Peter Kucirek, James Vaughan

    Latest revision by: pkucirek
    
    
    Exports a scenario as a compressed folder of files (*.nwp), which contains
    data about modes, vehicles, base network, transit lines, link shapes, and turns.
    Eventually this will also include extra attribute data (which is optionally
    exported). The ratio of compression tends to be very good, since network batch
    files are just text files. For example, a network of 18419 nodes and 46963 links
    (with 1517 transit lines) takes less than 1MB of storage (And nearly 1GB 
    uncompressed).
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created.
    
    0.2.0 Updated to optionally export extra attributes, using a custom script to update
            the page with the available attributes for the selected scenario. This custom
            script was written and (c) by INRO (see license notice just above the script).
    
    0.1.1 Downgraded from 2.0  to work with the EMME/3 Modeller Beta
    
    0.1.2 Updated to export NWP v2 files (see the main branch)
    
    0.1.3 Minor update to check for null export file
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from os import path as _path
import os as _os
import shutil as _shutil
import zipfile as _zipfile
import tempfile as _tf
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class ExportNetworkPackage(_m.Tool()):
    
    version = '0.1.3'
    tool_run_msg = ""
    number_of_tasks = 6 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    Scenario = _m.Attribute(_m.InstanceType) # common variable or parameter
    ExportFile = _m.Attribute(str)
    AttributeIdsToExport = _m.Attribute(_m.ListType)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Network Package v%s" %self.version,
                     description="Exports all scenario data files (modes, vehicles, nodes, \
                                 links, transit lines, link shape, turns) to a compressed \
                                 network package file (*.nwp).\
                                 <br><br><font color='red'>\
                                 This version is downgraded to work with the Modeller Beta Release \
                                 in Emme 3.4.2, and doesn't export extra attributes.</font>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=False)
        
        pb.add_select_file(tool_attribute_name='ExportFile',
                           title="File name",
                           window_type='save_file',
                           file_filter="*.nwp")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if self.ExportFile == None:
            raise IOError("Export file not specified")
        
        self.ExportFile = _path.splitext(self.ExportFile)[0] + ".nwp"
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done. Scenario exported to %s" %self.ExportFile)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            #Only use the EMME 3 namespaces of these tools
            modeExportTool = _MODELLER.tool('inro.emme.standard.data.network.mode.export_modes')
            vehiclesExportTool = _MODELLER.tool('inro.emme.standard.data.network.transit.export_vehicles')
            baseNetworkExportTool = _MODELLER.tool('inro.emme.standard.data.network.base.export_base_network')
            transitExportTool = _MODELLER.tool('inro.emme.standard.data.network.transit.export_transit_lines')
            linkShapeExportTool = _MODELLER.tool('inro.emme.standard.data.network.base.export_link_shape')
            turnExportTool = _MODELLER.tool('inro.emme.standard.data.network.turn.export_turns')
            
            with nested(self._zipFileMANAGER(), self._TempDirectoryMANAGER()) as (zf, tempFolder):
                verionFile = tempFolder + "/version.txt"
                with open(verionFile, 'w') as writer:
                    writer.write("2.0")
                zf.write(verionFile, arcname="version.txt")
                
                with _m.logbook_trace("Exporting modes"):
                    exportFile = tempFolder + "/modes.201"
                    self.TRACKER.runTool(modeExportTool, 
                                         export_file=exportFile,
                                         scenario=self.Scenario)
                    zf.write(exportFile, arcname=("modes.201"))
                
                with _m.logbook_trace("Exporting vehicles"):
                    exportFile = tempFolder + "/vehicles.202"
                    if self.Scenario.element_totals['transit_vehicles'] == 0:
                        self._exportBlankBatchFile(exportFile, "vehicles")
                        self.TRACKER.completeTask()
                    else:
                        self.TRACKER.runTool(vehiclesExportTool,
                                         export_file=exportFile,
                                         scenario=self.Scenario)
                    zf.write(exportFile, arcname=("vehicles.202"))
                    
                with _m.logbook_trace("Exporting base network"):
                    exportFile = tempFolder + "/base.211"                    
                    self.TRACKER.runTool(baseNetworkExportTool,
                                         export_file=exportFile,
                                         scenario=self.Scenario)
                    zf.write(exportFile, arcname=("base.211"))
                    
                with _m.logbook_trace("Exporting link shapes"):
                    exportFile = tempFolder + "/shapes.251"
                    self.TRACKER.runTool(linkShapeExportTool,
                                         export_file=exportFile,
                                         scenario=self.Scenario)
                    zf.write(exportFile, arcname=("shapes.251"))
                
                with _m.logbook_trace("Exporting transit lines"):
                    exportFile = tempFolder + "/transit.221"
                    if self.Scenario.element_totals['transit_lines'] == 0:
                        self._exportBlankBatchFile(exportFile, "lines")
                        self.TRACKER.completeTask()
                    else:
                        self.TRACKER.runTool(transitExportTool,
                                             export_file=exportFile,
                                             scenario=self.Scenario)
                        
                    zf.write(exportFile, arcname=("transit.221"))
                
                with _m.logbook_trace("Exporting turns"):
                    exportFile = tempFolder + "/turns.231"
                    if self.Scenario.element_totals['turns'] == 0:
                        self._exportBlankBatchFile(exportFile, "turns")
                        self.TRACKER.completeTask()
                    else:
                        self.TRACKER.runTool(turnExportTool,
                                             export_file=exportFile,
                                             scenario=self.Scenario)
                        
                    zf.write(exportFile, arcname=("turns.231"))
                

    ##########################################################################################################
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _zipFileMANAGER(self):
        zf = _zipfile.ZipFile(self.ExportFile, 'w', _zipfile.ZIP_DEFLATED)
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
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario.id),
                "Export File": _path.splitext(self.ExportFile)[0], 
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _exportBlankBatchFile(self, filename, tRecord):
        with open(filename, 'w') as file:
            file.write("t %s init" %tRecord)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg

    