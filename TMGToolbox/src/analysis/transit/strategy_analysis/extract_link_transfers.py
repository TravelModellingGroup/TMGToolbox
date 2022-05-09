from __future__ import print_function
#---LICENSE----------------------
'''
	Copyright 2016 Matt Austin, Transportation Planning, City Planning Division, City of Toronto

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
	along with the TMG Toolbox.	 If not, see <http://www.gnu.org/licenses/>.
'''
#---METADATA---------------------
'''
Extract Link Transfers

	Authors: Matt Austin

	Latest revision by: Matt Austin
	
	
	Takes a pair of links and extracts the volume of transit passengers using both.
	Typical use case is to find number of passengers transferring in a certain way.
		
'''
#---VERSION HISTORY
'''
	0.0.1 Created on 2016-02-16 by Matt Austin: Initial build
	0.0.2 Created on 2016-05-09 by Matt Austin: Added ability to restrict to a set of lines on each link
'''

import inro.modeller as _m
import traceback as _traceback
import csv
from re import split as _regex_split
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('tmg.common.utilities')
_spindex = _MODELLER.module('tmg.common.spatial_index')
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
networkCalcTool = _MODELLER.tool('inro.emme.network_calculation.network_calculator')
pathAnalysis = _m.Modeller().tool("inro.emme.transit_assignment.extended.path_based_analysis")
EMME_VERSION = _util.getEmmeVersion(tuple)

# import six library for python2 to python3 conversion
import six 
# initalize python3 types
_util.initalizeModellerTypes(_m)

##########################################################################################################

class ExtractLinkTransfers(_m.Tool()):
	
	version = '0.0.2'
	tool_run_msg = ""
	number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
	
	#---PARAMETERS
	
	xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
	BaseScenario = _m.Attribute(_m.InstanceType) 
	
	xtmf_DemandMatrixNumber = _m.Attribute(int)
	DemandMatrix = _m.Attribute(_m.InstanceType)
	
	LinkSetString = _m.Attribute(str)
	ExportFile = _m.Attribute(str) 
	PeakHourFactor = _m.Attribute(float)   
		
	HypernetworkFlag = _m.Attribute(bool)
	
	def __init__(self):
		#---Init internal variables
		self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
		#---Set the defaults of parameters used by Modeller
		self.BaseScenario = _MODELLER.scenario
		self.HypernetworkFlag = False
		self.PeakHourFactor = 1.0
		self.LinkSetString = ""
		
		

	
	##########################################################################################################
	#---
	#---MODELLER INTERACE METHODS
	
	def page(self):
		#if EMME_VERSION < (4,1,5):
		#	 raise ValueError("Tool not compatible. Please upgrade to version 4.1.5+")
		
		pb = _tmgTPB.TmgToolPageBuilder(self, title="Extract Link Transfers v%s" %self.version,
					 description="Extracts volumes of transit passengers \
						 using pairs of links.",
					 branding_text="- City of Toronto/TMGToolbox")
		
		if self.tool_run_msg != "": # to display messages in the page
			pb.tool_run_status(self.tool_run_msg_status)
			
		pb.add_select_scenario(tool_attribute_name='BaseScenario',
							   title='Base Scenario:',
							   allow_none=False)
		
		pb.add_select_file(tool_attribute_name='ExportFile',
						   title="File name",
						   window_type='save_file',
						   file_filter="*.csv")
		
		pb.add_select_matrix(tool_attribute_name= 'DemandMatrix',
							 filter= ['FULL'], 
							 title= "Demand Matrix",
							 allow_none= True,
							 note= "Choose the demand matrix to use. Tool will determine matrix analyzed in assignment if you select 'None'.")

		pb.add_text_box(tool_attribute_name='PeakHourFactor',
						title="Peak Hour Factor",
						size=10,
						note= "Value by which to divide the transit volumes")
		
		pb.add_text_box(tool_attribute_name='LinkSetString',
						size= 750, multi_line=True,
						title= "List of Link Pairs",
						note= "Set of link pairs to be examined.\
						Use the following syntax.\
						The line filters are optional - leaving them out will use all possible lines.\
						<br><br><b>Syntax:</b> [<em>Label</em>] : [<em>Link #1</em>] : [<em>Link #2</em>] : [<em>Line #1</em>] : [<em>Line #2</em>]\
						<br><br>Punctuation is important.\
						Links should be expressed in the form 1000,1001\
						where the first number is the i node and the second is the j node.\
						Lines should be expressed as full filter expressions (e.g. line=T_____)\
						<br><br>Separate link pairs using new lines or semicolons.")		
	   
		pb.add_checkbox(tool_attribute_name= 'HypernetworkFlag',
						label= "Use links of same geometry?")
		
		#---JAVASCRIPT
		pb.add_html("""
<script type="text/javascript">
	$(document).ready( function ()
	{
		var tool = new inro.modeller.util.Proxy(%s) ;
				
		//Modeller likes to make multi-line text boxes very
		//short, so this line changes the default height
		//to something a little more visible.
		$("#LinkSetString").css({height: '90px', width: '500px'});
		
	});
</script>""" % pb.tool_proxy_tag)
		
		return pb.render()

