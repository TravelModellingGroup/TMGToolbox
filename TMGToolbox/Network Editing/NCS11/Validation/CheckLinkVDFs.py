import os
import os.path
import time
import math
import inro.modeller as _m
import traceback as _traceback

class CheckVDFs(_m.Tool()):
    
    WorksheetFile = _m.Attribute(str)
    Scenario = _m.Attribute(_m.InstanceType)
    tool_run_msg = ""
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Check Link VDFs",
                     description="Produces a worksheet to view all link VDFs in a scenario. It is recommended that you open the default worksheet prior to running this tool.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_scenario(tool_attribute_name="Scenario",
                                title="Select scenario",
                                note="Select a scenario to view")
        
        try:
            root = os.path.dirname(_m.Modeller().desktop.project_filename())
        except Exception, e:
            root = os.path.dirname(_m.Modeller().desktop.project_file_name())
        pb.add_select_file(tool_attribute_name="WorksheetFile",
                           window_type="file",
                           file_filter="*.emw",
                           start_path=root,
                           title="Emme worksheet file",
                           note="Optional. If provided, this tool will add layers to the worksheet file selected.")
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        try:
           self()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    def __call__(self):
        worksheet = None
        if not (self.WorksheetFile == None or self.WorksheetFile == ""):
            #Open a worksheet file
            worksheet = _m.Modeller().desktop.open_worksheet(self.WorksheetFile)
        else:
            worksheet = _m.Modeller().desktop.current_window()
            if not isWorksheet(worksheet):
                for w in _m.Modeller().desktop.windows():
                    if isWorksheet(w):
                        worksheet = w
                        break
                if not isWorksheet(worksheet):
                    raise Exception("No worksheet file was selected, and no worksheet is currently open! You need to specify a worksheet")
        
        vdfValues = self.getLinkVDFs()
        
        for v in vdfValues:
            l = worksheet.add_layer_front('Link base', layer_name="VDF %s" %v)
            l.par('LinkFilter').set('vdf == %s' %v)
    
    def getLinkVDFs(self):
        network = self.Scenario.get_network()
        vdfValues = set()
        for link in network.links():
            vdfValues.add(link.volume_delay_func)
        return vdfValues
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
def isWorksheet(w):
    return dir(w).count('layers') == 1