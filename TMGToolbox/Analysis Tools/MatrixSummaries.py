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
Export Matrix Summary

    Authors: pkucirek

    Latest revision by: pkucirek
    
    
    Computes using numpy a several aggregate statistics 
    for a given matrix: average, median, standard deviation, and 
    a histogram of values. Users can also specify an optional matrix 
    of weights, and the tool will also compute weighted average, 
    standard deviation, and histogram values.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created on 2014-01-30 by pkucirek
    
    1.0.0 Added description/better documentation for release. Could not get logbook
        reporting to work properly, so this feature will be added in a later release.
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from numpy import average, histogram, array, min, max, std, median
from math import sqrt
from inro.emme.matrix import submatrix as get_submatrix
from datetime import datetime as dt
from os import path
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class MatrixSummary(_m.Tool()):
    
    version = '1.0.0'
    tool_run_msg = ""
    number_of_tasks = 8 # For progress reporting, enter the integer number of tasks here
    
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
    xtmf_OriginRangeSetString = _m.Attribute(str)
    xtmf_DestinationRangeSetString = _m.Attribute(str)
    
    
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
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Export Matrix Summary v%s" %self.version,
                     description="Computes using <em>numpy</em> a several aggregate statistics \
                         for a given matrix: average, median, standard deviation, and \
                         a histogram of values. Users can also specify an optional matrix \
                         of weights, and the tool will also compute weighted average, \
                         standard deviation, and histogram values.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        pb.add_select_matrix(tool_attribute_name='ValueMatrix',
                             filter=['FULL'], allow_none=False,
                             title="Value Matrix")
        
        pb.add_select_matrix(tool_attribute_name='WeightingMatrix',
                             filter=['FULL'], allow_none=True,
                             title="Weighting Matrix",
                             note="<font color='green'><b>Optional:</b></font> Matrix of weights")
        
        pb.add_select_file(tool_attribute_name='ReportFile',
                           window_type='save_file',
                           file_filter='*.txt',
                           title="Report File",
                           note="<font color='green'><b>Optional.</b></font> Matrix data will be \
                               saved to the logbook.")
        
        pb.add_select_scenario(tool_attribute_name='Scenario',
                               title='Scenario:',
                               allow_none=True,
                               note="<font color='green'><b>Optional:</b></font> Only required if \
                                   scenarios have differing zone systems.")
        
        pb.add_header('FILTERS')
        
        pb.add_text_box(tool_attribute_name='OriginFilterExpression',
                        size=100, multi_line=False,
                        title="def OriginFilter(p):",
                        note="Enter a Python expression. Include the return statement.")
        
        pb.add_text_box(tool_attribute_name='DestinationFilterExpression',
                        size=100, multi_line=False,
                        title="def DestinationFilter(q):",
                        note="Enter a Python expression. Include the return statement")
        
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
            originFilter = self._GetOriginFilterFunction()
            destinationFilter = self._GetDestinationFilterFunction()
            
            self._Execute(originFilter, destinationFilter)
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
        
        self.tool_run_msg = _m.PageBuilder.format_info("Done.")
    
    def __call__(self, xtmf_ValueMatrixNumber, xtmf_WeightingMatrixNumber, xtmf_ScenarioNumber,
                 ReportFile, HistogramMin, HistogramMax, HistogramStepSize, xtmf_OriginRangeSetString,
                 xtmf_DestinationRangeSetString):
        
        
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
        
        originFilter = self._ParseRangeSetString(xtmf_OriginRangeSetString)
        destinationFilter = self._ParseRangeSetString(xtmf_DestinationRangeSetString)
        
        self.ReportFile = ReportFile
        self.HistogramMin = HistogramMin
        self.HistogramMax = HistogramMax
        self.HistogramStepSize = HistogramStepSize
        
        try:
            self._Execute(originFilter, destinationFilter)
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)
    
    ##########################################################################################################    
    
    
    def _Execute(self, originFilter, destinationFilter):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            if self.Scenario:
                valueData = self.ValueMatrix.get_data(self.Scenario.number)
            else:
                valueData = self.ValueMatrix.get_data()
            self.TRACKER.completeTask() #1
            
            validIndices = [[p for p in valueData.indices[0] if originFilter(p)],
                            [q for q in valueData.indices[1] if destinationFilter(q)]]
            self.TRACKER.completeTask() #2
            
            valueSubmatrix = get_submatrix(valueData, validIndices)
            valueArray = array(valueSubmatrix.raw_data).flatten()
            self.TRACKER.completeTask() #3
            
            self.TRACKER.startProcess(6)
            #Start getting the relevant data from the matrix
            unweightedAverage = average(valueArray)
            self.TRACKER.completeSubtask()
            minVal = min(valueArray)
            self.TRACKER.completeSubtask()
            maxVal = max(valueArray)
            self.TRACKER.completeSubtask()
            unweightedStdDev = std(valueArray)
            self.TRACKER.completeSubtask()
            unweightedMedian = median(valueArray)
            self.TRACKER.completeSubtask()
            
            #Create the array of bins
            bins = [self.HistogramMin]
            if minVal < self.HistogramMin: bins.insert(0, minVal)
            c = self.HistogramMin + self.HistogramStepSize
            while c < self.HistogramMax:
                bins.append(c)
                c += self.HistogramStepSize
            bins.append(self.HistogramMax)
            if maxVal > self.HistogramMax: bins.append(maxVal)
            
            unweightedHistogram, ranges = histogram(valueArray, bins)
            self.TRACKER.completeSubtask()
            self.TRACKER.completeTask() #4
            
            #Get weighted values if neccessary
            if self.WeightingMatrix != None:
                if self.Scenario:
                    weightData = self.WeightingMatrix.get_data(self.Scenario.number)
                else:
                    weightData = self.WeightingMatrix.get_data()
                self.TRACKER.completeTask() #5
                
                weightSubmatrix = get_submatrix(weightData, validIndices)
                weightArray = array(weightSubmatrix.raw_data).flatten()
                self.TRACKER.completeTask() #6
                
                self.TRACKER.startProcess(3)
                weightedAverage = average(valueArray, weights= weightArray)
                self.TRACKER.completeSubtask()
                weightedStdDev = self._WtdStdDev(valueArray, weightArray)
                self.TRACKER.completeSubtask()
                weightedHistogram, ranges = histogram(valueArray, weights= weightArray, bins = bins)
                self.TRACKER.completeSubtask()
                self.TRACKER.completeTask() #7
                
                
                if self.ReportFile:
                    self._WriteReportToFile(unweightedAverage,
                                            minVal, maxVal, unweightedStdDev, 
                                            unweightedMedian, unweightedHistogram, 
                                            bins, weightedAverage, weightedStdDev, 
                                            weightedHistogram)
                    print "Report written to %s" %self.ReportFile
                
                self._WriteReportToLogbook(unweightedAverage, minVal, maxVal, unweightedStdDev, 
                                           unweightedMedian, unweightedHistogram, bins, 
                                           weightedAverage, weightedStdDev, weightedHistogram)
                print "Report written to logbook."
                
            elif self.ReportFile:
                for i in range(3): self.TRACKER.completeTask()
                self._WriteReportToFile(unweightedAverage, minVal, 
                                        maxVal, unweightedStdDev, unweightedMedian, 
                                        unweightedHistogram, bins)
                print "Report written to %s" %self.ReportFile
                
                self._WriteReportToLogbook(unweightedAverage, minVal, maxVal, unweightedStdDev, 
                                           unweightedMedian, unweightedHistogram, bins)
                print "Report written to logbook."
                
            else:
                self._WriteReportToLogbook(unweightedAverage, minVal, maxVal, unweightedStdDev, 
                                           unweightedMedian, unweightedHistogram, bins)
                print "Report written to logbook."
            
            
            
            self.TRACKER.completeTask() #8

    ##########################################################################################################
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Scenario" : str(self.Scenario),
                "Version": self.version, 
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts
    
    def _ParseRangeSetString(self, rss):
        ranges = []
        cells = rss.split(',')
        for c in cells:
            r = c.split('-')
            start = int(r[0])
            end = int(r[1])
            rs = _util.IntRange(start, end)
            ranges.append(rs)
        
        def filter(v):
            for r in ranges:
                if v in r: return True
            return False
        
        return filter
    
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
        
        #print "CURRENTLY DOES NOT WRITE REPORT TO LOGBOOK"
        #return
        
        pb = _m.PageBuilder(title="Matrix Summary Report")
        
        bodyText = "Summary for matrix: <b>{mtx1!s} - {desc1}</b> ({stamp1!s})\
        <br>Weighting Matrix: <b>{mtx2!s}".format(
                                                  mtx1= self.ValueMatrix, 
                                                  mtx2= self.WeightingMatrix,
                                                  desc1= self.ValueMatrix.description, 
                                                  stamp1= self.ValueMatrix.timestamp)
        if self.WeightingMatrix != None: bodyText += " - %s" %self.WeightingMatrix.description
        bodyText += "</b><br>"
        
        rows = []
        rows.append("<b>Average:</b> %s" %unweightedAverage)
        rows.append("<b>Minimum:</b> %s" %minVal)
        rows.append("<b>Maximum:</b> %s" %maxVal)
        rows.append("<b>Standard Deviation:</b> %s" %unweightedStdDev)
        rows.append("<b>Median:</b> %s" %unweightedMedian)
        
        if weightedAverage != None:
            rows.append("<br><br><b>Weighted Average:</b> %s" %weightedAverage)
            rows.append("<b>Weighted Standard Deviation:</b> %s" %weightedStdDev)
        
        bodyText += "<h3>Matrix Statistics</h3>" + "<br>".join(rows)
        pb.add_text_element(bodyText)
        
        #Build the chart data
        uwData = []
        wData = []
        for i, binEdge in enumerate(bins):
            if i == 0:
                prevEdge = binEdge
                continue #Skip the first
            
            if (i - 1) >= len(unweightedHistogram):
                uwVal = 0.0
            else:
                uwVal = unweightedHistogram[i - 1]
            uwData.append((int(prevEdge), float(uwVal)))
            
            if weightedHistogram != None:
                if (i - 1) >= len(weightedHistogram):
                    wVal = 0.0
                else:
                    wVal = weightedHistogram[i - 1]
                wData.append((int(prevEdge), float(wVal)))
            
            prevEdge = binEdge
        
        cds = [{"title": "Unweighted frequency", 
                "data": uwData,
                "color": "red"}]
        if weightedHistogram != None:
            cds.append({"title": "Weighted frequency",
                        "data": wData,
                        "color": "blue"})
        
        try:
            pb.add_chart_widget(chart_data_series=cds,
                options= {'table': True,
                          "plot_parameters": {
                               "series": {
                                   "stack": False,
                                   #"points": {"show": False},
                                   #"lines": {"show": False},
                                   "bars": {"show": True},
                                        }
                                    }
                          })
        except Exception, e:
            print cds
            raise
        
        _m.logbook_write("Matrix Summary Report for %s" %self.ValueMatrix,
                         value= pb.render())
    
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
        