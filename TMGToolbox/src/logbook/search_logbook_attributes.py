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

        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 20/01/2015
    
    1.0.0 Cleaned and published 20/01/2015
    
'''
import traceback as _traceback
from html import HTML

import inro.modeller as _m
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')

##########################################################################################################

class SearchLogbookAttribtues(_m.Tool()):
    
    BEGIN_KEY = 'begin_304A7365_C276_493A_AB3B_9B2D195E203F'
    END_KEY = 'end_304A7365_C276_493A_AB3B_9B2D195E203F'
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    AttributeName = _m.Attribute(str)
    AttributeValue = _m.Attribute(str)
    
    CaseSensitivity = _m.Attribute(bool)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        self.AttributeName = 'scenario'
        self.AttributeValue = _MODELLER.scenario.id
        
        self.CaseSensitivity = False
        
        self.matches = []
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Search Logbook Attribtues v%s" %self.version,
                     description="Searches the logbook for entries with a named attribute value \
                         (available attributes & their associated values can be discovered by \
                         double-clicking a logbook entry). One example of where this is useful is \
                         to trace the histroy of a single scenario.",
                     branding_text="- TMG Toolbox")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
            
        if self.matches:
            with pb.section('Search Results'):
                h = HTML()
                l = h.ul()
                for timestamp, element_id, title in self.matches:
                    description = "%s: %s" %(title, timestamp)
                    
                    a = self._render_entry_link(element_id, description)
                    
                    l.li(a, escape= False)
                
                pb.wrap_html(body= str(l))
        
        pb.add_text_box(tool_attribute_name= 'AttributeName',
                        title= "Attribute",
                        note= "Match attribute names containing this text.",
                        size=100)
        
        pb.add_text_box(tool_attribute_name= 'AttributeValue',
                        title = "Value",
                        note="Match attribute values containing this text",
                        size=100)
        
        pb.add_checkbox(tool_attribute_name= 'CaseSensitivity',
                       label= "Case sensitive?")
        
        return pb.render()
    
    def _render_entry_link(self, id, description):
        l = '''<a href="#" class= "-inro-modeller-logbook-history-item-link" data-logbook-item-id= "%s">''' %id
        return l + description + "</a>"
        
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.matches = []
        
        try:
            self._execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def _execute(self):
        record_list = self._search_logbook()
        
        if len(record_list) < 1:
            raise Exception("No matches found.")
        
        for element_id in record_list:
            timestamp, title = self._query_element_metadata(element_id)
            
            self.matches.append((timestamp, element_id, title))
            
        self.matches.sort()
        
    def _search_logbook(self):
        if self.CaseSensitivity:
            n = self.AttributeName
            v = self.AttributeValue
            condition1 = 'name'
            condition2 = 'value'
            
        else:
            n = self.AttributeName.lower()
            v = self.AttributeValue.lower()
            condition1 = 'LOWER(name)'
            condition2 = 'LOWER(value)'

        where = "{c1} LIKE '%{n}%' AND {c2} LIKE '%{v}%';".format(c1= condition1, n=n, c2= condition2, v=v)
        
        sql = '''SELECT element_id
                FROM attributes
                WHERE %s''' %where
        
        result = _m.logbook_query(sql)
        return [t[0] for t in result]
    
    def _query_element_metadata(self, elemnt_id):
        sql = '''SELECT value FROM attributes WHERE element_id= '{id}' 
            AND name = '{begin}';'''.format(id= elemnt_id, begin= self.BEGIN_KEY)
        
        timestamp = _m.logbook_query(sql)[0][0]
        print timestamp
        
        sql = '''SELECT tag FROM elements WHERE element_id= %s''' %elemnt_id
        title = _m.logbook_query(sql)[0][0]
        print title
        
        return timestamp, title
    
    ##########################################################################################################    
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
        