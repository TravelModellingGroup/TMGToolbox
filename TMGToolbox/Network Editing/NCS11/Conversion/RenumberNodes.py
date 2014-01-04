import os
import os.path
import time
import math
import inro.modeller as _m
import traceback as _traceback

class RenumberNonZoneNodes(_m.Tool()):
    
    Scenarios = _m.Attribute(_m.ListType)
    revertOnError = False
    tool_run_msg = ""
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Renumber Nodes",
                     description="Re numbers non-zone nodes from NCS01 to NCS11.<br><br><b>This tool is irreversible. \
                                 Make sure to copy your scenarios prior to running!</b>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="Scenarios",
                               title="Select scenarios",
                               allow_none=False)
        
        return pb.render()
    
    def run(self):
        self.tool_run_msg = ""
        try:
           self._exectue()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        _m.Modeller().desktop.refresh_needed(False) #Tells the Emme desktop that it needs to refresh the GUI with the emmebank
    
    def _exectue(self):
        with _m.logbook_trace("Renumber nodes from DMG2001 to NCS11"):
            
            report = ""
            
            for Scenario in self.Scenarios:
                network = Scenario.get_network()
                count = 0
                
                for i in range(30000, 80000):
                    # All of the regional nodes from 30,000 to 79,999 
                    # must be shifted down by 10,000.
                    # Cycling through them from bottom-up, to ensure no id conflicts occur.
                    n = network.node(i)
                    if n == None:
                        continue
                    newNumber = n.number - 10000
                    nn = network.node(newNumber)
                    if nn != None:
                        raise Exception("Renumbering of node " + str(n.number) + " failed! New number " + str(newNumber) +" already exists!")
                    
                    n.number -= 10000
                    count += 1
                
                for i in range(0,1000):
                    n = network.node(91999 - i) 
                    # GO Rail nodes need to be shifted up by 7,000
                    # Cycling through them top to bottom to prevent id conflicts.
                    if n == None:
                        continue
                    
                    newNumber = n.number + 7000
                    nn = network.node(newNumber)
                    if nn != None:
                        raise Exception("Renumbering of node " + str(n.number) + " failed! New number " + str(newNumber) +" already exists!")
                    
                    n.number += 7000
                    count += 1
                
                for i in range(0,1000):
                    n = network.node(90999 - i) 
                    # Subway nodes need to be shifted up by 7,000
                    # Cycling through them top to bottom to prevent id conflicts.
                    if n == None:
                        continue
                    
                    newNumber = n.number + 7000
                    nn = network.node(newNumber)
                    if nn != None:
                        raise Exception("Renumbering of node " + str(n.number) + " failed! New number " + str(newNumber) +" already exists!")
                    
                    n.number += 7000
                    count += 1
                    
                Scenario.publish_network(network)
                s = "{0} nodes were changed in scenario {1}".format(count, Scenario.id)
                _m.logbook_write(s)
                report += "<br>%s" %s
                
            self.tool_run_msg = _m.PageBuilder.format_info(report)
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg