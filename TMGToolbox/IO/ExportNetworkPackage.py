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
    
    0.2.1 Removed code which supports Emme 3. A new version of this tool had been branched
            to support the Emme 3 Modeller Beta version
    
    0.3.0 Change the NWP file specification. Component files, instead of using '[fileName].211'
            (or simillar extensions) now just use one name. This allows for re-naming of the entire
            network package without adverse effects.
        
    0.4.0 Major update to export database functions, to ensure no information is lost in
            transferring networks.
    
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
_inroExportUtil = _MODELLER.module("inro.emme.utility.export_utilities")

##########################################################################################################

class ExportNetworkPackage(_m.Tool()):
    
    version = '0.4.0'
    tool_run_msg = ""
    number_of_tasks = 9 # For progress reporting, enter the integer number of tasks here
    
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
                                 network package file (*.nwp).",
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
        
        keyval = self._GetSelectAttributeOptionsJSON()
        pb.add_select(tool_attribute_name="AttributeIdsToExport", keyvalues=keyval,
                    title="Extra Attributes",  
                    note="Optional")
        
        pb.add_html("""
<script type="text/javascript">
    $(document).ready( function ()
    {
        var tool = new inro.modeller.util.Proxy(%s) ;

        $("#Scenario").bind('change', function()
        {
            $(this).commit();
            $("#AttributeIdsToExport")
                .empty()
                .append(tool._GetSelectAttributeOptionsHTML())
            inro.modeller.page.preload("#AttributeIdsToExport");
            $("#AttributeIdsToExport").trigger('change');
        });
    });
</script>""" % pb.tool_proxy_tag)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
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
            
            self._CheckAttributes() #Due to the dynamic nature of the selection process, it could happen that attributes are
                                    #selected which don't exist in the current scenario. The method checks early to catch
                                    #any problems
            
            #Only need the Emme 4 namespaces of these tools
            modeExportTool = _MODELLER.tool('inro.emme.data.network.mode.export_modes')
            vehiclesExportTool = _MODELLER.tool('inro.emme.data.network.transit.export_vehicles')
            baseNetworkExportTool = _MODELLER.tool('inro.emme.data.network.base.export_base_network')
            transitExportTool = _MODELLER.tool('inro.emme.data.network.transit.export_transit_lines')
            linkShapeExportTool = _MODELLER.tool('inro.emme.data.network.base.export_link_shape')
            turnExportTool = _MODELLER.tool('inro.emme.data.network.turn.export_turns')
            attributeExportTool = _MODELLER.tool('inro.emme.data.extra_attribute.export_extra_attributes')
            functionExportTool = _MODELLER.tool('inro.emme.data.function.export_functions')
            
            with nested(self._zipFileMANAGER(), self._TempDirectoryMANAGER()) as (zf, tempFolder):
                verionFile = tempFolder + "/version.txt"
                with open(verionFile, 'w') as writer:
                    writer.write("3.0")
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
                
                with _m.logbook_trace("Exporting Functions"):
                    exportFile = tempFolder + "/functions.411"
                    self.TRACKER.runTool(functionExportTool,
                                         export_file=exportFile)
                    zf.write(exportFile, arcname=("functions.411"))
                
                if len(self.AttributeIdsToExport) > 0:
                    with _m.logbook_trace("Exporting extra attributes"):
                        _m.logbook_write("List of attributes: %s" %self.AttributeIdsToExport)
                        
                        extraAttributes = [self.Scenario.extra_attribute(id) for id in self.AttributeIdsToExport]
                        typeSet = set([att.type.lower() for att in extraAttributes])
                        
                        self.TRACKER.runTool(attributeExportTool, extraAttributes,
                                            tempFolder,
                                            field_separator=',',
                                            scenario=self.Scenario)
                        for t in typeSet:
                            if t == 'transit_segment':
                                t = 'segment'
                            filename = tempFolder + "/extra_%ss_%s.csv" %(t, self.Scenario.number)
                            zf.write(filename, arcname="exatt_%ss.241" %t)
                            #_os.remove(filename)
                        
                        summaryFile = tempFolder + "/exatts.241"
                        self._ExportAttributeDefinitionFile(summaryFile, extraAttributes)
                        zf.write(summaryFile, arcname=_path.basename("exatts.241"))
                        #_os.remove(summaryFile)
                else:
                    self.TRACKER.completeTask()
                

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
    
    def _CheckAttributes(self):
        definedAttributes = [att.name for att in self.Scenario.extra_attributes()]
        for attName in self.AttributeIdsToExport:
            if not attName in definedAttributes:
                raise IOError("Attribute '%s' not defined in scenario %s" %(attName, self.Scenario.number))
    
    def _exportBlankBatchFile(self, filename, tRecord):
        with open(filename, 'w') as file:
            file.write("t %s init" %tRecord)

    def _ExportAttributeDefinitionFile(self, filename, attList):
        with open(filename, 'w') as writer:
            writer.write("name,type, default")
            for att in attList:
                writer.write("\n{name},{type},{default},'{desc}'"\
                             .format(name=att.name,
                                     type=att.type,
                                     default=att.default_value,
                                     desc=att.description))
    
    def _GetSelectAttributeOptionsJSON(self):
        keyval = {}
        
        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            keyval[att.name] = label
        
        return keyval
    
    @_m.method(return_type=unicode)
    def _GetSelectAttributeOptionsHTML(self):
        list = []
        
        for att in self.Scenario.extra_attributes():
            label = "{id} ({domain}) - {name}".format(id=att.name, domain=att.type, name=att.description)
            html = unicode('<option value="{id}">{text}</option>'.format(id=att.name, text=label))
            list.append(html)
        return "\n".join(list)
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    

    