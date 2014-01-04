import inro.modeller as _m
import traceback as _traceback
_util = _m.Modeller().module('TMG2.Common.Utilities')

class MoveNetowrks(_m.Tool()):
    
    Scenarios = _m.Attribute(_m.ListType)
    tool_run_msg = ""
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Move Networks",
                     description="Moves selected networks up by 4,000,000 meters; essentially \
                             adding a 7th digit to the y-coordinate to make the projection \
                             compatible with UTM-17N.<br>\
                             <br><b>This tool is irreversible. Make sure to copy your \
                             scenarios prior to running!</b>",
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
            with _m.logbook_trace(name="Move Networks",
                                     attributes=self._getAtts()):
                
                calculator = None
                try:
                    calculator = _m.Modeller().tool("inro.emme.network_calculation.network_calculator")
                except Exception, e:
                    calculator = _m.Modeller().tool("inro.emme.standard.network_calculation.network_calculator")
                
                spec = {
                        "result": "yi",
                        "expression": "yi + 4000000",
                        "aggregation": None,
                        "selections": {
                                       "node": "all"
                                       },
                        "type": "NETWORK_CALCULATION"
                        }
                
                for scenario in self.Scenarios:
                    _m.logbook_write("Changing scenario %s" %scenario.id)
                    calculator(spec, scenario=scenario)
                
                self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")
           
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    def _getAtts(self):
        result = {}
        
        count = 1
        for s in self.Scenarios:
            result["Scenario_%s" %count] = s.id
            count +=1
            
        result["self"] = self.__MODELLER_NAMESPACE__
        
        return result
        
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg