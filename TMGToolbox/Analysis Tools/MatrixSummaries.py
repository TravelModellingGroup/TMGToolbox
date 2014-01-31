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
[TITLE]

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    [Description]
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-30 by pkucirek
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from numpy import average, histogram, array, min, max, std, median
from math import sqrt
from inro.emme.matrix import submatrix as get_submatrix
from datetime import datetime as dt
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class MatrixSummary(_m.Tool()):
    
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    ValueMatrix = _m.Attribute(_m.InstanceType)
    WeightingMatrix = _m.Attribute(_m.InstanceType)
    Scenario = _m.Attribute(_m.InstanceType)
    ReportFile = _m.Attribute(str)
    
    OriginFilterExpression = _m.Attribute(str)
    DestinationFilterExpression = _m.Attribute(str)
    CellFilterExpression = _m.Attribute(str)
    
    HistogramMin = _m.Attribute(float)
    HistogramMax = _m.Attribute(float)
    HistogramStepSize = _m.Attribute(float)
    
    xtmf_ScenarioNumber = _m.Attribute(int) # parameter used by XTMF only
    xtmf_ValueMatrixNumber = _m.Attribute(int)
    xtmf_WeightingMatrixNumber = _m.Attribute(int)
    
    
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        self.HistogramMin = 0.0
        self.HistogramMax = 200.0
        self.HistogramStepSize = 10.0
        
        self.OriginFilterExpression = "return p < 9000"
        self.DestinationFilterExpression = "return q < 9000"
        self.CellFilterExpression = "return pq < 1000.0"
        
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="[TOOL NAME] v%s" %self.version,
                     description="[DESCRIPTION]",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_matrix(tool_attribute_name='ValueMatrix',
                             filter=['FULL'], allow_none=False,
                             title="Value Matrix")
        
        pb.add_select_matrix(tool_attribute_name='WeightingMatrix',
                             filter=['FULL'], allow_none=True,
                             title="Weighting Matrix",
                             note="<font color='blue'><b>Optional:</b> Matrix of weights</font>")
        
        pb.add_select_file(tool_attribute_name='ReportFile',
                           window_type='save_file',
                           file_filter='*.txt',
                           title="Report File",
                           note="<font color='blue'><b>Optional</b></font>")
        
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=True)
        
        pb.add_header('FILTERS')
        
        pb.add_text_box(tool_attribute_name='OriginFilterExpression',
                        size=100, multi_line=False,
                        title="def OriginFilter(p):",
                        note="Enter a Python expression.")
        
        pb.add_text_box(tool_attribute_name='DestinationFilterExpression',
                        size=100, multi_line=False,
                        title="def DestinationFilter(q):",
                        note="Enter a Python expression.")
        
        #TODO: Figure out how to apply the filter expression
        #simultaeneously to both the value and weight matrix
        #using numpy
        '''
        pb.add_text_box(tool_attribute_name='CellFilterExpression',
                        size=100, multi_line=True,
                        title="def CellFilter(pq):",
                        note="Enter a Python expression.")
        '''
        
        pb.add_header("HISTOGRAM")
        
        with pb.add_table(visible_border=False) as t:
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='HistogramMin',
                                title= "Min", size=10)
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='HistogramMax',
                                title= "Max", size=10)
            
            with t.table_cell():
                pb.add_text_box(tool_attribute_name='HistogramStepSize',
                                title= "Step Size", size=10)
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ValueMatrixNumber, xtmf_WeightingMatrixNumber, xtmf_ScenarioNumber,
                 ReportFile, HistogramMin, HistogramMax, HistogramStepSize):
        
        
        self.ValueMatrix = _MODELLER.emmebank.matrix('mf%s' %xtmf_ValueMatrixNumber)
        if self.ValueMatrix == None:
            raise Exception("Full matrix mf%s was not found!" %xtmf_ValueMatrixNumber)
        
        if xtmf_WeightingMatrixNumber == 0:
            self.WeightingMatrix = None
        else:
            self.WeightingMatrix = _MODELLER.emmebank.matrix('mf%s' %xtmf_WeightingMatrixNumber)
            if self.WeightingMatrix == None:
                raise Exception("Full matrix mf%s was not found!" %xtmf_WeightingMatrixNumber)
        
        if xtmf_ScenarioNumber == 0:
            self.Scenario == None
        else:
            self.Scenario = _m.Modeller().emmebank.scenario(xtmf_ScenarioNumber)
            if (self.Scenario == None):
                raise Exception("Scenario %s was not found!" %xtmf_ScenarioNumber)
        
        self.ReportFile = ReportFile
        self.HistogramMin = HistogramMin
        self.HistogramMax = HistogramMax
        self.HistogramStepSize = HistogramStepSize
        
        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            originFilter = self._GetOriginFilterFunction()
            destinationFilter = self._GetDestinationFilterFunction()
            #print "Loaded filters"
            
            if self.Scenario:
                valueData = self.ValueMatrix.get_data(self.Scenario.number)
            else:
                valueData = self.ValueMatrix.get_data()
            #print "Got value matrix data"
            
            validIndices = [[p for p in valueData.indices[0] if originFilter(p)],
                            [q for q in valueData.indices[1] if destinationFilter(q)]]
            #print "Filtered indices"
            
            valueSubmatrix = get_submatrix(valueData, validIndices)
            #print "Prepared value submatrix"
            
            valueArray = array(valueSubmatrix.raw_data).flatten()
            
            #Start getting the relevant data from the matrix
            unweightedAverage = average(valueArray)
            minVal = min(valueArray)
            maxVal = max(valueArray)
            unweightedStdDev = std(valueArray)
            unweightedMedian = median(valueArray)
            #print "Calculated unweighted stats."
            
            #Create the array of bins
            bins = [self.HistogramMin]
            if minVal < self.HistogramMin: bins.insert(0, minVal)
            c = self.HistogramMin + self.HistogramStepSize
            while c < self.HistogramMax:
                bins.append(c)
                c += self.HistogramStepSize
            bins.append(self.HistogramMax)
            if maxVal > self.HistogramMax: bins.append(maxVal)
            #print "Bins:"
            #print bins
            
            unweightedHistogram, ranges = histogram(valueArray)
            #print "Extracted unweighted histogram"
            
            #Get weighted values if neccessary
            if self.WeightingMatrix != None:
                if self.Scenario:
                    weightData = self.WeightingMatrix.get_data(self.Scenario.number)
                else:
                    weightData = self.WeightingMatrix.get_data()
                #print "Loaded weighting data"
                
                weightSubmatrix = get_submatrix(weightData, validIndices)
                #print "Prepared weighting submatrix"
                
                weightArray = array(weightSubmatrix.raw_data).flatten()
                
                weightedAverage = average(valueArray, weights= weightArray)
                weightedStdDev = self._WtdStdDev(valueArray, weightArray)
                
                weightedHistogram, ranges = histogram(valueArray, weights= weightArray)
                #print "Extracted weighted histogram"
                
                if self.ReportFile:
                    self._WriteReportToFile(unweightedAverage,
                                            minVal, maxVal, unweightedStdDev, 
                                            unweightedMedian, unweightedHistogram, 
                                            bins, weightedAverage, weightedStdDev, 
                                            weightedHistogram)
            elif self.ReportFile:
                self._WriteReportToFile(unweightedAverage, minVal, 
                                        maxVal, unweightedStdDev, unweightedMedian, 
                                        unweightedHistogram, bins)
            print "Done writing report."

    ##########################################################################################################
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _GetOriginFilterFunction(self):
        exec('''def filter(p):
    %s''' %self.OriginFilterExpression)
        
        return filter
    
    def _GetDestinationFilterFunction(self):
        exec('''def filter(q):
    %s''' %self.DestinationFilterExpression)
        
        return filter
    
    def _WtdStdDev(self, values, weights):
        avg = average(values, weights=weights)
        variance = average((values-avg)**2, weights=weights)
        return sqrt(variance)
    
    def _WriteReportToLogbook(self, 
                            unweightedAverage,
                            minVal,
                            maxVal,
                            unweightedStdDev,
                            unweightedMedian,
                            unweightedHistogram,
                            bins,
                            weightedAverage=None,
                            weightedStdDev=None,
                            weightedHistogram=None):
        pb = _m.PageBuilder(title="Matrix Summary Report")
        
        #TODO: Record report to logbook
    
    def _WriteReportToFile(self,
                            unweightedAverage,
                            minVal,
                            maxVal,
                            unweightedStdDev,
                            unweightedMedian,
                            unweightedHistogram,
                            bins,
                            weightedAverage=None,
                            weightedStdDev=None,
                            weightedHistogram=None):
        
        with open(self.ReportFile, 'w') as writer:
            writer.write('''Matrix Summary Report
#####################

Generated on %s\n\n''' %dt.now())
            
            writer.write("Matrix: {id!s} - {desc!s} ({stamp!s})".format(id= self.ValueMatrix,
                                                                        desc= self.ValueMatrix.description,
                                                                        stamp= self.ValueMatrix.timestamp))
            
            writer.write("\nWeight Matrix: %s" %self.WeightingMatrix)
            if self.WeightingMatrix != None:
                writer.write(" - {desc!s} ({stamp!s})".format(desc= self.WeightingMatrix.description,
                                                              stamp = self.WeightingMatrix.timestamp))
            
            writer.write("\n\nAverage:\t%s" %unweightedAverage)
            writer.write("\nMinimum:\t%s" %minVal)
            writer.write("\nMaximum:\t%s" %maxVal)
            writer.write("\nStd. Dev:\t%s" %unweightedStdDev)
            writer.write("\n Median:\t%s" %unweightedMedian)
            
            if weightedAverage != None:
                writer.write("\nWeighted Avg.:\t%s" %weightedAverage)
            if weightedStdDev != None:
                writer.write("\nWeighted StDv:\t%s" %weightedStdDev)
           
            writer.write('''

-------------------------
HISTOGRAM
BinMin,BinMax,Freq''')
            
            if weightedHistogram != None: writer.write(",wFreq")
            
            for i, binEdge in enumerate(bins):
                if i == 0:
                    prevEdge = binEdge
                    continue #Skip the first
                
                if (i - 1) >= len(unweightedHistogram):
                    uwVal = 0.0
                else:
                    uwVal = unweightedHistogram[i - 1]
                writer.write("\n%s,%s,%s" %(prevEdge, binEdge, uwVal))
                
                if weightedHistogram != None:
                    if (i - 1) >= len(weightedHistogram):
                        wVal = 0.0
                    else:
                        wVal = weightedHistogram[i - 1]
                    writer.write(",%s" %wVal)
                    
                prevEdge = binEdge

                
    
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
        