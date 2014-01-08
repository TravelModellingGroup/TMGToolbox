#---METADATA---------------------
'''
Create Network Correspondence File

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Creates a correspondence file for comparing two networks. This file should be easily parseable
    for other analyses.
        
'''
#---VERSION HISTORY
'''
    0.1.0 Created
    
    0.1.1 Updated to catch null export file error
    
    0.1.2 Added CorrespondenceFileReader class for easy loading in of correspondence file data
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
import math as _math
import numpy as _n
import zipfile as _zf
from os import path as _path
import os
from datetime import datetime as _dt
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')


##########################################################################################################

class CreateNetworkCorrespondenceFile(_m.Tool()):
    
    version = '0.1.2'
    tool_run_msg = ""
    number_of_tasks = 7 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    PrimaryScenario = _m.Attribute(_m.InstanceType)
    SecondaryScenario = _m.Attribute(_m.InstanceType)
    SearchBuffer = _m.Attribute(float)
    MaxSplitLinks = _m.Attribute(int)
    MaxBearingDifference = _m.Attribute(int)
    CorrespondenceFile = _m.Attribute(str)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.PrimaryScenario = _MODELLER.scenario #Default is primary scenario
        self.SearchBuffer = 50.0
        self.MaxSplitLinks = 10
        self.MaxBearingDifference = 5
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Create Network Correspondence File v%s" %self.version,
                     description="<p class='tmg_left'>Twins together nodes and links in two networks. \
                         Node correspondence \
                         is based on proximity (Manhattan distance). Link correspondence is based on \
                         node correspondence - e.g., if both ends of a link in the primary correspond \
                         to both ends of another link in the secondary network, then those two links \
                         are twinned. If no link twin is found, this tool attempts to determine if a \
                         split has occurred; based on the bearing of links attached to it's twinned \
                         nodes.\
                         <br><br>The results are saved into a zip file, containing three files: \
                         <ul class='tmg_left'><li><b>config.txt</b> contains the parameters used to \
                         write the file</li>\
                         <li><b>nodes.txt</b> contains the node correspondence</li>\
                         <li><b>links.txt</b> contains the link correspondence</li></ul></p>",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_header("SCENARIOS")
        #------------------------------------------------------------
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_select_scenario(tool_attribute_name='PrimaryScenario',
                                       title='Primary Scenario',
                                       allow_none=False)
            
            with t.table_cell():
                pb.add_select_scenario(tool_attribute_name='SecondaryScenario',
                                       title='Secondary Scenario',
                                       allow_none=False)
        
        pb.add_header("CORRESPONDANCE PARAMETERS")
        #------------------------------------------------------------
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='SearchBuffer',
                                title="Node Search Buffer",
                                size=10,
                                note="Search radius, in coordinate units.")
                
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='MaxSplitLinks',
                                size=2,
                                title="Max split links",
                                note="Maximum number of split links to look for.")
                
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='MaxBearingDifference',
                                size=2,
                                title="Max bearing difference",
                                note="In degrees.")
        
        pb.add_header("OUTPUT FILE")
        #------------------------------------------------------------
        
        pb.add_select_file(tool_attribute_name='CorrespondenceFile',
                           window_type='save_file',
                           title="Correspondence File",
                           file_filter="*.zip")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if self.CorrespondenceFile == None:
            raise IOError("Export file not specified")
        
        self.CorrespondenceFile = _path.splitext(self.CorrespondenceFile)[0] + ".zip"
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Run complete.<br>\
                                    <a href=%s target='_top'>%s</a>" 
                                    %(self.CorrespondenceFile,
                                      _path.basename(self.CorrespondenceFile)), escape=False)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            self._maxBearingDiffRadians = abs(2 * _math.pi * self.MaxBearingDifference / 360.0)
            
            #Load the networks
            self.TRACKER.startProcess(2)
            primaryNetwork = self.PrimaryScenario.get_network()
            self.TRACKER.completeSubtask()
            secondaryNetwork = self.SecondaryScenario.get_network()
            self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
            
            with _m.logbook_trace("Associating node twins"):
                self._ConnectTwinNodes(primaryNetwork, secondaryNetwork)
                
            with _m.logbook_trace("Associating link twins"):
                maxTwins = self._ConnectTwinLinks(primaryNetwork, secondaryNetwork)
                
            with _m.logbook_trace("Writing results to file"):
                self._WriteFile(primaryNetwork, maxTwins)
                _m.logbook_write("Done.")
            

    ##########################################################################################################
    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _zipFileMANAGER(self):
        file = _zf.ZipFile(self.CorrespondenceFile, 'w', _zf.ZIP_DEFLATED)
        try:
            yield file
        finally:
            file.close()
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Primary Scenario" : self.PrimaryScenario.id,
                "Secondary Scenario": self.SecondaryScenario.id,
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _ConnectTwinNodes(self, primaryNetwork, secondaryNetwork):
        self.TRACKER.startProcess(primaryNetwork.element_totals['regular_nodes'])
        
        primaryNetwork.create_attribute('NODE', "twin_node", default_value=None)
        secondaryNetwork.create_attribute('NODE', "twin_node", default_value=None)
        
        grid = _util.buildSearchGridFromNetwork(secondaryNetwork)
        for primaryNode in primaryNetwork.regular_nodes():
            twin = grid.getNearestNode(primaryNode.x, primaryNode.y, self.SearchBuffer)
            
            if twin == None:
                self.TRACKER.completeSubtask()
                continue
        
            primaryNode['twin_node'] = twin
            twin['twin_node'] = primaryNode
            self.TRACKER.completeSubtask()
        
        self.TRACKER.completeTask()
    
    def _ConnectTwinLinks(self, primaryNetwork, secondaryNetwork):
        primaryNetwork.create_attribute('LINK', "twin_links", default_value=[])
        secondaryNetwork.create_attribute('LINK', "twin_links", default_value=[])
        
        maxTwins = 0
        
        # First pass.
        pLinksTwinned = 0
        sLinksTwinned = 0
        self.TRACKER.startProcess(primaryNetwork.element_totals['links'])
        for primaryLink in primaryNetwork.links():
            if primaryLink.i_node.is_centroid or primaryLink.j_node.is_centroid:
                self.TRACKER.completeSubtask()
                continue # Skip centroid connectors
            
            twins = self._GetTwinLinks(primaryLink)
            
            if twins == None:
                self.TRACKER.completeSubtask()
                continue
            
            if len(twins) > maxTwins:
                maxTwins = len(twins)
            
            primaryLink['twin_links'] = twins
            pLinksTwinned += 1
            for secondaryLink in twins:
                secondaryLink['twin_links'] = [primaryLink]
                sLinksTwinned += 1
        self.TRACKER.completeTask()
        
        _m.logbook_write("Finished first pass. %s primary links twinned to %s secondary links." 
                         %(pLinksTwinned, sLinksTwinned))
        
        # Second Pass
        pLinksTwinned = 0
        sLinksTwinned = 0
        self.TRACKER.startProcess(secondaryNetwork.element_totals['links'])
        for secondaryLink in secondaryNetwork.links():
            if secondaryLink.i_node.is_centroid or secondaryLink.j_node.is_centroid:
                self.TRACKER.completeSubtask()
                continue # Skip centroid connectors
            
            if len(secondaryLink['twin_links']) > 0:
                continue # Skip if link is already twinned.
            
            twins = self._GetTwinLinks(secondaryLink)
            
            if twins == None:
                self.TRACKER.completeSubtask()
                continue
            
            if len(twins) > maxTwins:
                maxTwins = len(twins)
            
            secondaryLink['twin_links'] = twins
            sLinksTwinned += 1
            for primaryLink in twins:
                primaryLink['twin_links'] = [secondaryLink]
                pLinksTwinned += 1
        self.TRACKER.completeTask()
        
        _m.logbook_write("Finished second pass. %s additional secondary links twinned to %s primary links." 
                         %(sLinksTwinned, pLinksTwinned))
        
        return maxTwins
        
    def _GetTwinLinks(self, originalLink):
        
        if originalLink.i_node['twin_node'] == None or originalLink.j_node['twin_node'] == None:
            return None #Cannot ever find a corresponding originalLink for a originalLink with no twin nodes
    
        # Check for the same link in the other network
        for outLink in originalLink.i_node['twin_node'].outgoing_links():
            if outLink.j_node == originalLink.j_node['twin_node']:
                return [outLink] 
        
        # If not, try and get the collection of links which were created by splitting this link
        # (if such links exist). This function returns None if a valid split path cannot be found. 
        return self._GetCorrespondingSplitLinks(originalLink)
    
    def _GetCorrespondingSplitLinks(self, originalLink):
        #don't call this method unless both node-ends of the original link have twins
        originalBearing = self._GetLinkBearing(originalLink)
        
        linkSequece = []
        prevNode = originalLink.i_node['twin_node'] 
        for i in range(0, self.MaxSplitLinks):
            candidateLinks = [] #tuple of 0. Bearing difference, 1. outgoing link
            outgoingLinks = [link for link in prevNode.outgoing_links()]
            
            for link in outgoingLinks:
                bearingDiff = abs(self._GetLinkBearing(link) - originalBearing)
                
                if bearingDiff > self._maxBearingDiffRadians:
                    continue
                candidateLinks.append((bearingDiff, link))
            
            if len(candidateLinks) == 0:
                return None # If there are no links within the search arc, since we haven't reached the 
                            # end node of the original link, therefore no straight path exists.
            
            bestLink = min(candidateLinks)[1] #If there are more than one links within the search arc, pick 
                                            # the closest.
            linkSequece.append(bestLink)
            
            if bestLink.j_node == originalLink.j_node['twin_node']:  # We've reached the end node of the original
                return linkSequece                                  # link. So, return the sequence
            
            prevNode = bestLink.j_node #continue searching for candidate links in the sequences
        
    def _GetLinkBearing(self, link):
        rad = _math.atan2(link.j_node.x - link.i_node.x, link.j_node.y - link.i_node.y)
        if rad < 0:
            return rad + _math.pi * 2
        return rad
    
    def _WriteFile(self, primaryNetwork, maxLinkTwins):
        folderName = _path.dirname(self.CorrespondenceFile)
        with open("%s/config.txt" %folderName, 'w') as writer:
            s = "project_path: {projPath}\
                \nprimary_scenario: {pSc}\
                \nsecondary_scenario: {sSc}\
                \nsearch_radius: {rad}\
                \nmax_twins: {max}\
                \narc_tolerance: {arc}\
                \ncreated: {date}".format(projPath=_MODELLER.desktop.project_file_name(),
                                       pSc=self.PrimaryScenario.id,
                                       sSc=self.SecondaryScenario.id,
                                       rad=str(self.SearchBuffer),
                                       max=str(self.MaxSplitLinks),
                                       arc=str(self.MaxBearingDifference),
                                       date=_dt.now())
            writer.write(s)
        
        with open("%s/nodes.txt" %folderName, 'w') as writer:
            self.TRACKER.startProcess(primaryNetwork.element_totals['regular_nodes'])
            writer.write("primary_node,secondary_node")
            for node in primaryNetwork.nodes():
                twin = node['twin_node']
                if twin == None:
                    writer.write("\n%s,null" %node)
                else:
                    writer.write("\n%s,%s" %(node,twin))
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
        
        with open("%s/links.txt" %folderName, 'w') as writer:
            self.TRACKER.startProcess(primaryNetwork.element_totals['links'])
            writer.write("primary_link")
            for i in range(0, maxLinkTwins):
                writer.write(",twin_link_%s" %(i + 1))
                
            for primaryLink in primaryNetwork.links():
                writer.write("\n(%s-%s)" %(primaryLink.i_node, primaryLink.j_node))
                twins = primaryLink['twin_links']
                
                if len(twins) == 0:
                    for i in range(0, maxLinkTwins):
                        writer.write(",null")
                    continue
                
                for secondaryLink in twins:
                    writer.write(",(%s-%s)" %(secondaryLink.i_node, secondaryLink.j_node))
                for i in range(len(twins), maxLinkTwins):
                    writer.write(",null")
                self.TRACKER.completeSubtask()
            self.TRACKER.completeTask()
        
        with self._zipFileMANAGER() as zf:
            zf.write("%s/config.txt" %folderName, arcname="config.txt")
            zf.write("%s/links.txt" %folderName, arcname="links.txt")
            zf.write("%s/nodes.txt" %folderName, arcname="nodes.txt")
            os.remove("%s/config.txt" %folderName)
            os.remove("%s/links.txt" %folderName)
            os.remove("%s/nodes.txt" %folderName)
            
            self.TRACKER.completeTask()    
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
######################################################

class CorrespondenceFileReader():
    
    def __init__(self, filename, emmebank=_MODELLER.emmebank):
        self.__fn = filename
        self.emmebank = emmebank
        self.TRACKER = _util.ProgressTracker(5) #init the ProgressTracker
    
    def __enter__(self):
        self.__zf = _zipfile.ZipFile(filename)
        return self
    
    def __exit__(self, *args):
        self.__zf.close()
    
    def __call__(self):        
        #Load config file
        cFile = zf.open('config.txt')
        config = {}
        for line in cFile:
            cells = line.split(':', 1)
            cells = [s.strip() for s in cells]
            config[cells[0]] = cells[1]
        cFile.close() 
        self.TRACKER.completeTask()
        
        #Get the scenarios
        pScenario = self.emmebank.scenario(config['primary_scenario'])
        if pScenario == None: raise IOError("Primary scenario %s doesn't exist." %config['primary_scenario'])
        sScenario = self.emmebank.scenario(config['secondary_scenario'])
        if sScenario == None: raise IOError("Secondary scenario %s doesn't exist." %config['secondary_scenario'])
        
        #Load the networks into RAM
        primaryNetwork = pScenario.get_network()
        self.TRACKER.completeTask()
        secondaryNetwork = sScenario.get_network()
        self.TRACKER.completeTask()
        
        #Load node twins
        primaryNetwork.create_attribute('NODE', 'twin', None)
        secondaryNetwork.create_attribute('NODE', 'twin', None)
        nodeFile = zf.open('nodes.txt')
        for line in nodeFile:
            line = line.strip()
            cells = line.split(',')
            if 'null' in cells: continue #Skip null matching
            pNode = primaryNetwork.node(cells[0])
            sNode = secondaryNetwork.node(cells[1])
            pNode.twin = sNode
            sNode.twin = pNode
        nodeFile.close()
        self.TRACKER.completeTask()
        
        def parseLinkId(s):
            cells = s.strip(')').strip('(').split('-')
            return (int(cells[0]), int(cells[1]))
        def getLink(id, network):
            iNode, jNode = parseLinkId(id)
            return network.link(iNode, jNode)
            
        #Load link twins
        primaryNetwork.create_attribute('LINK', 'twins', None)
        for link in primaryNetwork.links(): link.twins = set()
        secondaryNetwork.create_attribute('LINK', 'twins', None)
        for link in secondaryNetwork.links(): link.twins = set()
        linksFile = zf.open('links.txt')
        for line in linksFile:
            line = line.strip()
            cells = [id for id in line.split(',') if id != 'null']
            if len(cells) == 1: continue #Skip links with no twins
            
            iter = cells.__iter__()
            pLink = getLink(iter.next(), primaryNetwork)
            for id in iter:
                sLink = getLink(id, secondaryNetwork)
                pLink.twins.add(sLink)
                sLink.twins.add(pLink)
                
        self.TRACKER.completeTask()
        return (primaryNetwork, secondaryNetwork)
        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    