##########################################################################################################

	def run(self):
		self.tool_run_msg = ""
		self.TRACKER.reset()

		
		try:
			self._Execute()
		except Exception as e:
			self.tool_run_msg = _m.PageBuilder.format_exception(
				e, _traceback.format_exc())
			raise
		
		self.tool_run_msg = _m.PageBuilder.format_info("Done.")

##########################################################################################################

	def __call__(self, xtmf_ScenarioNumber, xtmf_DemandMatrixNumber, LinkSetString, 
				 ExportFile, PeakHourFactor, HypernetworkFlag):

		print("Beginning to extract link transfer data")

		self.BaseScenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
		if (self.BaseScenario is None):
			raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
		
		if xtmf_DemandMatrixNumber == 0:
			self.DemandMatrix = None
		else:
			self.DemandMatrix = _MODELLER.emmebank.matrix("mf%s" %xtmf_DemandMatrixNumber)
			if self.DemandMatrix is None:
				raise Exception("Matrix %s was not found!" %xtmf_DemandMatrixNumber)
		
		self.LinkSetString = LinkSetString
		self.ExportFile = ExportFile
		self.PeakHourFactor = PeakHourFactor
		self.HypernetworkFlag = HypernetworkFlag		   
		   
		try:
			self._Execute()
		except Exception as e:
			msg = str(e) + "\n" + _traceback.format_exc()
			raise Exception(msg)

		print("Finished extracting link transfer data")

