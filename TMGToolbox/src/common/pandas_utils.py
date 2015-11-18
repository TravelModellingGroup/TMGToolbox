import warnings as warn
import inro.modeller as _m
mm = _m.Modeller()

class Face(_m.Tool()):
    def page(self):
        pb = _m.ToolPageBuilder(self, runnable=False, title="Utilities",
                                description="Collection of tools working with <a href='http://pandas.pydata.org/'>pandas</a>",
                                branding_text="- TMG Toolbox")

        pb.add_text_element("To import, call inro.modeller.Modeller().module('%s')" %str(self))

        try: import pandas
        except ImportError:
            pb.add_text_element("<font color='red'><b>ImportWarning:</b> Pandas library is not installed.")

        return pb.render()

try:
    import pandas as pd
    import numpy as np

    def load_node_dataframe(scenario, pythonize_exatts = False):
        '''
        Creates a table for node attributes in a scenario.

        Args:
            scenario: An instance of inro.emme.scenario.Scenario
            pythonize_exatts: Flag to make extra attribute names 'Pythonic'. If set
                to True, then "@stn1" will become "x_stn1".

        Returns:

        '''
        attr_list = scenario.attributes("NODE")
        package = scenario.get_attribute_values("NODE", attr_list)

        node_indexer = pd.Series(package[0])
        node_indexer.index.name = 'i'
        tables = package[1:]

        if pythonize_exatts:
            attr_list = [attname.replace("@", "x_")  for attname in attr_list]

        df = pd.DataFrame(index=node_indexer.index)
        for attr_name, table in zip(attr_list, tables):
            data_array = np.array(table)
            reindexed = data_array.take(node_indexer.values)
            df[attr_name] = reindexed

        df['is_centroid'] = df.index.isin(scenario.zone_numbers)

        return df

    def load_link_dataframe(scenario, pythonize_exatts = False):
        '''
        Creates a table for link attributes in a scenario.

        Args:
            scenario: An instance of inro.emme.scenario.Scenario
            pythonize_exatts: Flag to make extra attribute names 'Pythonic'. If set
                to True, then "@stn1" will become "x_stn1".

        Returns: pandas.DataFrame

        '''
        attr_list = scenario.attributes('LINK')
        if "vertices" in attr_list: attr_list.remove("vertices")

        data_pack = scenario.get_attribute_values('LINK', attr_list)
        data_positions = data_pack[0]
        tables = data_pack[1:]

        link_indexer = {}
        for i, outgoing_data in data_positions.iteritems():
            for j, pos in outgoing_data.iteritems():
                link_indexer[(i,j)] = pos
        link_indexer = pd.Series(link_indexer)
        link_indexer.index.names = 'i j'.split()

        if pythonize_exatts:
            attr_list = [attname.replace("@", "x_")  for attname in attr_list]

        df = pd.DataFrame(index= link_indexer.index)
        for attr_name, table in zip(attr_list, tables):
            data_array = np.array(table)
            reindexed = data_array.take(link_indexer.values)
            df[attr_name] = reindexed

        return df

    def load_turn_dataframe(scenario, pythonize_exatts = False):
        '''
        Creates a table for turn attributes in a scenario.

        Args:
            scenario: An instance of inro.emme.scenario.Scenario
            pythonize_exatts: Flag to make extra attribute names 'Pythonic'. If set
                to True, then "@stn1" will become "x_stn1".

        Returns:

        '''
        attr_list = scenario.attributes("TURN")
        package = scenario.get_attribute_values("TURN", attr_list)

        index_data = package[0]
        tables = package[1:]

        turn_indexer = {}
        for (i, j), outgoing_data in index_data.iteritems():
            for k, pos in outgoing_data.iteritems():
                turn_indexer[(i,j,k)] = pos
        turn_indexer = pd.Series(turn_indexer)
        turn_indexer.index.names = "i j k".split()

        if pythonize_exatts:
            attr_list = [attname.replace("@", "x_")  for attname in attr_list]

        df = pd.DataFrame(index= turn_indexer.index)
        for attr_name, table in zip(attr_list, tables):
            data_array = np.array(table)
            reindexed = data_array.take(turn_indexer.values)
            df[attr_name] = reindexed

        return df

    def load_transit_line_dataframe(scenario, pythonize_exatts = False):
        '''
        Creates a table for transit line attributes in a scenario.

        Args:
            scenario: An instance of inro.emme.scenario.Scenario
            pythonize_exatts: Flag to make extra attribute names 'Pythonic'. If set
                to True, then "@stn1" will become "x_stn1".

        Returns:

        '''
        attr_list = scenario.attributes("TRANSIT_LINE")
        package = scenario.get_attribute_values("TRANSIT_LINE", attr_list)

        line_indexer = pd.Series(package[0])
        line_indexer.index.name = 'line'
        tables = package[1:]

        if pythonize_exatts:
            attr_list = [attname.replace("@", "x_")  for attname in attr_list]

        df = pd.DataFrame(index=line_indexer.index)
        for attr_name, table in zip(attr_list, tables):
            data_array = np.array(table)
            reindexed = data_array.take(line_indexer.values)
            df[attr_name] = reindexed

        return df

    def load_transit_segment_dataframe(scenario, pythonize_exatts = False):
        '''
        Creates a table for transit segment attributes in a scenario.

        Args:
            scenario: An instance of inro.emme.scenario.Scenario
            pythonize_exatts: Flag to make extra attribute names 'Pythonic'. If set
                to True, then "@stn1" will become "x_stn1".

        Returns:

        '''
        attr_list = scenario.attributes("TRANSIT_SEGMENT")
        package = scenario.get_attribute_values("TRANSIT_SEGMENT", attr_list)

        index_data = package[0]
        tables = package[1:]

        segment_indexer = {}
        for line, segment_data in index_data.iteritems():
            for tupl, pos in segment_data.iteritems():
                if len(tupl) == 3: i,j, loop = tupl
                else:
                    i,j = tupl
                    loop = 0

                segment_indexer[(line, i, j, loop)] = pos
        segment_indexer = pd.Series(segment_indexer)
        segment_indexer.index.names = "line i j loop".split()

        if pythonize_exatts:
            attr_list = [attname.replace("@", "x_")  for attname in attr_list]

        df = pd.DataFrame(index=segment_indexer.index)
        for attr_name, table in zip(attr_list, tables):
            data_array = np.array(table)
            reindexed = data_array.take(segment_indexer.values)
            df[attr_name] = reindexed

        return df

except ImportError:
    warn.warn(ImportWarning("Older versions of Emme Modeller do not come with pandas library installed."))