#---LICENSE----------------------
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
#---METADATA---------------------
'''
INDEX

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Table-of-contents tool 
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-08-25 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from html import HTML
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class Index(_m.Tool()):
    
    ##########################################################################################################
    #---
    #---MODELLER INTERACE METHODS
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="TMG Toolbox Index" ,
                     description="Lists all tools and libraries within the TMG Toolbox, \
                         alphabetically by tool name, with links to each tool.",
                     branding_text="- TMG Toolbox", runnable= False)
        
        tmg = [tb for tb in _MODELLER.toolboxes if tb.namespace() == 'tmg'][0]
        toolNames = self.get_tool_names(tmg)
        topCategories = self.get_top_categories(tmg)
        
        alphabetizedToolNames = {}
        for name, namespacce in toolNames:
            firstChar = name[0].upper()
            if firstChar in alphabetizedToolNames:
                alphabetizedToolNames[firstChar].append((name, namespacce))
            else:
                alphabetizedToolNames[firstChar] = [(name, namespacce)]
        orderedKeys = [key for key in six.iterkeys(alphabetizedToolNames)]
        orderedKeys.sort()
        
        for firstChar in orderedKeys:
            #pb.add_header(firstChar)
            
            toolNames = alphabetizedToolNames[firstChar]
            h = HTML()
            t = h.table(style= 'border-style:none;', width= '100%')
            tr = t.tr()
            tr.th(firstChar, colspan= '3', align= 'left')
            
            for name, namespace in toolNames:
                
                #Get description from the code
                tool = _MODELLER.tool(namespace)
                if hasattr(tool, 'short_description'):
                    description = tool.short_description()
                else:
                    description = "<em>--No description--</em>"
                
                #Determine the top-level category
                topNamespace = namespace.split('.')[1]
                if topNamespace in topCategories:
                    category = topCategories[topNamespace]
                else: continue #Skip top-level tool
                
                #Add data to table
                tr = t.tr()
                tr.td("<em>%s</em>" %category, escape= False, width= '20%')
                link = '<a data-ref="%s" class="-inro-modeller-namespace-link" style="text-decoration: none;">' %namespace
                link += name + "</a>"
                tr.td(link, escape= False, width= '40%')
                tr.td(description, escape= False, align= 'left')

            pb.wrap_html(body= str(t))
        
        return pb.render()
    
    def get_tool_names(self, toolbox):
            
        indices = toolbox.search('') #This will find the indices of every tool in the toolbox
        result = []
        for index in indices:
            element = toolbox.element(index)
            attributes = element['attributes']
            if not 'script' in attributes: continue #Only tools have scripts
            
            namespace = self.build_element_namespace(toolbox, index)
            name = attributes['name']
            
            tup = name, namespace
            result.append(tup)
        return result
            
    def build_element_namespace(self, toolbox, id):
        element = toolbox.element(id)
        attributes = element['attributes']
        ns = attributes['namespace']
        parent = element['parent_id']
        
        if parent is None:
            return ns
        else:
            return self.build_element_namespace(toolbox, parent) + '.' + ns
    
    def get_top_categories(self, toolbox):
        topElement = toolbox.element(1)
        childrenString = topElement['attributes']['children']
        middle = childrenString[1:-1]
        children = [int(cell) for cell in middle.split(',')]
        
        result = {} #Namespace -> Name
        for index in children:
            element = toolbox.element(index)
            attributes = element['attributes']
            if 'script' in attributes: continue #Only tools have scripts
            
            ns = attributes['namespace']
            name = attributes['name']
            
            result[ns] = name
        return result
        
        