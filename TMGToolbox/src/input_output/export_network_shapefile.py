"""
    Copyright 2017 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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
"""

import inro.modeller as _m
import traceback as _traceback
from contextlib import contextmanager
from os import path as _path
from datetime import datetime as _dt
import shutil as _shutil
import zipfile as _zipfile
import tempfile as _tf

_MODELLER = _m.Modeller()  # Instantiate Modeller once.
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_exportShapefile = _MODELLER.module('inro.emme.data.network.export_network_as_shapefile')

class ExportNetworkAsShapefile(_m.Tool()):
    version = '0.0.1'
    tool_run_msg = ""
    number_of_tasks = 1

    scenario = _m.Attribute(_m.InstanceType)
    export_path = _m.Attribute(str)
    transit_shapes = _m.Attribute(str)
    def __init__(self):
        # Init internal variables
        self.TRACKER = _util.ProgressTracker(self.number_of_tasks)  # init the ProgressTracker

        # Set the defaults of parameters used by Modeller
        self.scenario = _MODELLER.scenario  # Default is primary scenario
        self.ExportMetadata = ""

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(
            self, title="Export Network as Shapefile v%s" % self.version,
            description="Not Callable from Modeller. Please use XTMF. EXPERIMENTAL",
            branding_text="- XTMF")
        return pb.render()

    def __call__(self, xtmf_exportPath, xtmf_transitShapes, xtmf_scenario):
        self.export_path = xtmf_exportPath
        self.transit_shapes = xtmf_transitShapes
        self.scenario = _m.Modeller().emmebank.scenario(xtmf_scenario)

        try:          
                print "Starting export."
                self._execute()
                print "Export complete."  
        except Exception, e:
            raise Exception(_util.formatReverseStack())

    def _execute(self):
        if self.transit_shapes == '' or self.transit_shapes == None or self.transit_shapes == ' ':
            self.transit_shapes == 'SEGMENTS'

        _exportShapefile(export_path = self.export_path, transit_shapes = self.transit_shapes, scenario = self.scenario)




