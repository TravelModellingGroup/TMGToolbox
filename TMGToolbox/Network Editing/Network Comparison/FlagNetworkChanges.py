#---METADATA---------------------
'''
Flag Network Changes

    Authors: 

    Latest revision by: 
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.1.0 [Description]
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import zipfile as _zf
import os
from os import path as _path
import shutil as _shutil
import tempfile as _tf
_util = _m.Modeller().module('TMG2.Common.Utilities')
_tmgTPB = _m.Modeller().module('TMG2.Common.TmgToolPageBuilder')
_MODELLER = _m.Modeller() #Instantiate Modeller once.

##########################################################################################################

class FlagNetworkChanges(_m.Tool()):
    
    version = '0.1.0'
    tool_run_msg = ""
    number_of_tasks = 8 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    NetworkCorrespondenceFile = _m.Attribute(str)
    LinkAttributeName = _m.Attribute(str)
    NodeAttributeName = _m.Attribute(str)
    LinkAttsToCompare = _m.Attribute(_m.ListType)
    NodeAttsToCompare = _m.Attribute(_m.ListType)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.Scenario = _MODELLER.scenario #Default is primary scenario
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Flag Network Changes v%s" %self.version,
                     description="Flags links and nodes in the primary scenario based on \
                         comparison against the secondary network. The flag is an attribute \
                         which takes the following values:<ol class='tmg_left' start='0'>\
                         <li> No changes</li>\
                         <li> One or more standard attributes have changed (coordinates not counted)</li>\
                         <li> Element exists in current scenario but not the other</li>\
                         <li> (Links only) Link was split in the other scenario</li>\
                         <li> (Links only) Belongs to a split link in the other scenario</li>\
                         </ol> Both scenarios will be contain the flagged attributes.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("CORRESPONDENCE FILE")
        
        pb.add_select_file(tool_attribute_name='NetworkCorrespondenceFile',
                           window_type='file',
                           title="Network correspondence File",
                           file_filter="*.zip")
        
        pb.add_header("NETWORK ATTRIBUTES")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='LinkAttributeName',
                                size=5,
                                title="Link flag attribute name",
                                note="5 characters - the '@' will be <br> \
                                    automatically appended. If the <br>\
                                    attribute already exists, it will <br>\
                                    initialized to 0.")
                
            with t.table_cell():
                keyval={'type': "Link type",
                        'num_lanes': "Link number of lanes",
                        'volume_delay_func': "Link VDF index",
                        'data1': "Link user data 1 (ul1)",
                        'data2': "Link user data 2 (ul2)",
                        'data3': "Link user data 3 (ul3)"}
                pb.add_select(tool_attribute_name='LinkAttsToCompare',
                              keyvalues=keyval,
                              title="Link attributes to compare")
            
            t.new_row()
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='NodeAttributeName',
                                size=5,
                                title="Node flag attribute name",
                                note="5 characters - the '@' will be <br> \
                                    automatically appended. If the <br>\
                                    attribute already exists, it will <br>\
                                    initialized to 0.")
            
            with t.table_cell():
                keyval={'label': "Node label",
                        'data1': "Node user data 1 (ui1)",
                        'data2': "Node user data 2 (ui2)",
                        'data3': "Node user data 3 (ui3)"}
                pb.add_select(tool_attribute_name='NodeAttsToCompare',
                              keyvalues=keyval,
                              title="Node attributes to compare")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        
        self.NodeAttributeName = "@%s" %self.NodeAttributeName
        self.LinkAttributeName = "@%s" %self.LinkAttributeName
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        self.TRACKER.reset()
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            with _m.logbook_trace("Loading correspondence file"):
                #Task 1, 2
                (primaryScenario, primaryNetwork, secondaryScenario, secondaryNetwork) = self._LoadCorrespondenceFile()
            
            with nested(self._linkAttributeMANAGER(primaryScenario),
                        self._linkAttributeMANAGER(secondaryScenario),
                        self._nodeAttributeMANAGER(primaryScenario),
                        self._nodeAttributeMANAGER(secondaryScenario),
                        _m.logbook_trace("Flagging elements")):
                
                if not self.NodeAttributeName in primaryNetwork.attributes('NODE'):
                    primaryNetwork.create_attribute('NODE', self.NodeAttributeName)
                    
                if not self.LinkAttributeName in primaryNetwork.attributes('LINK'):
                    primaryNetwork.create_attribute('LINK', self.LinkAttributeName)
                    
                if not self.NodeAttributeName in secondaryNetwork.attributes('NODE'):
                    secondaryNetwork.create_attribute('NODE', self.NodeAttributeName)
                    
                if not self.LinkAttributeName in secondaryNetwork.attributes('LINK'):
                    secondaryNetwork.create_attribute('LINK', self.LinkAttributeName)
                
                self._FlagNodes(primaryNetwork) #Task 3
                _m.logbook_write("Finished flagging nodes in scenario %s" %primaryScenario.id)
                self._FlagNodes(secondaryNetwork) #Task 4
                _m.logbook_write("Finished flagging nodes in scenario %s" %secondaryScenario.id)
                self._FlagLinks(primaryNetwork) #Task 5
                _m.logbook_write("Finished flagging links in scenario %s" %primaryScenario.id)
                self._FlagLinks(secondaryNetwork) #Task 6
                _m.logbook_write("Finished flagging links in scenario %s" %secondaryScenario.id)
            
            primaryScenario.publish_network(primaryNetwork, resolve_attributes=True)
            secondaryScenario.publish_network(secondaryNetwork, resolve_attributes=True)
                

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    @contextmanager
    def _zipFileMANAGER(self):
        file = _zf.ZipFile(self.NetworkCorrespondenceFile, 'r')
        try:
            yield file
        finally:
            file.close()
    
    @contextmanager
    def _TempDirectoryMANAGER(self):
        foldername = _tf.mkdtemp()
        _m.logbook_write("Created temporary directory at '%s'" %foldername)
        try:
            yield foldername
        finally:
            _shutil.rmtree(foldername, True)
            _m.logbook_write("Deleted temporary directory at '%s'" %foldername)
    
    #Context managers for the main output attributes, sos that they get erased if something goes wrong
    @contextmanager
    def _linkAttributeMANAGER(self, scenario):
        attributeCreated = False
        att = scenario.extra_attribute(self.LinkAttributeName)
        if att == None:
            att = scenario.create_extra_attribute('LINK', self.LinkAttributeName)
            attributeCreated = True
            _m.logbook_write("Created link extra attribute '%s' in scenario %s" %(self.LinkAttributeName, scenario.id))
        else:
            att.initialize()
            _m.logbook_write("Initialized link extra attribute '%s' in scenario %s" %(self.LinkAttributeName, scenario.id))
        
        try:
            yield
        except Exception, e:
            if attributeCreated:
                scenario.delete_extra_attribute(self.LinkAttributeName)
                _m.logbook_write("Error during normal execution. Deleted link extra attribute '%s'" %self.LinkAttributeName)
            raise
    
    @contextmanager
    def _nodeAttributeMANAGER(self, scenario):
        attributeCreated = False
        att = scenario.extra_attribute(self.NodeAttributeName)
        if att == None:
            att = scenario.create_extra_attribute('NODE', self.NodeAttributeName)
            _m.logbook_write("Created node extra attribute '%s' in scenario %s" %(self.NodeAttributeName, scenario.id))
        else:
            att.initialize()
            _m.logbook_write("Initialized node extra attribute '%s' in scenario %s" %(self.NodeAttributeName, scenario.id))
        try:
            yield
        except Exception, e:
            if attributeCreated:
                scenario.delete_extra_attribute(self.NodeAttributeName)
                _m.logbook_write("Error during normal execution. Deleted node extra attribute '%s'" %self.NodeAttributeName)
            raise    
        
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _LoadCorrespondenceFile(self):
        with self._TempDirectoryMANAGER() as tempFolder:
            with self._zipFileMANAGER() as zf:
                zf.extractall(tempFolder)
                
            (primaryScenario, secondaryScenario) = self._LoadConfig(tempFolder)
            
            self.TRACKER.startProcess(2)
            primaryNetwork = primaryScenario.get_network()
            self.TRACKER.completeSubtask()
            secondaryNetwork = secondaryScenario.get_network()
            self.TRACKER.completeTask()
            
            with _m.logbook_trace("Loading node twins"):
                self._LoadNodes(tempFolder, primaryNetwork, secondaryNetwork)
            
            with _m.logbook_trace("Loading link twins"):
                self._LoadLinks(tempFolder, primaryNetwork, secondaryNetwork)
            
            #os.remove(tempFolder + "/config.txt")
            #os.remove(tempFolder + "/nodes.txt")
            #os.remove(tempFolder + "/links.txt")
            
            return (primaryScenario, primaryNetwork, secondaryScenario, secondaryNetwork)
        
    
    def _LoadConfig(self, folderName):
        with open(folderName + "/config.txt") as reader:
            contents = dict([line.split(": ") for line in reader.readlines()])
            
            if not 'primary_scenario' in contents:
                raise IOError("Config file does not specify a primary scenario!")
            
            if not 'secondary_scenario' in contents:
                raise IOError("Config file does not specify a secondary_scenario!")
            
            primaryScenario = _MODELLER.emmebank.scenario(contents['primary_scenario'])
            secondaryScenario = _MODELLER.emmebank.scenario(contents['secondary_scenario'])
            
            if primaryScenario == None:
                raise IOError("Cannot find scenario %s in project database!" %contents['primary_scenario'])
            
            if secondaryScenario == None:
                raise IOError("Cannot find scenario %s in project database!" %contents['secondary_scenario'])
            
            return (primaryScenario, secondaryScenario)
    
    def _LoadNodes(self, folderName, primaryNetwork, secondaryNetwork):
        with open(folderName + "/nodes.txt") as reader:
            primaryNetwork.create_attribute('NODE', "twin_node", default_value=None)
            secondaryNetwork.create_attribute('NODE', "twin_node", default_value=None)
            
            reader.readline() # Toss the header
            twins = 0
            for line in reader.readlines():
                cells = line.strip().split(',')
                
                pNode = primaryNetwork.node(cells[0])
                if pNode == None:
                    raise IOError("Could not find node in primary network with id='%s'" %cells[0])
                
                if cells[1] == "null":
                    continue
                
                sNode = secondaryNetwork.node(cells[1])
                if sNode == None:
                    raise IOError("Could not find node in secondary network with id='%s'" %cells[1])
                
                pNode['twin_node'] = sNode
                sNode['twin_node'] = pNode
                
                twins += 1
        _m.logbook_write("%s nodes twinned." %twins)
        self.TRACKER.completeTask()
    
    def _LoadLinks(self, folderName, primaryNetwork, secondaryNetwork):
        with open(folderName + "/links.txt") as reader:
            primaryNetwork.create_attribute('LINK', "twin_links", default_value=None)
            secondaryNetwork.create_attribute('LINK', "twin_links", default_value=None)
            
            reader.readline() # Toss header
            twinCounts = {}
            
            def tryGetPLink(id):
                (i, j) = id.replace('(', '').replace(')', '').split('-')
                link = primaryNetwork.link(i, j)
                if link == None:
                    raise IOError("Could not find link %s in primary network!" %id)

                if link['twin_links'] == None:
                    link['twin_links'] = []
                return link
            
            def tryGetSLink(id):
                (i, j) = id.replace('(', '').replace(')', '').split('-')
                link = secondaryNetwork.link(i, j)
                if link == None:
                    raise IOError("Could not find link %s in secondary network!" %id)
                
                if link['twin_links'] == None:
                    link['twin_links'] = []
                return link
            
            for line in reader.readlines():
                ids = [s for s in line.strip().split(',') if s != "null"]
                
                pLink = tryGetPLink(ids[0])
    
                for i in range(1, len(ids)):
                    sLink = tryGetSLink(ids[i])
                    pLink['twin_links'].append(sLink)
                    sLink['twin_links'].append(pLink)
                    
                if len(pLink['twin_links']) in twinCounts:
                    twinCounts[len(pLink['twin_links'])] += 1
                else:
                    twinCounts[len(pLink['twin_links'])] = 1
                
        _m.logbook_write("Done:")
        for (size, count) in twinCounts.iteritems():
            _m.logbook_write("%s links in the primary scenario have %s twin(s)" %(count, size))
        
        self.TRACKER.completeTask()
    
    def _FlagNodes(self, network):
         
         def _GetNodeFlag(node):            
             twin = node['twin_node']
             if twin == None:
                return 2
             for attributeName in self.NodeAttsToCompare:
                if node[attributeName] != twin[attributeName]:
                    return 1
             return 0
         
         self.TRACKER.startProcess(network.element_totals['regular_nodes'])
         for node in network.regular_nodes():             
             node[self.NodeAttributeName] = _GetNodeFlag(node)
             self.TRACKER.completeSubtask()
         self.TRACKER.completeTask()        
    
    def _FlagLinks(self, network):
        
        def _GetLinkFlag(link):
            if link[self.LinkAttributeName] == 4:
                return 4 # This link is grouped with several others
            
            twins = link['twin_links']
            if twins == None: #Equivalent to having no twins
                return 2
            
            if len(twins) == 0:
                return 2
            if len(twins) > 1:
                for twin in twins:
                    twin[self.LinkAttributeName] = 4
                print "%s twins were flagged." %len(twins)
                return 3
            if len(twins) != 1: # This should never happen.
                raise Exception("Twinning error with %s" %link)
            
            for attributeName in self.LinkAttsToCompare:
                if twins[0][attributeName] != link[attributeName]:
                    return 1
            
            return 0 
        
        self.TRACKER.startProcess(network.element_totals['links'])
        for link in network.links():
            if link.i_node.is_centroid or link.j_node.is_centroid:
                self.TRACKER.completeSubtask()
                continue # skip connectors
            link[self.LinkAttributeName] = _GetLinkFlag(link)
            self.TRACKER.completeSubtask()
        self.TRACKER.completeTask()
            
            
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    