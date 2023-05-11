"""
    Copyright 2023 Travel Modelling Group, Department of Civil Engineering, University of Toronto

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

import multiprocessing
import inro.modeller as _m
import os
from json import loads as _parsedict

_MODELLER = _m.Modeller()
_util = _MODELLER.module("tmg.common.utilities")


class SetTrafficTransitResults(_m.Tools()):
    # ---Parameters---
    Scenario = _m.Attribute(str)
    has_traffic = _m.Attribute(int)
    has_transit = _m.Attribute(int)

    def __init__(self):
        self.Scenario = _MODELLER.scenario
        self.HasTraffic = 0
        self.HasTransit = 0

    def __call__(self, ScenarioNumber, HasTraffic, HasTransit):
        Scenario = _m.Modeller().emmebank.scenario(ScenarioNumber)
        if Scenario is None:
            raise Exception("Scenario %s was not found!" % ScenarioNumber)
        try:
            self._execute(Scenario, HasTraffic, HasTransit)
        except Exception as e:
            raise Exception(_util.formatReverseStack())

    def _execute(self, Scenario, HasTraffic, HasTransit):
        if HasTraffic != 0:
            self._set_has_traffic(Scenario, HasTraffic)
        if HasTransit != 0:
            self._set_has_traffic(Scenario, HasTransit)

    def _set_has_traffic(self, Scenario, HasTraffic):
        if HasTraffic == 1:
            Scenario.has_traffic_results = True
        elif HasTraffic == 2:
            Scenario.has_traffic_results = False

    def _set_has_transit(self, Scenario, HasTransit):
        if HasTransit == 1:
            Scenario.has_traffic_results = True
        elif HasTransit == 2:
            Scenario.has_traffic_results = False
