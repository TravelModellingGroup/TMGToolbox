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
_EMMEBANK = _MODELLER.emmebank

class Face(_m.Tool()):
    def page(self):
        pb = TmgToolPageBuilder(self, runnable=False, title="TMG ToolPageBuilder",
                                description="A wrapped version of the standard inro.modeller.ToolPageBuilder\
                                which adds some additional functionality",
                                branding_text="- TMG Toolbox")
        
        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))
        
        
        
        return pb.render()

_getMatrixText = lambda matrix: "%s - %s - %s" %(matrix.id, matrix.name, matrix.description)
_getExtraAttributeText = lambda exatt: "%s - %s - %s"(exatt.id, exatt.type, exatt.description)
_matrixOrder = {'FULL': 0, 'ORIGIN': 1, 'DESTINATION': 2, 'SCALAR': 3}
_matrixTypeSorter = lambda matrix_type: _matrixOrder[matrix_type]
_matrixTypeDimension = lambda matrix_type: _EMMEBANK.dimensions["%s_matrices" %matrix_type.lower()] 
_matrixPrefixes = {'FULL': 'mf', 'ORIGIN': 'mo', 'DESTINATION': 'md', 'SCALAR': 'ms'}

class TmgToolPageBuilder(_m.ToolPageBuilder):
    
    def __init__(self, tool, runnable=True, title="", description="", branding_text="", help_path=None,
                 footer_help_links=None):
        self.root = super(TmgToolPageBuilder, self)
        self.root.__init__(tool, runnable=runnable, title=title, description=description, branding_text=branding_text,
                           help_path=help_path, footer_help_links=footer_help_links)
        self.description = "<div class=tmg_left>%s</div>" %self.description
    
    #-------------------------------------------------------------------------------------------
    
    def _addHiddenHTML(self):
        return '''
            <style>
                    .hdr1{border-bottom: 1px solid gray;}
                    .sm_indent{padding-left: 25px; background-color: rgb( 241, 243, 233);}
                    .indent{padding-left:50px; background-color: rgb( 241, 243, 233);}
                    .tmg_left{text-align: justify;}
                    .tmg_table{background-color: rgb( 241, 243, 233); margin:0px}
            </style>'''
    
    #-------------------------------------------------------------------------------------------
    
    def render(self):
        return self._addHiddenHTML() + self.root.render()
    
    #-------------------------------------------------------------------------------------------
    
    def add_header(self,text, note=None):      
        s = '<div class="hdr1 t_element"><br><b>%s</b></div>' %text
        if note != None:
            s += '<div class="t_element">%s</div>' %note
        self.root.add_html(s)
        
    #-------------------------------------------------------------------------------------------    
    
    def add_plain_text(self, text):
        self.root.add_html('<div class="t_element">%s</div>' %text)
    
    #-------------------------------------------------------------------------------------------
    
    def add_sub_section(self, header, text):
        self.root.add_html('<div class="t_element"><b>%s</b></div>' %header)
        self.root.add_html('<div class="indent">%s</div>' %text)
     
    #-------------------------------------------------------------------------------------------
        
    def add_new_scenario_select(self, tool_attribute_name="",
                                title="", note="",
                                next_scenario_option= True,
                                allow_none= False):
        availableScenarioIds = []
        if allow_none:
            availableScenarioIds.append((-1, 'None'))
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
    
    #-------------------------------------------------------------------------------------------
    
    def add_select_output_matrix(self, tool_attribute_name,
                                 matrix_types= ['FULL'],
                                 title= "", note= "",
                                 include_none= True,
                                 include_next= True,
                                 include_existing= False,
                                 include_new= False):
        '''
        Add a widget to the page to select an output matrix. The widget
        returns a string matrix ID (or None).
        
        Args:
            - matrix_types (=['FULL']): An list of a subset of the four
                    matrix types (FULL, ORIGIN, DESTINATION, or SCALAR).
            - title (=""): Optional title above widget.
            - note (=""): Optional note below widget.
            - include_none (=True): Include the 'None' option in the 
                    widget. If selected, the widget will return the None
                    object.
            - include_next (=True): Include an option to select the next
                    available matrix for the given type(s).
            - include_existing (=False): Include existing matrices of the
                    given type(s) which are not protected from modification.
            - include_new (=False): Include options for matrices which do
                    not yet exist. Turning on this flag can make the list
                    of options very long - at minimum one entry for each
                    available matrix ID up to the maximum number of 
                    matrices given by the databank.
        
        '''
        
        if not matrix_types:
            raise TypeError("No matrix types were selected")
        
        matrix_types = list(matrix_types) #Make a copy, just in case the user wishes to preserve their original list
        matrix_types.sort(key= _matrixTypeSorter) #Sort in order of FULL, ORIGIN, DESTINATION, SCALAR
        
        options = []
        if include_none: options.append((-1, "None - Do not save"))
        
        if include_next:
            for matrixType in matrix_types:
                nextId = _EMMEBANK.available_matrix_identifier(matrixType)
                options.append((nextId,
                                "Next available %s matrix" %matrixType))
        
        if include_existing or include_new:
            for matrixType in matrix_types:
                dimension = _matrixTypeDimension(matrixType)
                prefix = _matrixPrefixes[matrixType]
                for i in range(1, dimension + 1):
                    id = prefix + str(i)
                    
                    matrix = _EMMEBANK.matrix(id)
                    if matrix == None and include_new:
                        options.append((id,
                                       "%s - New matrix %s" %(id, id)))
                        
                    elif matrix != None and include_existing:
                        if matrix.read_only: continue #Skip protected matrices
                        options.append((id,
                                       _getMatrixText(matrix)))
        if len(options) == 0:
            raise TypeError("No options were permitted")
        
        self.root.add_select(tool_attribute_name,
                             keyvalues= options,
                             title= title,
                             note= note,
                             searchable= True)
    
    #-------------------------------------------------------------------------------------------
    
    #@deprecated: Use add_select_output_matrix instead
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
                             title=title, note=note, searchable= True)
    
    #-------------------------------------------------------------------------------------------
    
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
    
    #-------------------------------------------------------------------------------------------
    
    def add_file_example(self, file_type="Sample file", header_text="", body_text=""):
        pass

    #-------------------------------------------------------------------------------------------

    def add_multi_widget(self, func_name='add_text_box', list_of_kwargs=None, width=None):
        widget_creator_func = getattr(self, func_name)
        if list_of_kwargs == None: list_of_kwargs = []

        with self.add_table(width=width) as t:
            for row in list_of_kwargs:
                if type(row) == dict:
                    #1D array of args
                    widget_creator_func(**row)
                elif type(row) == list:
                    #2D array of args
                    for kwargs in row:
                        with t.table_cell(): widget_creator_func(**kwargs)
                else:
                    raise RuntimeError("list_of_kwargs contained unsupported type %s" %type(row))

                t.new_row()

    #-------------------------------------------------------------------------------------------
    
    def add_table(self, visible_border=False, title="", width= None):
        '''
        Returns a special Table object which can be used inside a 'with'
        statement to wrap other Page widgets. This facilitates the creation
        of layout tables inside of the Page.
        
        Args:
            - visible_border (=False): Flag to make the table's borders visible.
            - title (=""): Title text to appear above the table.
            
        Returns: A Table object, with the following methods:
        
            - add_table_header(list_of_column_names): Adds a header row to the
                    table. The argument list_of_column_names is an iterable of
                    column headers. This header is automatically encapsulated
                    in its own row (there is no need to call new_row() after
                    this method).
            - new_row(): Starts a new row in the table, ending the current row.
            - table_cell(): Context manager to wrap the contents within a cell
                    within a row.
                    
        Example:
            with pb.add_table() as t:
                t.add_table_header(['Parameter', 'Value', 'Description'])
                
                with t.table_cell():
                    pb.add_html("Walk Perception")
                with t.table_cell():
                    pb.add_text_box(tool_attribute_name= 'WalkPerception', size= 6)
                with t.table_cell():
                    pb.add_html("The perception factor of walking time.")
                
                t.new_row()
                
                with t.table_cell():
                    pb.add_html("Wait Perception")
                with t.table_cell():
                    pb.add_text_box(tool_attribute_name= 'WaitPerception', size= 6)
                with t.table_cell():
                    pb.add_html("The perception factor of waiting time.")
                
                ...
        
        '''
        return _table(self.root, visible_border, title, width)
    
    #-------------------------------------------------------------------------------------------

# Context manager for creating tables inside the PageBuilder
class _table():
        
    def __init__(self, root, visible_border, title, width):
        self.root = root
        self.visible_border = visible_border
        self.title = title
        self.row_is_open = False
        self.width = width
            
    def __enter__(self):
        borderWidth = ""
        frame = "none"
        if self.visible_border:
            borderWidth = "1"
            frame = "solid"
        
        if self.width == None:
            s = "<div class='sm_indent'><table class='tmg_table' style='border-style:{1};' border={0} \
            cellpadding='0'>".format(borderWidth,  frame)
        else:
            s = "<div class='sm_indent'><table class='tmg_table' style='border-style:{1};' border={0} \
            cellpadding='0' width='{2}%'>".format(borderWidth,  frame, self.width)
            
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
    def table_cell(self, **attributes):
        h = "<td"
        for keyval in attributes.iteritems():
            h += " %s='%s'" %keyval
        h += ">"
        
        self.root.add_html(h)
        yield
        self.root.add_html("</td>")
