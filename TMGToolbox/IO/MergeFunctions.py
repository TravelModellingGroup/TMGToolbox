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
Merge Functions

    Authors: Peter Kucirek

    Latest revision by: 
    
    
    Merges functions from a .411 file, throwing an Exception if 
    a conflict of expression arises.
        
'''
#---VERSION HISTORY
'''
    0.0.1 Created
    
    0.1.0 Major overhaul of the popup GUI, which now displays all necessary changes at once.
    
    0.1.1 Bug fix to work properly with exported functions in a NWP file
    
    0.1.2 Minor update to check for null export file
    
    0.1.3 Conflicted functions are now sorted in alphabetical order
    
'''

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from contextlib import nested
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt
from os import path as _path
_MODELLER = _m.Modeller() #Instantiate Modeller once.
_util = _MODELLER.module('TMG2.Common.Utilities')
_tmgTPB = _MODELLER.module('TMG2.Common.TmgToolPageBuilder')

##########################################################################################################

class MergeFunctions(_m.Tool()):
    
    version = '0.1.3'
    tool_run_msg = ""
    number_of_tasks = 3 # For progress reporting, enter the integer number of tasks here
    
    # Tool Input Parameters
    #    Only those parameters neccessary for Modeller and/or XTMF to dock with
    #    need to be placed here. Internal parameters (such as lists and dicts)
    #    get intitialized during construction (__init__)
    
    FunctionFile = _m.Attribute(str)
    RevertOnError = _m.Attribute(bool)
    
    def __init__(self):
        #---Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks) #init the ProgressTracker
        
        #---Set the defaults of parameters used by Modeller
        self.RevertOnError = True
    
    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Merge Functions v%s" % self.version,
                     description="Merges into this emmebank functions defined in a standard \
                         function transaction file. Delete and modify commands are ignored.\
                         <br><br>Detects conflicts in functional definitions and prompts \
                         user for input. New functions as simply merged in.",
                     branding_text="TMG")
        
        if self.tool_run_msg != "": # to display messages in the page
            pb.tool_run_status(self.tool_run_msg_status)
        
        baseFolder = _path.dirname(_MODELLER.desktop.project_file_name())
        pb.add_select_file(tool_attribute_name='FunctionFile',
                           window_type='file', start_path=baseFolder,
                           title="Functions File")
        
        pb.add_checkbox(tool_attribute_name='RevertOnError',
                        label="Revert on error?")
        
        return pb.render()
    
    ##########################################################################################################
        
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        
        if self.FunctionFile == None:
            raise IOError("Import file not specified")
        
        try:
            self._Execute()
        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise
    
    ##########################################################################################################    
    
    
    def _Execute(self):
        with _m.logbook_trace(name="{classname} v{version}".format(classname=(self.__class__.__name__), version=self.version),
                                     attributes=self._GetAtts()):
            
            file_functions = self._LoadFunctionFile()
            self.TRACKER.completeTask()
            
            database_functions = self._LoadFunctionsInDatabank()
            self.TRACKER.completeTask()
            
            newFuncCount, modFuncCount = self._MergeFunctions(database_functions, file_functions)
            self.TRACKER.completeTask()
            
            msg = "Done."
            if newFuncCount > 0:
                msg += " %s functions added." %newFuncCount
            if modFuncCount > 0:
                msg += " %s functions modified." %modFuncCount
            self.tool_run_msg = _m.PageBuilder.format_info(msg)
            _m.logbook_write(msg)

    ##########################################################################################################

    #----CONTEXT MANAGERS---------------------------------------------------------------------------------
    '''
    Context managers for temporary database modifications.
    '''
    
    @contextmanager
    def _NewFunctionMANAGER(self, newFunctions, modifiedFunctions):
        emmebank = _MODELLER.emmebank
        
        try:
            yield # Yield return a temporary object
        except Exception, e:
            if self.RevertOnError:
                for id in newFunctions:
                    emmebank.delete_function(id)
                for id, expression in modifiedFunctions.iteritems():
                    emmebank.function(id).expression = expression
            raise
    
    
    #----SUB FUNCTIONS---------------------------------------------------------------------------------  
    
    def _GetAtts(self):
        atts = {
                "Functions File" : self.FunctionFile,
                "Version": self.version,
                "self": self.__MODELLER_NAMESPACE__}
            
        return atts 
    
    def _LoadFunctionFile(self):
        functions = {}
        with open(self.FunctionFile) as reader:
            expressionBuffer = ""
            trecord = False
            currentId = None
            
            for line in reader:
                line = line.rstrip()
                linecode = line[0]
                record = line[2:]
                
                if linecode == 'c':
                    pass
                elif linecode == 't':
                    if not record.startswith("functions"):
                        raise IOError("Wrong t record!")
                    trecord = True
                elif linecode == 'a':
                    if not trecord: raise IOError("A before T")
                    if currentId != None:
                        functions[currentId] = expressionBuffer
                        currentId = None
                        expressionBuffer = ""
                    index = record.index('=')
                    currentId = record[:index].strip()
                    expressionBuffer = record[(index + 1):].replace(' ', '')
                elif linecode == ' ':
                    if currentId != None and trecord:
                        s = record.strip().replace(' ', '')
                        expressionBuffer += s
                    else: raise IOError("Blank line not in function definition")
                elif linecode == 'd' or linecode == 'm':
                    if currentId != None:
                        functions[currentId] = expressionBuffer
                        currentId = None
                        expressionBuffer = ""
                else: raise KeyError(linecode)
                    
        return functions
    
    def _LoadFunctionsInDatabank(self):
        functions = {}
        for func in _MODELLER.emmebank.functions():
            expr = func.expression.replace(' ', '')
            functions[func.id] = expr
        return functions
    
    def _MergeFunctions(self, databaseFunctions, fileFunctions):
        emmebank = _MODELLER.emmebank
        
        
        databaseIds = set([key for key in databaseFunctions.iterkeys()])
        fileIds = set([key for key in fileFunctions.iterkeys()])
        
        newFunctions = []
        modifiedFunctions = {}
        with self._NewFunctionMANAGER(newFunctions, modifiedFunctions):
            for id in (fileIds - databaseIds): #Functions in the new source only
                expression = fileFunctions[id]
                emmebank.create_function(id, expression)
                _m.logbook_write("Added %s : %s" %(id, expression))
                newFunctions.append(id)
            
            conflicts = []
            for id in (fileIds & databaseIds): #Functions in both sources
                database_expression = databaseFunctions[id]
                file_expression = fileFunctions[id]
                if file_expression != database_expression:
                    conflicts.append((id, database_expression, file_expression))
            
            if len(conflicts) > 0:
                conflicts.sort()
                dialog = FunctionConflictDialog(conflicts)
                result = dialog.exec_()
                
                if result == dialog.Accepted:
                    acceptedChanges = dialog.getFunctionsToChange()
                    for fid, expression in acceptedChanges.iteritems():
                        func = _MODELLER.emmebank.function(fid)
                        oldExpression = func.expression
                        func.expression = expression
                        modifiedFunctions[fid] = oldExpression
                        
                        with _m.logbook_trace("Modified function %s" %fid.upper()):
                            _m.logbook_write("Old expression: %s" %oldExpression)
                            _m.logbook_write("New expression: %s" %expression)
                dialog.deleteLater()
                        
        return len(newFunctions), len(modifiedFunctions)
        
    @_m.method(return_type=_m.TupleType)
    def percent_completed(self):
        return self.TRACKER.getProgress()
                
    @_m.method(return_type=unicode)
    def tool_run_msg_status(self):
        return self.tool_run_msg
    
##########################################################################################

class FunctionConflictDialog(QtGui.QDialog):
    
    def __init__(self, data):
        super(FunctionConflictDialog, self).__init__()
        
        self.setWindowTitle("Function Conflict")
        infoText = QtGui.QLabel("""Conflicts detected between the database and the network package \
file for the following function(s). Please resolve these conflicts by indicating which version(s) to save \
in the database.""")
        infoText.setWordWrap(True)
        infoText.setAlignment(Qt.AlignJustify)
        #infoText.setFrameShadow(infoText.Sunken)
        #infoText.setFrameStyle(infoText.StyledPanel)
        infoText.setMargin(5)
        
        self.dataRows = []
        
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(infoText)
        vbox.addSpacing(15)
        
        headerGrid = self.buildHeaderGrid()
        vbox.addLayout(headerGrid)
        
        mainGrid = self.buildMainGrid(data)
        mainGridWrapper = QtGui.QWidget()
        mainGridWrapper.setLayout(mainGrid)
        scrollArea = QtGui.QScrollArea()
        scrollArea.setWidget(mainGridWrapper)
        scrollArea.setMaximumHeight(220)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollArea.setFrameShadow(QtGui.QFrame.Sunken)
        scrollArea.setFrameStyle(QtGui.QFrame.StyledPanel)
        scrollArea.setWidgetResizable(True)
        
        vbox.addWidget(scrollArea)
        
        footerGrid = self.buildFooterGrid()
        vbox.addLayout(footerGrid)
        
        vbox.addSpacing(10)
        vbox.addLayout(self.buildFooterButtons())
        
        self.syncGridWidths(headerGrid, mainGrid, footerGrid)
        
        self.setLayout(vbox)
        self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        
        self.setResult(self.Rejected)
        
    def buildHeaderGrid(self):
        headerGrid = QtGui.QGridLayout()
        
        idLabel = QtGui.QLabel("Id")
        dbLabel = QtGui.QLabel("Database")
        fileLabel = QtGui.QLabel("File")
        otherLabel = QtGui.QLabel("Other")
        expLabel = QtGui.QLabel("  Expression")
        
        font = idLabel.font()
        font.setBold(True)
        idLabel.setFont(font)
        dbLabel.setFont(font)
        fileLabel.setFont(font)
        otherLabel.setFont(font)
        expLabel.setFont(font)
        
        headerGrid.setMargin(2)
        headerGrid.setColumnMinimumWidth(0,3)
        headerGrid.addWidget(idLabel, 0, 1, 1, 1, Qt.AlignHCenter)
        headerGrid.addWidget(dbLabel, 0, 2, 1, 1, Qt.AlignHCenter)
        headerGrid.addWidget(fileLabel, 0, 3, 1, 1, Qt.AlignHCenter)
        headerGrid.addWidget(otherLabel, 0, 4, 1, 1, Qt.AlignHCenter)
        headerGrid.addWidget(expLabel, 0, 5, 1, 1, Qt.AlignLeft)
        
        return headerGrid
    
    def buildMainGrid(self, data):
        mainGrid = QtGui.QGridLayout()
        
        row = 0
        for fid, dbExpression, fileExpression in data:
            rowDataWrapper = FunctionRowDataWrapper(fid, dbExpression, fileExpression, row, mainGrid, self)
            self.dataRows.append(rowDataWrapper)
            row += 1
            
            strut = QtGui.QFrame()
            strut.setFrameShadow(strut.Raised)
            strut.setFrameShape(strut.HLine)
            mainGrid.addWidget(strut, row, 0, 1, 5)
            row += 1
        mainGrid.setColumnStretch(4, 1.0)
        
        return mainGrid
    
    def buildFooterGrid(self):
        footerGrid = QtGui.QGridLayout()
        
        label = QtGui.QLabel("All")
        
        self.dbCheckBox = QtGui.QRadioButton()
        self.dbCheckBox.setAutoExclusive(False)
        self.dbCheckBox.toggled.connect(self.dbButtonToggled)
        self.fCheckBox = QtGui.QRadioButton()
        self.fCheckBox.setAutoExclusive(False)
        self.fCheckBox.toggled.connect(self.fButtonToggled)
        
        self.dbCheckBox.click()
        
        footerGrid.setColumnMinimumWidth(0, 10)
        footerGrid.addWidget(label, 0, 1, 1, 1, Qt.AlignHCenter)
        footerGrid.addWidget(self.dbCheckBox, 0, 2, 1, 1, Qt.AlignHCenter)
        footerGrid.addWidget(self.fCheckBox, 0, 3, 1, 1, Qt.AlignHCenter)
        
        return footerGrid
    
    def syncGridWidths(self, headerGrid, mainGrid, footerGrid):
        rowCount = mainGrid.rowCount()
        for columnNumber in range(5):
            width = 0
            
            def getWidth(grid, row, col):
                item = grid.itemAtPosition(row, col)
                width = 0
                if item != None:
                    width = item.widget().sizeHint().width()
                return width
            
            width = max(width, getWidth(headerGrid, 0, columnNumber + 1))
            for row in range(rowCount):
                width = max(width, getWidth(mainGrid, row, columnNumber))
            if columnNumber < 3: minWidth = max(width, getWidth(footerGrid, 0, columnNumber + 1))
            
            headerGrid.setColumnMinimumWidth(columnNumber + 1, width)
            mainGrid.setColumnMinimumWidth(columnNumber, width)
            if columnNumber < 3: footerGrid.setColumnMinimumWidth(columnNumber + 1, width)
        headerGrid.setColumnStretch(6, 1.0)
        footerGrid.setColumnStretch(4, 1.0)          
    
    def buildFooterButtons(self):
        hbox = QtGui.QHBoxLayout()
        
        saveButton = QtGui.QPushButton("Save")
        saveButton.clicked.connect(self.accept)
        cancelButton = QtGui.QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)
        
        hbox.addWidget(saveButton)
        hbox.addWidget(cancelButton)
        hbox.addStretch(1.0)
        
        return hbox
    
    def dbButtonToggled(self):
        if self.dbCheckBox.isChecked():
            for row in self.dataRows:
                row.dbButton.click()
    def fButtonToggled(self):
        if self.fCheckBox.isChecked():
            for row in self.dataRows:
                row.fButton.click()
    
    def selectAllDB(self, state):
        if state == QtCore.Qt.Checked:
            self.fCheckBox.setChecked(False)
            for row in self.dataRows:
                row.dbButton.click()
    
    def selectAllFile(self, state):
        if state == QtCore.Qt.Checked:
            self.dbCheckBox.setChecked(False)
            for row in self.dataRows:
                row.fButton.click()
            self.fCheckBox.setChecked(True)
            
    def accept(self):
        super(FunctionConflictDialog, self).accept()
        self.close()
        
    def getFunctionsToChange(self):
        changes = {}
        for dataRow in self.dataRows:
            state = dataRow.buttonGroup.checkedId()
            if state == 1: continue #Function is flagged to not be changed
            
            fid = dataRow.fid
            expression = dataRow.textBox.text()
            
            changes[fid] = expression
        return changes
        
class FunctionRowDataWrapper():
    
    def __init__(self, fid, dbExpression, fileExpression, rowNumber, gridLayout, parent):
        self.fid = fid
        self.dbExpression = dbExpression
        self.fileExpression = fileExpression
        self.parent = parent
        
        label = QtGui.QLabel(fid.upper())
        gridLayout.addWidget(label, rowNumber, 0, 1, 1, QtCore.Qt.AlignHCenter)
        
        self.buttonGroup = QtGui.QButtonGroup()
        self.dbButton = QtGui.QRadioButton()
        self.dbButton.setChecked(True)
        self.fButton = QtGui.QRadioButton()
        self.oButton = QtGui.QRadioButton()
        self.buttonGroup.addButton(self.dbButton, 1)
        self.buttonGroup.addButton(self.fButton, 2)
        self.buttonGroup.addButton(self.oButton, 3)
        gridLayout.addWidget(self.dbButton, rowNumber, 1, 1, 1, QtCore.Qt.AlignHCenter)
        gridLayout.addWidget(self.fButton, rowNumber, 2, 1, 1, QtCore.Qt.AlignHCenter)
        gridLayout.addWidget(self.oButton, rowNumber, 3, 1, 1, QtCore.Qt.AlignHCenter)
        
        self.textBox = ActuatedTextBox()
        self.textBox.setText(self.dbExpression)
        self.textBox.adjustSize()
        #self.textBox.setMinimumWidth(150)
        #self.textBox.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Fixed)
        gridLayout.addWidget(self.textBox, rowNumber, 4)
                
        self.dbButton.clicked.connect(self.onDbButtonClick)
        self.fButton.clicked.connect(self.onFileButtonClick)
        self.oButton.clicked.connect(self.onOtherButtonClick)
        self.textBox.clicked.connect(self.onTextBoxClick)
    
    def onDbButtonClick(self):
        self.textBox.setText(self.dbExpression)
        self.parent.fCheckBox.setChecked(False)
    
    def onFileButtonClick(self):
        self.textBox.setText(self.fileExpression)
        self.parent.dbCheckBox.setChecked(False) 
    
    def onTextBoxClick(self):
        self.oButton.click()
    
    def onOtherButtonClick(self):
        self.parent.fCheckBox.setChecked(False)
        self.parent.dbCheckBox.setChecked(False)
    
class ActuatedTextBox(QtGui.QLineEdit):
    
    clicked = QtCore.pyqtSignal()
    
    def __init__(self, contents="", parent=None):
        super(ActuatedTextBox, self).__init__(contents, parent)
    
    def mousePressEvent(self, event):
        super(ActuatedTextBox, self).mousePressEvent(event)
        self.clicked.emit()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
