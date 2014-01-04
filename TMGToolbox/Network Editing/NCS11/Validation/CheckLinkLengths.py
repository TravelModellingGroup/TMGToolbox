import os
import os.path
import time
import math
import inro.modeller as _m
import math
import traceback as _traceback

class CheckLinkLengths(_m.Tool()):
    
    Scenario = _m.Attribute(_m.InstanceType)
    Error = _m.Attribute(float)
    tool_run_msg = ""
    
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Check Link Lengths",
                     description="Checks that link lengths are Euclidean as per NCS11. Does not edit \
                                 the network, but reports in the logbook which links are suspect.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
                pb.tool_run_status(self.tool_run_msg_status)
            
        pb.add_select_scenario(tool_attribute_name="Scenario",
                               title="Select scenario",
                               allow_none=False)
        
        pb.add_text_box(tool_attribute_name="Error",
                        size=8,
                        title="Length tolerance",
                        note="The tolerance, in meters")
        
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
        report = ""
        
        with _m.logbook_trace(name="Check Link Lengths",
                                     attributes={
                                         "Scenario" : self.Scenario.id,
                                         "Tolerance" : self.Error,
                                         "self" : self.__MODELLER_NAMESPACE__}):
            _m.logbook_write(
                name="Checking link lengths for scenario %s" %self.Scenario.id,
                attributes={
                    "version":"1.00.00"})
            
            linksChecked = 0
            problemLinks = 0
            for link in self.Scenario.get_network().links():
                i = link.i_node
                j = link.j_node    
                
                type = "link"
                
                distance = 0
                if self.linkHasMode(link, "t"):
                    distance = 0.10
                    type = "t-link"
                elif self.linkHasMode(link, "u"):
                    distance = 0.10
                    type = "u-link"
                elif (i.number > 900000 and j.number < 900000) or (j.number > 900000 and i < 900000):
                    # HOV ramp
                    distance = 0.0
                    type = "HOV ramp link"
                else:
                    d = math.sqrt((i.x - j.x)**2 + (i.y - j.y)**2) 
                    distance = (int(d /10) / 100.0) # Gives distance in km, truncated to 2 decimal places
                
                length = (int(link.length * 100) / 100.0) #Eliminates rounding error in the link length; length is in km, truncated to 2 decimal places
                
                diff = math.fabs(distance - length)
                
                if diff > self.Error:
                    problemLinks += 1
                    
                    # TODO: Have a better report, maybe in a table, which better organizes the results. 
                    report += "<p><b>Distance error:</b><ul><li><em>link id</em>: " + link.id +"</li><li><em>type</em>: " \
                        + type + "</li><li><em>distance</em>: " + str(distance) + "</li><li><em>length</em>: " + str(length) + "</li></ul></p>"
                
                linksChecked += 1
            _m.logbook_write(name="Report",
                             value=report)
            
            #test = """<select><option value="option1">1</option><option value="option2">2</option><option value="option3">3</option></select>"""
            #_m.logbook_write(name="Test Report", value=test)
                
        self.tool_run_msg = "Tool complete. " + str(linksChecked) + " links were checked, " + str(problemLinks) + " were flagged as problems. See logbook for details."
                
            
    def linkHasMode(self, Link, Char):
        for c in Link.modes:
            if c.id == Char:
                return True
        
        return False
 
            