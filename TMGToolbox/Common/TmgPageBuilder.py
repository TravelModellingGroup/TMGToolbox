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
from contextlib import contextmanager
_MODELLER = _m.Modeller() #Instantiate Modeller once.

class Face(_m.Tool()):
    def page(self):
        pb = TmgToolPageBuilder(self, runnable=False, title="TMG ToolPageBuilder",
                                description="A wrapped version of the standard inro.modeller.ToolPageBuilder\
                                which adds some additional functionality",
                                branding_text="TMG")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        
        
        return pb.render()

class TmgToolPageBuilder(_m.ToolPageBuilder):
    
    def __init__(self, tool, runnable=True, title="", description="", branding_text="", help_path=None,
                 footer_help_links=None):
        self.root = super(TmgToolPageBuilder, self)
        self.root.__init__(tool, runnable=runnable, title=title, description=description, branding_text=branding_text,
                           help_path=help_path, footer_help_links=footer_help_links)
        self.description = "<div class=tmg_left>%s</div>" %self.description
    
    def _addHiddenHTML(self):
        return '''
            <style>
                    .hdr1{border-bottom: 1px solid gray;}
                    .sm_indent{padding-left: 25px; background-color: rgb( 241, 243, 233);}
                    .indent{padding-left:50px; background-color: rgb( 241, 243, 233);}
                    .tmg_left{text-align: justify;}
                    .tmg_table{background-color: rgb( 241, 243, 233); margin:0px}
            </style>'''
    
    def render(self):
        return self._addHiddenHTML() + self.root.render()
    
    def add_header(self,text, note=None):      
        s = '<div class="hdr1 t_element"><br><b>%s</b></div>' %text
        if note != None:
            s += '<div class="t_element">%s</div>' %note
        self.root.add_html(s)
        
            
    
    def add_plain_text(self, text):
        self.root.add_html('<div class="t_element">%s</div>' %text)
        
    def add_sub_section(self, header, text):
        self.root.add_html('<div class="t_element"><b>%s</b></div>' %header)
        self.root.add_html('<div class="indent">%s</div>' %text)
    
    '''
    def add_select_scenario(self, tool_attribute_name, 
                            filter= lambda scenario: True,
                            filter_note="None",
                            title='', note='', allow_none=False):
        kv = []
        if allow_none:
            kv.append((None, "None"))
        for scenario in _MODELLER.emmebank.scenarios():
            if filter(scenario):
                kv.append((scenario, "%s - %s" %(scenario.number, scenario.title)))
        
        if len(kv) > 0:
            self.root.add_select(tool_attribute_name=tool_attribute_name,
                             title=title, note=note, keyvalues=kv)
        else:
            self.add_plain_text("<font color=red><b>Cannot run this tool, as there are no \
                        valid scenarios meeting criteria:</b> <em>'%s'</em></font>" %filter_note)
            self.runnable=False
    '''
        
    def add_new_scenario_select(self, tool_attribute_name="",
                                title="", note="",
                                next_scenario_option=True):
        availableScenarioIds = []
        scenarios = set([s.number for s in _MODELLER.emmebank.scenarios()])
        nextScenario = None
        for i in range(1, _MODELLER.emmebank.dimensions['scenarios'] + 1):
            if not i in scenarios:
                if nextScenario == None:
                    nextScenario = i
                availableScenarioIds.append((i, str(i)))
        if next_scenario_option:
            availableScenarioIds.append((nextScenario, "Next scenario"))
        
        self.root.add_select(tool_attribute_name=tool_attribute_name,
                      keyvalues=availableScenarioIds,
                      title=title,
                      note=note)
    
    def add_select_new_matrix(self, tool_attribute_name,
                              matrix_type='FULL',
                              title="", note="",
                              next_matrix_option=True,
                              overwrite_existing=False,
                              allow_none=False):
        availableMatrixIds = []
        currentMatrixIds = set()
        for matrix in _MODELLER.emmebank.matrices():
            if matrix.type == matrix_type: 
                currentMatrixIds.add(matrix.id)
            
        prefix = {'SCALAR': 'ms', 'ORIGIN': 'mo', 'DESTINATION': 'md', 'FULL': 'mf'}[matrix_type]
        maxMatrices = _MODELLER.emmebank.dimensions["%s_matrices" %matrix_type.lower()] + 1
        nextMatrix = None
        for i in range(1, maxMatrices):
            id = "%s%s" %(prefix, i)
            
            if not id in currentMatrixIds: #Matrix id is not yet defined
                if nextMatrix == None:
                    nextMatrix = id
                availableMatrixIds.append((id, "%s *new*" %id))
            else: #Matrix is defined
                if overwrite_existing:
                    mtx = _MODELLER.emmebank.matrix(id)
                    if not mtx.read_only:
                        availableMatrixIds.append((id, "%s '%s'" %(id, mtx.name.upper())))
                        
        if next_matrix_option:
            availableMatrixIds.insert(0, (nextMatrix, "Next available matrix"))
        if allow_none:
            tup = ("null", "None")
            availableMatrixIds.insert(0, tup)
        
        self.root.add_select(tool_attribute_name=tool_attribute_name,
                             keyvalues=availableMatrixIds,
                             title=title, note=note)
    
    def add_method_description(self, name, description="", args={}, return_string="void"):
        iter = args.iterkeys()
        h  = iter.next()
        for a in iter:
            h += ", %s" %a
        
        self.root.add_html('<div class="t_element"><b>{0}({1}) -> {2}</b></div>'.format(name, h, return_string))
        
        l = "<ul>"
        for a in args.iteritems():
            l += "<li><em>{0}: </em>{1}</li>".format(a[0], a[1])
        l += "</ul>"
        self.root.add_html('<div class="indent">{0}<br>{1}</div>'.format(description, l))           
    
    def add_file_example(self, file_type="Sample file", header_text="", body_text=""):
        pass
    
    def add_table(self, visible_border=True, title=""):
        return _table(self.root, visible_border, title)

# Context manager for creating tables inside the PageBuilder
class _table():
        
    def __init__(self, root, visible_border, title):
        self.root = root
        self.visible_border = visible_border
        self.title = title
        self.row_is_open = False
            
    def __enter__(self):
        borderWidth = ""
        frame = "none"
        if self.visible_border:
            borderWidth = "1"
            frame = "solid"
        
        #s = "<div class='t_element'><b>{0}</b><table style='border-style:{2};' border={1} \
        #    cellpadding='2' width='98%'>".format(self.title, borderWidth,  frame)
        
        s = "<div class='sm_indent'><table class='tmg_table' style='border-style:{1};' border={0} \
            cellpadding='0'>".format(borderWidth,  frame) #
            
        self.root.add_html(s)
        return self
        
    def __exit__(self, type, value, traceback):
        if self.row_is_open:
            self.root.add_html("</tr>")
            self.row_is_open = False
        self.root.add_html("</table></div>")
            
    def add_table_header(self, list_of_column_names):
        s = "<tr>"
        for column in list_of_column_names:
            s += "<th>%s</th>" %column
        s += "</tr>"
        self.root.add_html(s)
            
    def new_row(self):
        if self.row_is_open:
            self.root.add_html("</tr>")
            self.row_is_open = False
        self.root.add_html("<tr>")
        self.row_is_open = True
            
    @contextmanager
    def table_cell(self):
        self.root.add_html("<td valign='baseline'>")
        yield
        self.root.add_html("</td>")