##########################################################################################################		  

	def _Execute(self):
		with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
									 attributes=self._GetAtts()):

			linkLists = self._ParseLinkString(self.LinkSetString)
			results = []

			if self.DemandMatrix is None:
				demandMatrixId = _util.DetermineAnalyzedTransitDemandId(EMME_VERSION, self.BaseScenario)
			else:
				demandMatrixId = self.DemandMatrix.id			 
			
			for linkPair in linkLists:
				fullLinkSet = linkPair[0:3]
				link1List = [linkPair[1]] # maintain a list of links at and above link 1 for volume summing later (sums at/above link 1 and 2 will be identical)
				if self.HypernetworkFlag: # search for links 'above' the initial link pair in the hypernetwork
					print("Looking for links in the hypernetwork")
					network = self.BaseScenario.get_network()					 
					initialLink1 = self._ParseIndividualLink(linkPair[1])
					initialLink2 = self._ParseIndividualLink(linkPair[2])
					inode1 = initialLink1[0]
					inode2 = initialLink2[0]
					jnode1 = initialLink1[1]
					jnode2 = initialLink2[1]
					for link in network.links():
						if link.shape == network.link(inode1, jnode1).shape:
							linkString = self._LinkToString(link)
							if linkString not in fullLinkSet:
								fullLinkSet.append(linkString)
								link1List.append(linkString)
						if link.shape == network.link(inode2, jnode2).shape:
							linkString = self._LinkToString(link)
							if linkString not in fullLinkSet:
								fullLinkSet.append(linkString)

				with _util.tempExtraAttributeMANAGER(self.BaseScenario, 'LINK', description= 'Link Flag') as linkMarkerAtt, _util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_LINE', description= 'Line Flag') as lineMarkerAtt, _util.tempExtraAttributeMANAGER(self.BaseScenario, 'TRANSIT_SEGMENT', description= 'Transit Volumes') as segVol:
					
					networkCalcTool(self._MarkLinks(fullLinkSet, linkMarkerAtt.id), scenario=self.BaseScenario)
					print ('Finished marking links for %s' %fullLinkSet[0])
					if len(linkPair) == 5: #check if there are line filters
						networkCalcTool(self._MarkLines(linkPair[3], lineMarkerAtt.id), scenario=self.BaseScenario)
						networkCalcTool(self._MarkLines(linkPair[4], lineMarkerAtt.id), scenario=self.BaseScenario)
						pathAnalysis(self._PathVolumeWithLines(linkMarkerAtt.id, segVol.id, demandMatrixId, lineMarkerAtt.id), scenario=self.BaseScenario)  
						print ('Finished running path analysis for %s' %fullLinkSet[0])						
					else:
						pathAnalysis(self._PathVolume(linkMarkerAtt.id, segVol.id, demandMatrixId), scenario=self.BaseScenario)	 
						print ('Finished running path analysis for %s' %fullLinkSet[0])
											
					network = self.BaseScenario.get_network()
					print('Network loaded')
					linkSum = 0
					for link in link1List: #evaluate all links at/above link 1
						singleLinkList = self._ParseIndividualLink(link)
						for s in network.link(singleLinkList[0], singleLinkList[1]).segments(): #iterate through segments on the link
							linkSum += s[segVol.id]
					linkSum /= self.PeakHourFactor
					results.append([fullLinkSet[0],linkSum]) #add label and sum
					print('Results calculated for %s' %fullLinkSet[0])


			self._WriteResultsToFile(results)

			self.TRACKER.completeTask()


	##########################################################################################################

	#----SUB FUNCTIONS---------------------------------------------------------------------------------	 
	
	def _GetAtts(self):
		atts = {
				"Scenario" : str(self.BaseScenario.id),
				"Version": self.version,
				"self": self.__MODELLER_NAMESPACE__}
			
		return atts

	

	def _ParseLinkString(self, linkSetString):
		linkLists = []
		components = _regex_split('\n|;', linkSetString) #Supports newline and/or semi-colons
		for component in components:
			if component.isspace(): continue #Skip if totally empty
			
			parts = component.split(':')
			if len(parts) > 5 or len(parts) < 3 or len(parts) == 4:
				print(component)
				msg = "Error parsing label, link and line string: Separate label and links/lines with colons label:link1:link2[:line1:line2]"
				msg += ". [%s]" %component 
				raise SyntaxError(msg)
			strippedParts = [item.strip() for item in parts]
			linkLists.append(strippedParts)

		return linkLists

	def _ParseIndividualLink(self, linkString): #converts string form of link into a list
		indLinkList = linkString.split(',')
		if len(indLinkList) != 2:
			print(linkString)
			msg = "Error parsing link. Link must be in the form 1000,1001"
			msg += ". [%s]" %component 
			raise SyntaxError(msg)
		return indLinkList

	def _LinkToString(self, link): #converts link object into the string form 1000,1001
		linkStr = str(link.i_node) + "," + str(link.j_node)
		return linkStr

	
	def _MarkLinks(self, linkList, markerId):
		linkString = ""
		count = 0
		for item in linkList:
			if count == 0:
				count += 1
				continue
			elif count == 1:
				count += 1
				linkString += "link="
				linkString += item
			else:
				count += 1
				linkString += " or link="
				linkString += item
	
		
		spec = {
					"result": markerId,
					"expression": '10', #to avoid the situation where an extra line use replaces a link use, we use a larger value for links
					"aggregation": None,
					"selections": {
						"link": linkString
					},
					"type": "NETWORK_CALCULATION"
				}
		return spec
		
	def _MarkLines(self, lineString, markerId):
		spec = {
					"result": markerId,
					"expression": '1',
					"aggregation": None,
					"selections": {
						"transit_line": lineString
					},
					"type": "NETWORK_CALCULATION"
				}
		return spec
		
	def _PathVolume(self, markerId, volumeId, demandMatrixId):
		spec = {
					"type": "EXTENDED_TRANSIT_PATH_ANALYSIS",
					"portion_of_path": "COMPLETE",
					"trip_components": {
						"in_vehicle": markerId
					},
					"path_operator": "+",
					"path_selection_threshold": {
						"lower": 20,
						"upper": 20
					},
					"analyzed_demand": demandMatrixId,
					"results_from_retained_paths": {
						"paths_to_retain": "SELECTED",
						"transit_volumes": volumeId
					}
				} 
		return spec
		
	def _PathVolumeWithLines(self, markerId, volumeId, demandMatrixId, lineId):
		spec = {
					"type": "EXTENDED_TRANSIT_PATH_ANALYSIS",
					"portion_of_path": "COMPLETE",
					"trip_components": {
						"in_vehicle": markerId,
						"initial_boarding": lineId,
						"transfer_boarding": lineId
					},					
					"path_operator": "+",
					"path_selection_threshold": {
						"lower": 22,
						"upper": 22
					},
					"analyzed_demand": demandMatrixId,
					"results_from_retained_paths": {
						"paths_to_retain": "SELECTED",
						"transit_volumes": volumeId
					}
				} 
		return spec

	def _WriteResultsToFile(self, results):
		with open(self.ExportFile, 'wb') as csvfile:
			aggWrite = csv.writer(csvfile, delimiter = ',')
			aggWrite.writerow(['label', 'volume'])
			for item in results:
				aggWrite.writerow(item) 
	
	@_m.method(return_type=_m.TupleType)
	def percent_completed(self):
		return self.TRACKER.getProgress()
				
	@_m.method(return_type=six.u)
	def tool_run_msg_status(self):
		return self.tool_run_msg

	
	def short_description(self):
		return "<em>Returns volume of transit passengers using a pair of links.</em>"
