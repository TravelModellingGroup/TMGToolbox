import warnings as warn
from inro.emme.matrix import MatrixData
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
            A dataframe with the results.  None if there are no turns.
        '''
        attr_list = scenario.attributes("TURN")
        package = scenario.get_attribute_values("TURN", attr_list)

        index_data = package[0]
        tables = package[1:]

        turn_index = []
        indexer_values = []

        for (i,j), outgoing_data in index_data.iteritems():
            for k, pos in outgoing_data.iteritems():
                turn_index.append((i,j,k))
                indexer_values.append(pos)
        if len(turn_index) == 0:
            return None
        turn_indexer = pd.Series(indexer_values, pd.MultiIndex.from_tuples(turn_index, names=['i', 'j', 'k']))

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

    def matrix_to_pandas(mtx, scenario_id=None):
        '''
        Converts Emme Matrix objects to Pandas Series or DataFrames. Origin and Destination matrices will be
        converted to Series, while Full matrices will be converted to DataFrames. Scalar matrices are unsupported.

        Args:
            mtx: Either a Matrix object or a MatrixData object
            scenario_id: Int, optional. Must be provided if a `mtx` is a Matrix object.

        Returns: Series or DataFrame, depending on the type of matrix.

        '''
        if hasattr(mtx, 'prefix'): # Duck typing check for Matrix object rather than Matrix Data
            assert mtx.type != 'SCALAR', "Scalar matrices cannot be converted to DataFrames"
            md = mtx.get_data(scenario_id)
        else: md = mtx

        zones_tupl = md.indices
        if len(zones_tupl) == 1:
            # Origin or Destination matrix
            idx = pd.Index(zones_tupl[0])
            idx.name = 'zone'
            vector = md.to_numpy()
            return pd.Series(vector, index=idx)
        elif len(zones_tupl) == 2:
            # Full matrix
            idx = pd.Index(zones_tupl[0])
            idx.name = 'p'
            cols = pd.Index(zones_tupl[1])
            cols.name = 'q'
            matrix = md.to_numpy()
            return pd.DataFrame(matrix, index=idx, columns=cols)
        else:
            raise ValueError("Could not infer matrix from object type %s", repr(mtx))

    def pandas_to_matrix(series_or_dataframe):
        '''
        Converts a Series or DataFrame back to a MatrixData object

        Args:
            series_or_dataframe: Series or DataFrame

        Returns: MatrixData object.

        '''
        if isinstance(series_or_dataframe, pd.Series):
            indices = list(series_or_dataframe.index.values)
            md = MatrixData(indices)
            md.from_numpy(series_or_dataframe.values)
            return md
        elif isinstance(series_or_dataframe, pd.DataFrame):
            indices = list(series_or_dataframe.index.values), list(series_or_dataframe.columns.values)
            md = MatrixData(indices)
            md.from_numpy(series_or_dataframe.values)
            return md
        else: raise TypeError("Expected a Series or DataFrame, got %s" %type(series_or_dataframe))

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
                    loop = 1

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

    def _align_multiindex(index, levels_to_keep):
        '''Removes levels of a MultiIndex that are not required for the join.'''
        for levelname in reversed(index.names):
            if levelname not in levels_to_keep: index = index.droplevel(levelname)
        return index

    def reindex_series(right_series, left_indexer, left_levels=None, right_levels=None, **kwargs):
        '''
        MultiIndex-to-MultiIndex friendly wrapper function for `Series.reindex()`. Useful for
        re-indexing data between links and transit segments.

        Args:
            right_series: The right-hand-side Series to reindex
            left_indexer: The left-hand-side indexer-object, preferably an Index object to avoid duplication
            left_levels: The levels in the left-hand-side indexer on which to perform the join. Can be specified as
                either positional indices or level names. `None` can also be provided, in which case all levels from
                the left indexer are used.
            right_levels: The levels in the right_series.index on which to perform the join. Can be specified as
                either positional indices or level names. `None` can also be provided, in which case all levels from the
                right indexer are used. The number of specified levels MUST be the same for both the LEFT and the RIGHT.
            **kwargs: Any kwargs accepted by `Series.reindex()` (for example, 'fill_value')

        Returns: The reindexed Series.

        '''
        right_indexer = right_series.index
        left_indexer = pd.Index(left_indexer)

        right_index = right_series.index
        left_index = left_indexer

        left_is_multi = isinstance(left_indexer, pd.MultiIndex)
        right_is_multi = isinstance(right_indexer, pd.MultiIndex)

        left_levels = left_indexer.names if left_is_multi and left_levels is None else left_levels
        right_levels = right_indexer.names if right_is_multi and right_levels is None else right_levels

        if left_is_multi and right_is_multi:
            if len(left_levels) != len(right_levels):
                raise IndexError("Cannot join two multi-indexs on different number of levels.")

        if left_is_multi:
            left_indexer = _align_multiindex(left_indexer, left_levels)
        if right_is_multi:
            right_indexer = _align_multiindex(right_indexer, right_levels)

        try:
            right_series.index = right_indexer
            ret = right_series.reindex(left_indexer, **kwargs)
            ret.index = left_index
            return ret
        finally:
            right_series.index = right_index


    def split_zone_in_matrix(base_matrix, old_zone, new_zones, proportions):
        '''
        Takes a zone in a matrix (represented as a DataFrame) and splits it into several new zones,
        prorating affected cells by a vector of proportions (one value for each new zone). The old
        zone is removed.

        Args:
            base_matrix: The matrix to re-shape, as a DataFrame
            old_zone: Integer number of the original zone to split
            new_zones: List of integers of the new zones to add
            proportions: List of floats of proportions to split the original zone to. Must be the same
                length as `new_zones` and sum to 1.0

        Returns: Re-shaped DataFrame

        '''
        assert isinstance(base_matrix, pd.DataFrame), "Base matrix must be a DataFrame"

        old_zone = int(old_zone)
        new_zones = np.array(new_zones, dtype=np.int32)
        proportions = np.array(proportions, dtype=np.float64)

        assert len(new_zones) == len(proportions), "Proportion array must be the same length as the new zone array"
        assert len(new_zones.shape) == 1, "New zones must be a vector"
        assert base_matrix.index.equals(base_matrix.columns), "DataFrame is not a matrix"
        assert np.isclose(proportions.sum(), 1.0), "Proportions must sum to 1.0 "

        n_new_zones = len(new_zones)

        intersection_index = base_matrix.index.drop(old_zone)
        new_index = intersection_index
        for z in new_zones: new_index = new_index.insert(-1, z)
        new_index = pd.Index(sorted(new_index))

        new_matrix = pd.DataFrame(0, index=new_index, columns=new_index, dtype=base_matrix.dtypes.iat[0])

        # 1. Copy over the values from the regions of the matrix not being updated
        new_matrix.loc[intersection_index, intersection_index] = base_matrix

        # 2. Prorate the row corresponding to the dropped zone
        # This section (and the next) works with the underlying Numpy arrays, since they handle
        # broadcasting better than Pandas does
        original_row = base_matrix.loc[old_zone, intersection_index]
        original_row = original_row.values[:] # Make a shallow copy to preserve shape of the original data
        original_row.shape = 1, len(intersection_index)
        proportions.shape = n_new_zones, 1
        result = pd.DataFrame(original_row * proportions, index=new_zones, columns=intersection_index)
        new_matrix.loc[result.index, result.columns] = result

        # 3. Proprate the column corresponding to the dropped zone
        original_column = base_matrix.loc[intersection_index, old_zone]
        original_column = original_column.values[:]
        original_column.shape = len(intersection_index), 1
        proportions.shape = 1, n_new_zones
        result = pd.DataFrame(original_column * proportions, index=intersection_index, columns=new_zones)
        new_matrix.loc[result.index, result.columns] = result

        # 4. Expand the old intrazonal
        proportions_copy = proportions[:,:]
        proportions_copy.shape = 1, n_new_zones
        proportions.shape = n_new_zones, 1

        intrzonal_matrix = proportions * proportions_copy
        intrazonal_scalar = base_matrix.at[old_zone, old_zone]

        result = pd.DataFrame(intrazonal_scalar * intrzonal_matrix, index=new_zones, columns=new_zones)
        new_matrix.loc[result.index, result.columns] = result

        return new_matrix

except ImportError:
    warn.warn(ImportWarning("Older versions of Emme Modeller do not come with pandas library installed."))