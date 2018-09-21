import inro.modeller as _m
import inro.emme.desktop.app as _app
import traceback as _traceback
import csv

_MODELLER = _m.Modeller()
_emmebank = _MODELLER.emmebank
_tmgTPB = _MODELLER.module('tmg.common.TMG_tool_page_builder')
_util = _MODELLER.module('tmg.common.utilities')
network_results = _MODELLER.tool("inro.emme.transit_assignment.extended.network_results")

class Generate_Transit_Times(_m.Tool()):
    version = "0.0.6"
    tool_run_msg = ""
    number_of_tasks = 1

    #---PARAMETERS---
    #auto_scenario = _m.Attribute(_m.InstanceType)
    #transit_scenario = _m.Attribute(_m.InstanceType)
    scenario = _m.Attribute(_m.InstanceType)

    boarding_duration = _m.Attribute(float)
    alighting_duration = _m.Attribute(float) 
    default_duration = _m.Attribute(float)
    correlation = _m.Attribute(float)

    time_period_duration  = _m.Attribute(int)


    #---XTMF PARAMETERS---
    scenario_number = _m.Attribute(int)
    #transit_scenario_number = _m.Attribute(int)

    def __init__(self):
        pass
        #---SET THE DEFAULTS OF PARAMETERS---

    def page(self):
        pb = _tmgTPB.TmgToolPageBuilder(self, title="Generate Dwell Time II v%s" %self.version,
                     description="Generates dwell time for each transit segment. The dwell time is modelled as a function using the number of\
                     boarding and alighting passengers, which are obtained from EMME assignment. The results of EMME assignment,\
                     \"total boardings\" and \"total alightings\", will be stored in extra attributes\
                     \"@boardings\" and \"@alightings\", respectively. This dwell time model also accounts for the loss of time\
                     due to deceleration to and acceleration from each bus stop.\
                     Note that the bus stops that are eliminated as a result of Full Network Set Generator are taken care of in this tool.<br><br>\
                     The numbers of bus stops each transit segment accounts for will be stored in extra attributes \"@stops\", and\
                     the dwell time generated will be stored in attributes \"dwell_time\".",
                     branding_text="- TMG Toolbox")

        pb.add_header("INPUTS")

        pb.add_select_scenario(tool_attribute_name='scenario_number',
                               title='Scenario Number',
                               allow_none=False)

        pb.add_text_box(tool_attribute_name='time_period_duration',
                        title='Representative Hour Factor')

        pb.add_header("PARAMETERS") 

        pb.add_text_box(tool_attribute_name='boarding_duration',
                        title='Boarding Duration per Passenger (s)')

        pb.add_text_box(tool_attribute_name='alighting_duration',
                        title='Alighting Duration per Passenger (s)')

        pb.add_text_box(tool_attribute_name='default_duration',
                        title='Default Duration per Stop (s)')

        pb.add_text_box(tool_attribute_name='correlation',
                        title='Correlation factor between auto and Transit times (>1 means transit times are greater than auto')

        return pb.render()

    #---EMME---
    def run(self):
        self.tool_run_msg = ""
        self.TRACKER.reset()
        try:
            self._Execute()

        except Exception, e:
            self.tool_run_msg = _m.PageBuilder.format_exception(
                e, _traceback.format_exc(e))
            raise

        self.tool_run_msg = _m.PageBuilder.format_info("Tool complete.")

    #---XTMF---
    def __call__(self, scenario_number, time_period_duration, boarding_duration, alighting_duration, default_duration, correlation):

        self.scenario = _emmebank.scenario(int(scenario_number))
        
        self.time_period_duration = int(time_period_duration)
        
        self.boarding_duration = float(boarding_duration)
        self.alighting_duration = float(alighting_duration)
        self.default_duration = float(default_duration)

        self.correlation = float(correlation)

        try:
            self._Execute()
        except Exception, e:
            msg = str(e) + "\n" + _traceback.format_exc(e)
            raise Exception(msg)

    ##########################################################################################
    #---MAIN EXECUTION CODE---
    def _Execute(self):

        print "Running Generate Dwell Time"
        if self.scenario.has_transit_results == True:
            print "Updating Dwell Times"
            self._Update_Dwell_Times()
        elif self.scenario.has_traffic_results == True:
            print "Generating Base Speed"
            self._Generate_Base_Speeds()
        else:
            raise Exception("You need to have a valid auto assignment on scenario %d" %int(self.scenario.number))

        print "Generate Dwell Time Complete"

    ##########################################################################################
    #---MAIN FUNCTIONS---#
    def _Update_Dwell_Times(self):
        if self.scenario.extra_attribute("@boardings") == None:
            self.scenario.create_extra_attribute("TRANSIT_SEGMENT", "@boardings")
        if self.scenario.extra_attribute("@alightings") == None:
            self.scenario.create_extra_attribute("TRANSIT_SEGMENT", "@alightings")
        if self.scenario.extra_attribute("@boardings_") == None:
            self.scenario.create_extra_attribute("TRANSIT_SEGMENT", "@boardings_")
        if self.scenario.extra_attribute("@alightings_") == None:
            self.scenario.create_extra_attribute("TRANSIT_SEGMENT", "@alightings_")
        self.scenario.extra_attribute("@boardings").initialize(value = 0)
        self.scenario.extra_attribute("@alightings").initialize(value = 0)
        self.scenario.extra_attribute("@boardings_").initialize(value = 0)
        self.scenario.extra_attribute("@alightings_").initialize(value = 0)
        for name in _util.DetermineAnalyzedTransitDemandId(_util._getVersionOld(tuple), self.scenario):
            spec = {
                "on_links": None,
                "on_segments": {
                    "total_boardings": "@boardings_",
                    "total_alightings": "@alightings_"
                        },
                "aggregated_from_segments": None,
                "analyzed_demand": None,
                "constraint": None,
                "type": "EXTENDED_TRANSIT_NETWORK_RESULTS"
                }
            report = network_results(spec, scenario = self.scenario, class_name = name)
            network = self.scenario.get_network()
            for segment in network.transit_segments():
                segment["@boardings"] += float(segment["@boardings_"])
                segment["@alightings"] += float(segment["@alightings_"])
            self.scenario.publish_network(network)
        self.scenario.delete_extra_attribute("@boardings_")
        self.scenario.delete_extra_attribute("@alightings_")
        
        network = self.scenario.get_network()
        for segment in network.transit_segments():
            type = str(segment.line.id)[0:2]
            if type == "TS" or type == "T5" or type == "GT":
                continue
            headway = segment.line.headway
            number_of_trips = self.time_period_duration*60/headway
            boarding = segment["@boardings"]/number_of_trips
            alighting = segment["@alightings"]/number_of_trips

            if segment.j_node == None: 
                continue

            link_speed = segment.data1

            old_dwell = segment.dwell_time

            segment_dwell_time =(self.boarding_duration*boarding + self.alighting_duration*alighting) + \
                                 (int(segment["@tstop"])*self.default_duration) #seconds
            segment_dwell_time /= 60 #minutes
            
            segment.dwell_time = (segment_dwell_time+old_dwell)/2

        self.scenario.publish_network(network)


    def _Generate_Base_Speeds(self):
        network = self.scenario.get_network()
        for segment in network.transit_segments():
            is_surface_transit = False
            surface_transit = ["b","p","g","q"]
            if str(segment.line.mode.id) in surface_transit:
                is_surface_transit = True
            if not is_surface_transit:
                continue
            if segment.j_node == None:
                continue
            if segment.transit_time_func <= 10:
                segment.transit_time_func += 10
            if segment.link["auto_time"] < 0:
                total_segments = 0
                for seg in segment.line.segments():
                    total_segments += 1
                if int(segment.number) < 3 or int(segment.number) > total_segments-2:
                    time = float(segment.link.shape_length)/20.0*60
                else:
                    time = float(segment.link.shape_length)/50.0*60
            else:
                time = float(segment.link.auto_time)*self.correlation
            
            if time <= 0:
                print segment.id
            segment.data1 = time
               
        self.scenario.publish_network(network)

    ##########################################################################################
    #---SUB FUNCTIONS---
    def additional_time_loss(self, segment_speed): #Segment speed is in km/hr.
        #acceleration + deceleration
        segment_speed /= 3.6 #m/s
        if segment_speed < 15:
            T1 = (segment_speed/self.deceleration) + (segment_speed/self.acceleration) #deceleration, acceleration
            distance = 0.5*self.deceleration*(segment_speed/self.deceleration)**2 + 0.5*self.acceleration*(segment_speed/self.acceleration)**2
            T2 = distance/segment_speed
            time_loss = T1 - T2
        elif segment_speed < 45:
            T1 = (segment_speed/self.deceleration) + (15/self.acceleration) + ((segment_speed - 15)/self.acceleration) #deceleration, acceleration
            distance = 0.5*self.deceleration*(segment_speed/self.deceleration)**2 + 0.5*self.acceleration*(15/self.acceleration)**2 + (15*((segment_speed - 15)/self.acceleration) + 0.5*self.acceleration*((segment_speed - 15)/self.acceleration)**2)
            T2 = distance/segment_speed
            time_loss = T1 - T2
        else:
            T1 = (segment_speed/self.deceleration) + (15/self.acceleration) + ((45 - 15)/self.acceleration) + ((segment_speed - 45)/self.acceleration) #deceleration, acceleration
            distance = 0.5*self.deceleration*(segment_speed/self.deceleration)**2 + 0.5*self.acceleration*(15/self.acceleration)**2 + 15*((45 - 15)/self.acceleration) + 0.5*self.acceleration*((45 - 15)/self.acceleration)**2 + 45*((segment_speed - 45)/self.acceleration) + 0.5*self.acceleration*((segment_speed - 45)/self.acceleration)**2
            T2 = distance/segment_speed
            time_loss = T1 - T2
        #default
        time_loss += self.default_duration
        return time_loss

    def create_find(self, row): #dict find = {name of the header: column index}
        find = {}
        col = 0
        for header in row:
            find[header] = col
            col += 1
        return find
