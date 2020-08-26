# ---LICENSE----------------------
'''
    Copyright 2020 Travel Modelling Group, Department of Civil Engineering, University of Toronto
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
# ---METADATA---------------------
'''
    Estimate Transit Operating Costs

    Author: Peter Lai

    Description: Computes estimated route-by-route transit operating costs for the time period depicted 
                 by the selected scenario, in addition to revenue hours, revenue kilometres, and 
                 estimated vehicle count. Individual transit lines are grouped into routes.
    
'''
#---VERSION HISTORY
'''
    1.0.0 Created by Peter Lai on 2020-08-26

'''

import inro.modeller as _m
import traceback as _traceback
import datetime
import math
_MODELLER = _m.Modeller()
_util = _MODELLER.module('tmg.common.utilities')

#######################################################################################################


class EstimateTransitOperatingCosts(_m.Tool()):

    version = '1.0.0'
    tool_run_msg = ""
    Scenario = _m.Attribute(_m.InstanceType)
    xtmf_ScenarioNumber = _m.Attribute(int)
    ServiceTableFile = _m.Attribute(str)
    CostParamsFile = _m.Attribute(str)
    ReportFile = _m.Attribute(str)
    # DebugFile = _m.Attribute(str)

    def __init__(self):
        self.Scenario = _MODELLER.scenario  # set primary scenario as default
        self.HasTransitResults = False
        self.params = []

        self.time_period = 'AM'
        self.time_period_start = datetime.time(6, 00, 00)
        self.time_period_end = datetime.time(8, 59, 59)
        self.time_period_duration = 3.0

        # Threshold Values:
        self.short_len_th = 1.90
        self.low_freq_th = 2
        self.len_diff_th = 2.00
        self.rt_diff_th = 5.00
        self.hdwy_diff_th = 11.00
        self.tc_diff_div_th = 0.15
        self.tccond_th = 10

        # Column Indices for Each Line:
        self.idx_mode = 2
        self.idx_len = 4
        self.idx_startpt = 5
        self.idx_endpt = 6
        self.idx_time_act = 7
        self.idx_time_sch = 8
        self.idx_hdwy_new = 9
        self.idx_tc = 10

    #######################################################################################################

    def page(self):
        pb = _m.ToolPageBuilder(self)
        pb.title = "Estimate Transit Operating Costs"
        pb.description = "Computes estimated route-by-route transit operating costs for the time period depicted " \
                         "by the selected scenario, in addition to revenue hours, revenue kilometres, and estimated " \
                         "vehicle count. Individual transit lines are grouped into routes."
        pb.branding_text = "TMG Toolbox"
        pb.add_select_scenario(tool_attribute_name='Scenario', title='Scenario:', allow_none=False,
                               note="Select the scenario to perform the cost computation for. Be sure to have the time "
                                    "period information (AM, MD, PM, EV, or ON) present in the scenario title. "
                                    "For time periods other than ON, please select a scenario with completed transit "
                                    "assignment results for better accuracy.")
        pb.add_select_file(tool_attribute_name='ServiceTableFile', title='Service Table File:', file_filter="*.csv",
                           window_type='file',
                           note="The Service Table file contains three columns with a header row: emme_id, trip_depart,"
                                " trip_arrive. emme_id is the Emme transit line ID, and trip_depart and trip_arrive "
                                "are the start and end times of each scheduled transit trip in HH:MM:SS.")
        pb.add_select_file(tool_attribute_name='CostParamsFile', title='Cost Parameters File:', file_filter="*.csv",
                           window_type='file',
                           note="The Cost Parameters file contains ten columns with a header row: "
                                "<ul><li>agency_prefix: one or two capital letters</li>"
                                "<li>mode: the ID of the mode the set of parameters is for</li>"
                                "<li>uc_revhr: unit cost per revenue hour</li>"
                                "<li>uc_revkm: unit cost per revenue km</li>"
                                "<li>uc_veh_annual: annual unit cost per peak vehicle</li>"
                                "<li>uc_veh_daily: daily unit cost per peak vehile. Only one of uc_veh_annual and "
                                "uc_veh_daily is required.</li>"
                                "<li>weekday_ratio_revhr: multiplier to get annual estimates of revenue hours from a "
                                "weekday daily value</li>"
                                "<li>weekday_ratio_revkm: multiplier to get annual estimates of revenue km from a "
                                "weekday daily value</li>"
                                "<li>adj_revhr: calibrated adjustment factor for revenue hours</li>"
                                "<li>adj_revkm: calibrated adjustment factor for revenue km</li></ul>")
        pb.add_select_file(tool_attribute_name='ReportFile', title="Report File:", file_filter="*.csv",
                           window_type='save_file')
        # pb.add_select_file(tool_attribute_name='DebugFile', title="Debug File:", file_filter="*.csv",
        #                    window_type='save_file')
        if self.tool_run_msg:
            pb.add_html(self.tool_run_msg)
        return pb.render()

    def run(self):

        self._GetScenarioTimePeriodInfo()

        if self.ServiceTableFile is None:
            raise IOError("Service Table file not specified.")

        if self.CostParamsFile is None:
            raise IOError("Cost parameters file not specified.")

        if self.ReportFile is None:
            raise IOError("Output report file not specified.")

        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Completed!")

    def __call__(self, xtmf_ScenarioNumber, ServiceTableFile, CostParamsFile, ReportFile):

        self.Scenario = _MODELLER.emmebank.scenario(xtmf_ScenarioNumber)
        if self.Scenario is None:
            raise Exception("Scenario %s was not found!" % xtmf_ScenarioNumber)

        self._GetScenarioTimePeriodInfo()

        self.ServiceTableFile = ServiceTableFile
        self.CostParamsFile = CostParamsFile
        self.ReportFile = ReportFile

        try:
            self._Execute()
        except Exception as e:
            self.tool_run_msg = _m.PageBuilder.format_exception(e, _traceback.format_exc(e))
            raise

    def _Execute(self):

        with _m.logbook_trace(
                name="{classname} v{version}".format(classname=self.__class__.__name__, version=self.version),
                attributes=self._GetLogbookAttributes()):

            lines = self._GetAllLinesInfo()
            servt = self._ReadInputCSV(self.ServiceTableFile)
            self.params = self._ReadInputCSV(self.CostParamsFile)
            self._ValidateCostParamsFile()

            lines = self._CalculatePrelimLineProperties(lines, servt)
            routes = self._GroupLinesIntoRoutes(lines)
            routes = self._CleanDuplicateLines(routes)
            routes_unbalanced = list(routes)

            routes, do_not_pair = self._BalanceDirections(routes)
            pairs = self._GenerateDirectionPairs(routes, do_not_pair)

            route_ids, veh_no, mode = self._ComputeVehicleCount(routes, pairs)
            rev_hr, rev_km, cost = self._ComputeCost(routes_unbalanced, veh_no)

            self._ExportResults(self.ReportFile, route_ids, mode, rev_hr, rev_km, veh_no, cost)

    #######################################################################################################

    # ---------- Sub Functions: Setup and Main Execution ----------

    def _GetScenarioTimePeriodInfo(self):

        self.HasTransitResults = self.Scenario.has_transit_results

        if 'AM' in self.Scenario.title:
            self.time_period = 'AM'
            self.time_period_start = datetime.time(6, 00, 00)
            self.time_period_end = datetime.time(8, 59, 59)
            self.time_period_duration = 3.0
        elif 'MD' in self.Scenario.title:
            self.time_period = 'MD'
            self.time_period_start = datetime.time(9, 00, 00)
            self.time_period_end = datetime.time(14, 59, 59)
            self.time_period_duration = 6.0
        elif 'PM' in self.Scenario.title:
            self.time_period = 'PM'
            self.time_period_start = datetime.time(15, 00, 00)
            self.time_period_end = datetime.time(18, 59, 59)
            self.time_period_duration = 4.0
        elif 'EV' in self.Scenario.title:
            self.time_period = 'EV'
            self.time_period_start = datetime.time(19, 00, 00)
            self.time_period_end = datetime.time(23, 59, 59)
            self.time_period_duration = 5.0
        elif 'ON' in self.Scenario.title:
            self.time_period = 'ON'
            self.time_period_start = datetime.time(0, 00, 00)
            self.time_period_end = datetime.time(5, 59, 59)
            self.time_period_duration = 6.0
        else:
            raise Exception("Scenario title: '%s' does not contain time period name." % self.Scenario.title)

    def _GetLogbookAttributes(self):
        attr = {
            "Scenario": self.Scenario.id,
            "Service Table file": self.ServiceTableFile,
            "Cost Parameters file": self.CostParamsFile,
            "Report file": self.ReportFile,
            "Version": self.version,
            "self": self.__MODELLER_NAMESPACE__
        }

        return attr

    def _GetAllLinesInfo(self):

        lines_r = []

        lineObjects = self.Scenario.get_network().transit_lines()
        linkLengths = _util.fastLoadLinkAttributes(self.Scenario, ['length'])

        for l in lineObjects:
            lineLength = 0.0
            lineTime = 0.0
            lineSegments = l.segments()
            for seg in lineSegments:
                if self.HasTransitResults:
                    lineTime += seg.transit_time
                lineLength += linkLengths[(int(seg.i_node.id), int(seg.j_node.id))]['length']
            lineStart = l.segment(0).i_node.id
            lineEnd = l.segment(-1).i_node.id
            line = [l.id, l['description'], l.mode.id, l.vehicle.id, str(lineLength), lineStart, lineEnd, str(lineTime)]
            lines_r.append(line)

        lines_r.sort(key=lambda x: x[0])

        return lines_r

    def _ReadInputCSV(self, file):
        r = []
        with open(file) as reader:
            for l in reader:
                r.append(l.strip().split(','))
        # self._WriteDebugFile(self.DebugFile, r[1:])
        return r[1:]

    def _WriteDebugFile(self, file, content):
        with open(file, 'w') as writer_debug:
            for row in content:
                writer_debug.write(','.join(row) + '\n')

    def _ValidateCostParamsFile(self):
        for l in self.params:
            if len(l) != 10:
                _m.logbook_write("ERROR: Incorrect formatting for Cost Parameters file.")
                raise Exception("Incorrect formatting for Cost Parameters file.")
            if l[4] == l[5] == '':
                _m.logbook_write("ERROR: Neither uc_veh_annual and uc_veh_daily are specified for at least one entry "
                                 "in Cost Parameter file.")
                raise Exception("Neither uc_veh_annual and uc_veh_daily are specified for at least one entry in Cost "
                                "Parameter file.")
            for i in range(0, len(l), 1):
                if l[i] == '' and i != 4 and i != 5:
                    _m.logbook_write("ERROR: One or more required values are empty in Cost Parameters file.")
                    raise Exception("One or more required values are empty in Cost Parameters file.")

    def _CalculatePrelimLineProperties(self, lines_og, servt):

        lines = []

        for line in lines_og:
            id = line[0]
            trips = [trip for trip in servt if trip[0] == id and self._CheckTripValidity(trip)]
            if len(trips) == 0:
                _m.logbook_write("WARNING: Cannot find any trips in this time period for line " + id)
            elif self.time_period == 'ON':
                morning = []
                night = []
                for t in trips:
                    if int(self._FormatTime(t[1])[0:2]) < 6:
                        morning.append(t)
                    elif int(self._FormatTime(t[1])[0:2]) > 23:
                        night.append(t)
                line_runtimes = []
                morning_hdwys = []
                night_hdwys = []
                if len(morning) >= 1:
                    for j in range(0, len(morning) - 1, 1):
                        morning_hdwys.append(self._GetTimeDiff(morning[j][1], morning[j + 1][1]))
                        line_runtimes.append(self._GetTimeDiff(morning[j][1], morning[j][2]))
                    line_runtimes.append(self._GetTimeDiff(morning[-1][1], morning[-1][2]))
                if len(night) >= 1:
                    for j in range(0, len(night) - 1, 1):
                        night_hdwys.append(self._GetTimeDiff(night[j][1], night[j + 1][1]))
                        line_runtimes.append(self._GetTimeDiff(night[j][1], night[j][2]))
                    line_runtimes.append(self._GetTimeDiff(night[-1][1], night[-1][2]))
                avg_runtime = sum(line_runtimes) / float(len(line_runtimes))
                if len(morning) > len(night):
                    if len(morning) == 1:
                        line_hdwy = 360.00
                    else:
                        line_hdwy = sum(morning_hdwys) / float(len(morning_hdwys))
                elif len(night) > len(morning):
                    if len(night) == 1:
                        line_hdwy = 360.00
                    else:
                        line_hdwy = sum(night_hdwys) / float(len(night_hdwys))
                else:
                    if len(night) == 1:  # if both night and morning each have one trip
                        line_hdwy = 180.00
                    else:
                        line_hdwy = (sum(morning_hdwys) + sum(night_hdwys)) / \
                                    float(len(morning_hdwys) + len(night_hdwys))
                line.append("{:.2f}".format(avg_runtime))
                line.append("{:.2f}".format(line_hdwy))
                line.append("{:d}".format(len(line_runtimes)))  # trip count
                lines.append(line)
            else:
                if len(trips) == 1:
                    line.append("{:.2f}".format(self._GetTimeDiff(trips[0][1], trips[0][2])))
                    # set headway to length of entire time period
                    line.append("{:.2f}".format(60.00 * self.time_period_duration))
                    line.append('1')
                    lines.append(line)
                else:
                    line_hdwys = []
                    line_runtimes = []
                    for j in range(0, len(trips) - 1, 1):
                        line_hdwys.append(self._GetTimeDiff(trips[j][1], trips[j + 1][1]))
                        line_runtimes.append(self._GetTimeDiff(trips[j][1], trips[j][2]))
                    # calculate runtime of the last trip
                    line_runtimes.append(self._GetTimeDiff(trips[-1][1], trips[-1][2]))
                    line_hdwy = sum(line_hdwys) / float(len(line_hdwys))
                    avg_runtime = sum(line_runtimes) / float(len(line_runtimes))
                    line.append("{:.2f}".format(avg_runtime))
                    line.append("{:.2f}".format(line_hdwy))
                    line.append("{:d}".format(len(line_runtimes)))
                    lines.append(line)

        # self._WriteDebugFile(self.DebugFile, lines)

        return lines

    def _GroupLinesIntoRoutes(self, lines):
        routes_r = []
        cur_route_id = self._GetRouteID(lines[0])
        cur_route = []

        for line in lines:
            if self._GetRouteID(line) == cur_route_id:
                cur_route.append(line)
            else:
                routes_r.append(cur_route)
                cur_route = []
                cur_route_id = self._GetRouteID(line)
                cur_route.append(line)

        routes_r.append(cur_route)  # add last route

        return routes_r

    def _CleanDuplicateLines(self, routes):
        duplicate = []

        for route in routes:
            seen = []
            for line in route:
                if seen == []:  # if first line in route
                    seen.append(line)
                else:
                    for seen_line in seen:
                        if seen_line[self.idx_len] == line[self.idx_len] and \
                                seen_line[self.idx_time_sch] == line[self.idx_time_sch] and \
                                seen_line[0][-1] == line[0][-1]:
                            # if direction, length, and runtime are exactly the same, flag as duplicate
                            if float(seen_line[self.idx_tc]) < float(line[self.idx_tc]):
                                # delete the line with less trips
                                duplicate.append(seen_line)
                            else:
                                duplicate.append(line)
                    seen.append(line)

        new_routes = []

        for route in routes:
            new_routes.append([line for line in route if line not in duplicate])

        return new_routes

    def _BalanceDirections(self, routes):
        balanced_routes = []
        no_pair = []
        balance_err_route_ids = []  # FOR DEBUGGING USE

        for route in routes:
            if route[0][0][0] == 'G':  # special case for all GO Transit routes
                no_pair.append(self._GetRouteID(route[0]))
                balanced_routes.append(route)
            elif len(route) > 2 and route[0][0][0:3] == 'T14':  # special case for TTC 14X routes with more than 2 lines
                no_pair.append(self._GetRouteID(route[0]))
                balanced_routes.append(self._TTCExpress(route))
            elif self._GetLineDir(route[0]) == 'x':  # special case for routes with no direction ID
                no_pair.append(self._GetRouteID(route[0]))
                balanced_routes.append(self._NoDirRoute(route))
            elif len([line for line in route if self._GetLineDir(line) in ['c', 'x']]) == len(route):
                # special case if all lines are 'c' or no dir ('x')
                no_pair.append(self._GetRouteID(route[0]))
                balanced_routes.append(route)
            else:
                lines_to_balance = [line for line in route if self._GetLineDir(line) in ['a', 'b']]
                lines_other = [line for line in route if line not in lines_to_balance]
                if len(lines_to_balance) == 1:
                    no_pair.append(self._GetRouteID(route[0]))
                    balanced_routes.append(route)
                elif len(lines_to_balance) == 2:
                    balanced_routes.append(route)
                else:
                    [skew, skew_mag] = self._CheckDirSkew(lines_to_balance)
                    if skew != 'e':  # if directions are skewed, balance
                        [balanced, err] = self._Balance(lines_to_balance, skew, skew_mag)
                        if err is False:
                            balanced_routes.append(balanced + lines_other)
                        else:
                            balanced_routes.append(route)
                            no_pair.append(self._GetRouteID(route[0]))
                            balance_err_route_ids.append(self._GetRouteID(route[0]))
                    else:  # otherwise, directions are equal, no need to balance
                        balanced_routes.append(route)
                del lines_to_balance
                del lines_other

        return balanced_routes, no_pair

    def _GenerateDirectionPairs(self, routes, no_pair):
        routes_dir_pairs = []
        dir_mismatch_route_ids = []

        for route in routes:
            # print(self._GetRouteID(route[0]))
            if self._GetRouteID(route[0]) in no_pair:
                routes_dir_pairs.append([])
            else:
                lines_to_pair = [line for line in route if self._GetLineDir(line) in ['a', 'b']]
                dir_pairs = self._GetDirPairs(lines_to_pair)
                if dir_pairs == []:
                    dir_mismatch_route_ids.append(self._GetRouteID(route[0]))
                    routes_dir_pairs.append([])
                else:
                    routes_dir_pairs.append(dir_pairs)

        return routes_dir_pairs

    def _ComputeVehicleCount(self, routes, routes_dir_pairs):
        route_ids_r = []
        veh_no_r = []
        mode_r = []

        routes_iter = iter(routes)

        for route_dir_pairs in routes_dir_pairs:
            route = next(routes_iter)
            route_id = self._GetRouteID(route[0])
            route_ids_r.append(route_id)
            mode_r.append(route[0][self.idx_mode])
            if route_dir_pairs == []:  # if no pair
                veh_accum = 0
                if len(route) == 1 and route[0][self.idx_startpt] != route[0][self.idx_endpt] and 'HM' not in route_id:
                    # if route is only one direction (and not a loop line)
                    veh_accum = self._OneWayLine(route[0])
                else:
                    for line in route:
                        veh_computed = math.ceil(
                            (float(line[self.idx_time_sch]) + self._GetLayDur(line)) / float(line[self.idx_hdwy_new]))
                        veh_accum += min(veh_computed, float(line[self.idx_tc]))
            else:  # if there are pairings
                veh_accum = 0
                veh_accum_notccond = 0
                for pair in route_dir_pairs:
                    line1 = next(line for line in route if line[0] == pair[0])
                    line2 = next(line for line in route if line[0] == pair[1])
                    line1bad = (float(line1[self.idx_len]) <= self.short_len_th or
                                float(line1[self.idx_tc]) <= self.low_freq_th)
                    line2bad = (float(line2[self.idx_len]) <= self.short_len_th or
                                float(line2[self.idx_tc]) <= self.low_freq_th)
                    if (not line1bad) and (line2bad):
                        veh_count = self._OneWayLine(line1)
                        veh_accum += veh_count
                    elif (line1bad) and (not line2bad):
                        veh_count = self._OneWayLine(line2)
                        veh_accum += veh_count
                    else:
                        cycle_time = (float(line1[self.idx_time_sch]) +
                                      float(line2[self.idx_time_sch])) * self._GetLayFac(line1)
                        avg_hdwy = (float(line1[self.idx_hdwy_new]) + float(line2[self.idx_hdwy_new])) / 2.0
                        veh_count = math.ceil(cycle_time / avg_hdwy)
                        if float(line1[self.idx_tc]) > self.tccond_th and float(line2[self.idx_tc]) > self.tccond_th:
                            veh_accum += veh_count
                        else:  # make sure the vehicle count for the branch does not exceed the trip count
                            veh_accum += min(float(line1[self.idx_tc]), float(line2[self.idx_tc]), veh_count)
                    veh_accum_notccond += veh_count
                if veh_accum == 0:
                    veh_accum = veh_accum_notccond
                # now add the vehicles from the 'c' routes
                lines_other = [line for line in route if self._GetLineDir(line) not in ['a', 'b']]
                for line in lines_other:
                    veh_computed = math.ceil((float(line[self.idx_time_sch]) + self._GetLayDur(line))
                                             / float(line[self.idx_hdwy_new]))
                    veh_accum += min(veh_computed, float(line[self.idx_tc]))
            veh_no_r.append(str(int(veh_accum)))

        return route_ids_r, veh_no_r, mode_r

    def _ComputeCost(self, routes_unbalanced, veh_no):
        revhr_r = []
        revkm_r = []
        cost_r = []

        veh_no_iter = iter(veh_no)

        for route in routes_unbalanced:
            route_id = self._GetRouteID(route[0])
            revhr = 0.0
            revkm = 0.0
            for line in route:
                if self.time_period == 'ON':
                    revhr += float(line[self.idx_time_sch]) * float(line[self.idx_tc]) / 60.00
                else:
                    runtime = max(float(line[self.idx_time_sch]), float(line[self.idx_time_act]))
                    revhr += runtime * float(line[self.idx_tc]) / 60.00
                revkm += float(line[self.idx_len]) * float(line[self.idx_tc])
            if 'TS' in route_id:  # address how the op stats for the TTC rail routes are on a per-car basis
                if route_id == 'TS03' or route_id == 'TS04':  # Line 3, 4 are 4 cars per set
                    revhr = revhr * 4.00
                    revkm = revkm * 4.00
                else:  # Lines 1, 2 are 6 cars per set
                    revhr = revhr * 6.00
                    revkm = revkm * 6.00
            [uc_hr, uc_km, uc_veh] = self._GetCostParams(route_id, route[0])
            cost = uc_hr * revhr + uc_km * revkm + uc_veh * int(next(veh_no_iter))
            revhr_r.append("{:.4f}".format(revhr))
            revkm_r.append("{:.4f}".format(revkm))
            cost_r.append("$" + "{:.2f}".format(cost))

        return revhr_r, revkm_r, cost_r

    def _ExportResults(self, file, route_ids, mode, revhr, revkm, veh_no, cost):
        mode_iter = iter(mode)
        revhr_iter = iter(revhr)
        revkm_iter = iter(revkm)
        veh_no_iter = iter(veh_no)
        cost_iter = iter(cost)

        with open(file, 'w') as writer:
            writer.write(','.join(['route_id', 'mode', 'rev_hr', 'rev_km', 'no_veh', 'op_cost']) + '\n')
            for route_id in route_ids:
                w = [route_id, next(mode_iter), next(revhr_iter), next(revkm_iter), next(veh_no_iter), next(cost_iter)]
                writer.write(','.join(w) + '\n')


    # ---------- Sub Functions: Prelim Calculations ----------

    def _FormatTime(self, t):
        # ensures all hour values are zero-padded, given a time input string
        if len(t) < 7 or len(t) > 8:
            raise Exception("Service Table time '%s' not formatted according to HH:MM:SS!" % t)
        elif len(t) == 7:
            return '0' + t
        elif t[0] == ' ':
            return '0' + t[1:]
        else:
            return t

    def _GetTimeDiff(self, time1, time2):
        # computes time gap between two times, returns it in minutes (type float)
        # time1 is earlier time, time2 is later time
        start_str = self._FormatTime(time1)
        end_str = self._FormatTime(time2)
        if int(start_str[0:2]) > 23 or int(end_str[0:2]) > 23:
            start_str = str(int(start_str[0:2]) - 12) + start_str[2:]
            end_str = str(int(end_str[0:2]) - 12) + end_str[2:]
        t1 = datetime.datetime.strptime(start_str, '%H:%M:%S')
        t2 = datetime.datetime.strptime(end_str, '%H:%M:%S')
        diff = t2 - t1
        return diff.seconds / 60.00

    def _CheckTripValidity(self, trip):
        # checks if the trip start time is within the time period
        if len(trip) != 3:
            raise Exception("Not all rows of Service Table have three columns.")
        start_str = self._FormatTime(trip[1])
        if int(start_str[0:2]) > 23:
            start_str = str(int(start_str[0:2]) - 24) + start_str[2:]
        start = datetime.datetime.strptime(start_str, '%H:%M:%S').time()
        if self.time_period_start <= start <= self.time_period_end:
            return True
        else:
            return False


    # ---------- Sub Functions: Obtaining Values and Parameters ----------

    def _GetRouteID(self, line):
        if line[0][-1] in ['a', 'b', 'n', 's', 'e', 'w', 'c']:  # if last char is a direction ID
            if line[0][-2].isnumeric():  # if second last char is a number
                return line[0][:-1]
            else:  # if second last char is a letter
                return line[0][:-2]
        elif line[0][-1].isnumeric():  # if last char is a number
            return line[0]
        else:  # otherwise, i.e. if last char is uppercase letter
            return line[0][:-1]

    def _GetLineDir(self, line):
        if line[0][-1] in ['a', 'n', 'e']:
            return 'a'
        elif line[0][-1] in ['b', 's', 'w']:
            return 'b'
        elif line[0][-1] == 'c':
            return 'c'
        else:
            return 'x'

    def _GetLayFac(self, line):
        # returns the appropriate layover factor based on agency
        if line[0][0] == 'T':
            return 1.00
        else:
            return 1.15

    def _GetLayDur(self, line):
        # returns the appropriate layover duration based on agency and time period
        if line[0][0:2] == 'GB' and (self.time_period in ['AM', 'PM', 'EV']):
            return 35.00
        elif line[0][0:2] == 'HM':
            return 0.00
        else:
            return 5.00

    def _GetCostParams(self, route_id, line):
        # given a route ID and a representative line of the route, get the cost parameters as per input
        # order of columns: agency_prefix, mode, uc_revhr, uc_revkm, uc_veh_annual, uc_veh_daily, weekday_ratio_revhr,
        #                   weekday_ratio_revkm, adj_revhr, adj_revkm
        # return: [uc_hr, uc_km, uc_veh (adjusted for time period)]
        try:
            # find the matching row in params table,
            # where its agency prefix and mode are equal to those of the given route
            match = next(p for p in self.params if p[0] == route_id[0:len(p[0])] and p[1] == line[self.idx_mode])
        except StopIteration:
            _m.logbook_write("WARNING: Cannot find cost parameter specification that covers route '%s'. "
                             "Will proceed to be processed as zero cost." % route_id)
            return [0.00, 0.00, 0.00]
        if match[5] != '':
            # if daily uc available, use daily_uc / 24 * time_period_duration as uc_veh
            return [float(match[2]) * float(match[8]), float(match[3]) * float(match[9]),
                    float(match[5]) / 24.0 * self.time_period_duration]
        else:
            # if only annual uc available, use annual_uc / weekday_ratio average / 24 * time_period_duration as uc_veh
            return [float(match[2]) * float(match[8]), float(match[3]) * float(match[9]),
                    float(match[4]) / ((float(match[6]) + float(match[7])) / 2.0) / 24.0 * self.time_period_duration]


    # ---------- Sub Functions: Balancing / Pairing ----------

    def _CheckDirSkew(self, route):
        # given a route, check whether the number of lines in each direction is equal,
        # return the skewed direction if not
        counta = 0
        countb = 0
        for rline in route:
            if self._GetLineDir(rline) == 'a':
                counta += 1
            else:
                countb += 1
        if counta == countb:
            return ['e', 0]
        elif counta > countb:
            return ['a', counta - countb]
        else:
            return ['b', countb - counta]

    def _Balance(self, route, dir, mag):

        if len(route) == mag:
            return [route, True]

        # extract lines in the skewed direction
        lines_in_dir = []
        for rline in route:
            if self._GetLineDir(rline) == dir:
                lines_in_dir.append(rline)

        sort_len = sorted(lines_in_dir, key=lambda x: (float(x[self.idx_len]), float(x[self.idx_tc])))
        sort_tc = sorted(lines_in_dir, key=lambda x: (float(x[self.idx_tc]), float(x[self.idx_len])))
        sort_rt = sorted(lines_in_dir, key=lambda x: float(x[self.idx_time_sch]))

        remove = []
        error = False

        if len(route) == 3:
            if float(sort_len[0][self.idx_len]) <= self.short_len_th:
                remove.append(sort_len[0])
            elif float(sort_tc[0][self.idx_tc]) <= self.low_freq_th:
                remove.append(sort_tc[0])
            elif sort_len[0] == sort_tc[0]:
                remove.append(sort_len[0])
            else:  # check which pairing has a better geo match, and remove the line that is not in that pairing
                if dir == 'a':
                    line_other = next(line for line in route if self._GetLineDir(line) == 'b')
                else:
                    line_other = next(line for line in route if self._GetLineDir(line) == 'a')
                pairings = []
                for line in lines_in_dir:
                    pairings.append([[line[0], line_other[0]]])
                pairings[0].append(self._EvalGeo(route, pairings[0]))
                pairings[1].append(self._EvalGeo(route, pairings[1]))
                if pairings[0][-1] < pairings[1][-1]:
                    remove.append(next(line for line in route if line[0] not in pairings[0][0]))
                elif pairings[1][-1] < pairings[0][-1]:
                    remove.append(next(line for line in route if line[0] not in pairings[1][0]))
        else:
            for i in range(0, mag, 1):
                to_be_removed = []
                if float(sort_len[0][self.idx_len]) <= self.short_len_th:
                    to_be_removed = sort_len[0]
                elif float(sort_tc[0][self.idx_tc]) <= self.low_freq_th:
                    to_be_removed = sort_tc[0]
                elif sort_len[0] == sort_tc[0]:
                    to_be_removed = sort_len[0]
                else:
                    if mag - i == 1:
                        hypo_del_len = [line for line in route if line != sort_len[0] and line not in remove]
                        del_len_pairing = self._GetDirPairs(hypo_del_len)
                        del_len_geoscore = self._EvalGeo(hypo_del_len, del_len_pairing)
                        del_len_simscore = self._EvalSim(hypo_del_len, del_len_pairing)
                        hypo_del_tc = [line for line in route if line != sort_tc[0] and line not in remove]
                        del_tc_pairing = self._GetDirPairs(hypo_del_tc)
                        del_tc_geoscore = self._EvalGeo(hypo_del_tc, del_tc_pairing)
                        del_tc_simscore = self._EvalSim(hypo_del_tc, del_tc_pairing)

                        # calculate nominal final line count
                        bad_count = 0
                        for rline in route:
                            if float(rline[self.idx_len]) <= self.short_len_th or \
                                    float(rline[self.idx_tc]) <= self.low_freq_th:
                                bad_count += 1
                        if bad_count % 2 == 0:
                            final_line_count = len(route) - mag - bad_count
                        else:
                            final_line_count = len(route) - mag - bad_count - 1

                        if (len(del_len_pairing) * 2 == final_line_count) and (
                                len(del_tc_pairing) * 2 != final_line_count):
                            to_be_removed = sort_len[0]
                        elif (len(del_tc_pairing) * 2 == final_line_count) and (
                                len(del_len_pairing) * 2 != final_line_count):
                            to_be_removed = sort_tc[0]
                        else:
                            if del_len_geoscore < del_tc_geoscore:
                                to_be_removed = sort_len[0]
                            elif del_tc_geoscore < del_len_geoscore:
                                to_be_removed = sort_tc[0]
                            elif del_len_simscore < del_tc_simscore:
                                to_be_removed = sort_len[0]
                            elif del_tc_simscore < del_len_simscore:
                                to_be_removed = sort_tc[0]
                            else:
                                to_be_removed = sort_rt[0]
                    else:
                        to_be_removed = sort_rt[0]
                remove.append(to_be_removed)
                sort_len = [rline for rline in sort_len if rline is not to_be_removed]
                sort_tc = [rline for rline in sort_tc if rline is not to_be_removed]
                sort_rt = [rline for rline in sort_rt if rline is not to_be_removed]

        if remove == []:
            error = True

        r = [rline for rline in route if rline not in remove]

        return [r, error]

    def _CheckPairValidity(self, route, pair):
        # given a pair of lines in a route, check whether at least one of them are short / infrequent, and if so, flag
        # so that the pair is not added
        good_pair = True
        modes = []
        hdwys = []
        for pair_line_id in pair:
            line_match = next(line for line in route if line[0] == pair_line_id)
            modes.append(line_match[self.idx_mode])
            hdwys.append(float(line_match[self.idx_hdwy_new]))
            if float(line_match[self.idx_len]) <= self.short_len_th or \
                    float(line_match[self.idx_tc]) <= self.low_freq_th:
                good_pair = False
        # also check if modes are being mixed (could happen with streetcars), and if so, pair is not valid
        if modes[0] != modes[1]:
            good_pair = False
        # check if the lines have drastically different headways, and if so, pair is not valid
        if abs(hdwys[0] - hdwys[1]) > self.hdwy_diff_th:
            good_pair = False
        return good_pair

    def _CompareGeo(self, route, pairing1, pairing2):
        # takes two different pairing sets of the same route and
        # decide which one is better based on geographic start/end pts
        # return format: ['status', pairing_to_use]
        p1_mismatch_count = self._EvalGeo(route, pairing1)
        p2_mismatch_count = self._EvalGeo(route, pairing2)

        if p1_mismatch_count == p2_mismatch_count:
            return ['equal_mismatch', pairing1]
        elif p1_mismatch_count == 0:
            return ['fixed', pairing1]
        elif p2_mismatch_count == 0:
            return ['fixed', pairing2]
        elif p1_mismatch_count < p2_mismatch_count:
            return ['nonzero_mismatch', pairing1]
        else:
            return ['nonzero_mismatch', pairing2]

    def _EvalGeo(self, route, pairing_combo):
        mismatch_count = 0
        for p in pairing_combo:
            l1 = next(line for line in route if line[0] == p[0])
            l2 = next(line for line in route if line[0] == p[1])
            if not (l1[self.idx_startpt] == l2[self.idx_endpt] and l1[self.idx_endpt] == l2[self.idx_startpt]):
                mismatch_count += 1
        return mismatch_count

    def _RecursivePair(self, dir_a, dir_b):
        # takes two lists containing lines in each direction (lengths of both lists must be equal)
        # picks the smallest line from each direction, both in terms of length, and trip count; pair those lines up
        # passes the remaining lines into the recursive call
        # base case: pairs the only line in each direction and return it
        # format of the data structure: list of tuples; each tuple is a node-stems pair: (node, stems)
        # node is a list indicating the pair ['line1', 'line2']
        # stems is a list of tuples

        if len(dir_a) == 1 and len(dir_b) == 1:
            return [(sorted([dir_a[0][0], dir_b[0][0]]), [])]
        else:
            # len:
            line_a_len = min(dir_a, key=lambda x: (float(x[self.idx_len]), float(x[self.idx_tc])))
            line_b_len = min(dir_b, key=lambda x: (float(x[self.idx_len]), float(x[self.idx_tc])))
            pair_len = sorted([line_a_len[0], line_b_len[0]])
            # tc:
            line_a_tc = min(dir_a, key=lambda x: (float(x[self.idx_tc]), float(x[self.idx_len])))
            line_b_tc = min(dir_b, key=lambda x: (float(x[self.idx_tc]), float(x[self.idx_len])))
            pair_tc = sorted([line_a_tc[0], line_b_tc[0]])
            if pair_len == pair_tc:
                new_dir_a = [line for line in dir_a if line != line_a_len]
                new_dir_b = [line for line in dir_b if line != line_b_len]
                r = [(pair_len, self._RecursivePair(new_dir_a, new_dir_b))]
                return r
            else:
                new_dir_a_len = [line for line in dir_a if line != line_a_len]
                new_dir_b_len = [line for line in dir_b if line != line_b_len]
                new_dir_a_tc = [line for line in dir_a if line != line_a_tc]
                new_dir_b_tc = [line for line in dir_b if line != line_b_tc]

                return [(pair_len, self._RecursivePair(new_dir_a_len, new_dir_b_len)),
                        (pair_tc, self._RecursivePair(new_dir_a_tc, new_dir_b_tc))]

    def _ParseRecPair(self, recpair, rl):
        # parses the result of running the recursive pair function into a list of different pairing combinations
        if len(recpair) == 1 and recpair[0][1] == []:
            # base case: if the list only has one tuple and the tuple has no further stems, return the tuple's node
            return [rl + [recpair[0][0]]]
        else:
            r = []
            for tup in recpair:  # for each tuple in the list
                r += self._ParseRecPair(tup[1], rl + [tup[0]])
            return r

    def _GetDirPairs(self, route):

        if len(route) == 2:
            return [sorted([route[0][0], route[1][0]])]

        # calculate the number of bad lines for pair combo filtering
        bad_count = 0
        for rline in route:
            if float(rline[self.idx_len]) <= self.short_len_th or float(rline[self.idx_tc]) <= self.low_freq_th:
                bad_count += 1
        if bad_count % 2 == 0:
            final_line_count = len(route) - bad_count
        else:
            final_line_count = len(route) - bad_count - 1
        # print(final_line_count)

        # Group the lines of the route into the two directions
        lines_a = []
        lines_b = []
        for rline in route:
            if self._GetLineDir(rline) == 'a':
                lines_a.append(rline)
            else:
                lines_b.append(rline)

        if len(lines_a) != len(lines_b):
            return []

        pair_combos = self._ParseRecPair(self._RecursivePair(lines_a, lines_b), [])

        # filter pairing combos: remove the invalid pairs from each combo
        pair_combos_fltr = []
        for combo in pair_combos:
            combo_fltr = []
            for pair in combo:
                if self._CheckPairValidity(route, pair):
                    combo_fltr.append(pair)
            pair_combos_fltr.append(combo_fltr)

        # filter pairing combos: remove blank ones and duplicates
        pair_combos_fltr_unique = []
        for combo in pair_combos_fltr:
            if not combo == []:
                combo = sorted(combo, key=lambda x: x[0])
                if combo not in pair_combos_fltr_unique:
                    pair_combos_fltr_unique.append(combo)

        pair_combos_fltr = list(pair_combos_fltr_unique)
        del pair_combos_fltr_unique

        if pair_combos_fltr == []:
            pair_combos_fltr = list(self._NoValidCombo(route, pair_combos))

        # filter pairing combos: if the resulting combos have unequal lengths ...
        # ... remove the ones whose lengths are not half of the final length count
        first_combo_length = len(pair_combos_fltr[0])
        equal_combo_lengths = True
        for combo in pair_combos_fltr:
            if len(combo) != first_combo_length:
                equal_combo_lengths = False
        if not equal_combo_lengths:
            # filter out the combos that don't match the length count constraint
            pair_combos_fltr_lc = [combo for combo in pair_combos_fltr if len(combo) * 2 == final_line_count]
            # but if none of the combos meet the length count constraint, we revert to original
            if not pair_combos_fltr_lc == []:
                pair_combos_fltr = list(pair_combos_fltr_lc)
            del pair_combos_fltr_lc

        pair_combos_geo = []
        for combo in pair_combos_fltr:
            pair_combos_geo.append(combo + [self._EvalGeo(route, combo)])

        min_geo_score = min(pair_combos_geo, key=lambda x: x[-1])[-1]
        # print(min_geo_score)
        min_geo_combos = [combo[:-1] for combo in pair_combos_geo if combo[-1] == min_geo_score]
        # print(min_geo_combos)

        if len(min_geo_combos) == 1:
            return min_geo_combos[0]
        else:
            pair_combos_sim = []
            for combo in pair_combos_fltr:
                pair_combos_sim.append(combo + [self._EvalSim(route, combo)])
            min_sim_score = min(pair_combos_sim, key=lambda x: x[-1])[-1]
            # print(min_sim_score)
            min_sim_combos = [combo[:-1] for combo in pair_combos_sim if combo[-1] == min_sim_score]
            # print(min_sim_combos)
            if len(min_sim_combos) == 1:
                return min_sim_combos[0]
            else:
                return min_sim_combos[0]

    def _EvalSim(self, route, pairing_combo):
        # takes a combo of pairs and looks at how closely the lines in each pair match, in terms of hdwy, len, tc
        mismatch_count = 0
        for p in pairing_combo:
            l1 = next(line for line in route if line[0] == p[0])
            l2 = next(line for line in route if line[0] == p[1])
            if abs(float(l1[self.idx_hdwy_new]) - float(l2[self.idx_hdwy_new])) > self.hdwy_diff_th:
                mismatch_count += 1
            elif abs(float(l1[self.idx_len]) - float(l2[self.idx_len])) > self.len_diff_th:
                mismatch_count += 1
            elif min(float(l1[self.idx_tc]), float(l2[self.idx_tc])) / \
                    max(float(l1[self.idx_tc]), float(l2[self.idx_tc])) < self.tc_diff_div_th:
                mismatch_count += 1
        return mismatch_count

    def _TTCExpress(self, route):
        # special case for TTC 14X downtown express routes that have more than 2 lines
        r = []
        for line in route:
            if float(line[self.idx_len]) > self.short_len_th:
                r.append(line)
        return r

    def _NoValidCombo(self, route, pair_combos_og):
        cur_best_pair = []
        cur_best_pair_tc = 0
        for combo in pair_combos_og:
            for pair in combo:
                l1 = next(line for line in route if line[0] == pair[0])
                l2 = next(line for line in route if line[0] == pair[1])
                if (float(l1[self.idx_tc]) + float(l2[self.idx_tc])) > cur_best_pair_tc:
                    cur_best_pair = pair
        return [[cur_best_pair]]

    def _OneWayLine(self, line):
        if line[self.idx_startpt] == line[self.idx_endpt]:
            return math.ceil(float(line[self.idx_time_sch]) / float(line[self.idx_hdwy_new]))
        tc = int(float(line[self.idx_tc]))  # get the trip count
        if float(line[self.idx_len]) > 10.00:
            # if this is a long route, vehicles won't deadhead back
            return tc
        else:
            # get the veh count by looking at cycle time (duration in one dir * 2)
            cycle_veh = math.ceil(float(line[self.idx_time_sch]) * 2.0 / float(line[self.idx_hdwy_new]))
            return min(tc, cycle_veh)

    def _NoDirRoute(self, route):
        if len(route) == 1:
            return route
        r = []
        for line in route:
            if float(line[self.idx_len]) > self.short_len_th and float(line[self.idx_tc]) > self.low_freq_th:
                r.append(line)
        if len(r) == 0:
            return route
        return r

