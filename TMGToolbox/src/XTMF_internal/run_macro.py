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

import inro.modeller as _m

class RunMacro(_m.Tool()):
     
    ScenarioNumber = _m.Attribute(int)
    MacroFile = _m.Attribute(str)
    Args = _m.Attribute(str)
    
    def page(self):
        pb = _m.ToolPageBuilder(self, title="Run a macro",
                     runnable=False,
                     description="Cannot be called from Modeller.",
                     branding_text="XTMF")
        
        return pb.render()
    
    def run(self):
        pass
    
    def __call__(self, ScenarioNumber, MacroFile, Args):
        
        try:
            # Get the run macro tool         
            tool = None
            try:
                tool = _m.Modeller().tool('inro.emme.standard.prompt.run_macro') #Emme 3.4.2 namespace
            except Exception, e:
                tool = _m.Modeller().tool('inro.emme.prompt.run_macro') #Emme 4.0.3 namespace
                
            tool(macro_name=MacroFile,
                 macro_arguments=Args,
                 scenario=ScenarioNumber)
        except Exception, e:
            raise Exception(_traceback.format_exc(e))
        
        self.XTMFBridge.ReportProgress(1.0)
        
        