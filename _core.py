# -*- coding: utf-8 -*-
"""
Misc ArcPy Addons
Author: Garin Wally
License: MIT

"""
import os
import re
import sys
import sqlite3 as lite

import pandas as pd
import ogr

import arcpy


type_map = {
    "int": ["Double", "Integer", "ShortInteger"],
    "long": ["Float"],
    "str": ["Text", "String"]}


def is_active(exe="arcmap"):
    regex = "(?i){}.exe".format(exe)
    if re.findall(regex, sys.executable.replace("\\", "/")):
        return True
    return False


# =============================================================================
# LOCKS

def get_locks(gdb):
    """Generates a list of current locks in a gdb."""
    locks = [f for f in os.listdir(gdb) if ".lock" in f]
    for lock in locks:
        try:
            with open(gdb, "w") as f:
                pass
        except IOError:
            yield lock


def get_lock_users(gdb):
    """Lists the users holding locks on a gdb."""
    locks = [f.split(".")[1] for f in get_locks(gdb)]
    return list(set(locks))

# =============================================================================
# STRING FORMATTERS

def in_dataset(path):
    if not os.path.split(path)[0].endswith(".gdb"):
        return True
    return False


def rm_ds(dataset_path):
    """Removes the dataset name from a GDB path."""
    if in_dataset(dataset_path):
        parts = os.path.split(dataset_path)
        return os.path.join(os.path.split(parts[0])[0], parts[1])
    return dataset_path


# =============================================================================
# TABLE UTILITIES

def fill_na(fc, fields, repl_value=0):
    """Update '<Null>' values (None) in input fields.
    Args:
        fc (str): name or path of input feature class
        fields (list): list of fields to replace NULL with 'repl_value'
        repl_value (many): value to replace NULL
    """
    desc_fields = arcpy.Describe(fc).fields
    field_objs = [f for f in desc_fields if f.name in fields]
    if len(field_objs) != len(fields):
        raise AttributeError("Check spelling of field names")
    # Make sure fields are editable
    are_editable = [f.editable for f in field_objs]
    if not all(are_editable):
        ne_fields = [f.name for f in field_objs if not f.editable]
        raise AttributeError("Field(s) not editable: {}".format(ne_fields))
    # Make sure repl_value matches type of all input fields
    m = [f.type in type_map[type(repl_value).__name__] for f in field_objs]
    if not all(m):
        raise TypeError("Replace value and column types do not match")
    # Change the NULL values (None) to 0
    with arcpy.da.UpdateCursor(fc, fields) as cur:
        for row in cur:
            for v in row:
                if v is None:
                    row[row.index(v)] = repl_value
                cur.updateRow(row)
    return


def tbl2df(tbl, fields=["*"]):
    """Loads a table or featureclass into a pandas dataframe.
    Args:
        tbl (str): table or featureclass path or name (in Arc Python Window)
        fields (list): names of fields to load; value of '*' loads all fields
    """
    # List holds each row as a transposed dataframe
    frames = []
    if fields == ["*"] or fields == "*":
        fields = [f.name for f in arcpy.Describe(tbl).fields]
    with arcpy.da.SearchCursor(tbl, fields) as cur:
        for row in cur:
            row_df = pd.DataFrame(list(row)).T
            row_df.columns = cur.fields
            frames.append(row_df)
    # Make a single dataframe from the list
    df = pd.concat(frames)
    df.reset_index(inplace=True, drop=True)
    return df


def ogdb2df(fc_path, fields=["*"]):
    """Open ESRI GDB data as a pandas dataframe (uses osgeo/OpenFileGDB).
    This option can be much faster than tbl2df.
    Args:
        gdb_path (str): path to gdb or path to feature in gdb
        fields (list): names of fields to load; value of '*' loads all fields
    """
    fc_path = rm_ds(fc_path)
    driver = ogr.GetDriverByName("OpenFileGDB")
    gdb_path, fc_name = os.path.split(fc_path)
    gdb = driver.Open(gdb_path)
    fc = gdb.GetLayerByName(fc_name)
    schema = fc.schema
    if fields == ["*"] or fields == "*":
        fields = [f.name for f in schema]
    frames = []
    feat = fc.GetNextFeature()
    while feat:
        row = [feat.GetField(f) for f in fields]
        row_df = pd.DataFrame(row).T
        row_df.columns = fields
        frames.append(row_df)
        feat = fc.GetNextFeature()
    df = pd.concat(frames)
    df.index = range(len(df))
    return df


def tbl2excel(tbl, out_path, fields=["*"]):
    """Exports an input table or feature class to Excel."""
    df = tbl2df(tbl, fields)
    df.to_excel(out_path)
    return


def groupby(fc, gb_field, summary_field):
    fields = [gb_field, summary_field]
    df = tbl2df(fc, fields)
    return df.groupby(gb_field).sum()


def drop_all(fc, keep=[]):
    """Drops all nonrequired columns except those specified."""
    warnings = []
    fields = [f.name for f in arcpy.ListFields(fc)]
    # TODO: what about difference between keep and all_fields?
    rm_fields = list(set(fields).symmetric_difference(set(keep)))
    for field in rm_fields:
        try:
            arcpy.DeleteField_management(fc, field)
        except Exception:  # TODO:
            warnings.append(field)
    print("Field(s) could not be removed: {}".format(warnings))
    return


def is_unique(fc, fields):
    """Checks if fields of a feature class have all unique values."""
    if isinstance(fields, str):
        fields = [fields]
    s = set()
    row_cnt = 0
    with arcpy.da.SearchCursor(fc, fields) as cur:
        for row in cur:
            row_cnt += 1
            s.add(row[0])
    if len(s) == row_cnt:
        return True
    return False


def max_in_list(find_str, in_list, digits=2):
    """Find the field containing a substring and the largest number.
    Good for finding the max year of a series of fields.
    Args:
        find_str (str): substring of field name; use '' if for only max
        in_list (list): a list of field names to search
    Returns the field name containing the max number
    Use:
        >>> fields = ["Year", "Pop10", "Pop20", "Pop30", "Average60"]
        >>> max_in_list("Pop", fields)
        "Pop30"
        >>> max_in_list("", fields)
        "Average60"
    """
    # Filter out fields without numbers
    filt_re = "\d{}".format(digits)
    filtered_list = [f for f in in_list if re.findall(filt_re, f)]
    print filtered_list
    if not filtered_list:
        raise AttributeError("No list value contains a 2-digit number")
    m = max([int(re.findall("\d{2}", i)[0]) for i in filtered_list
             if find_str in i])
    return [i for i in in_list if str(m) in i][0]


def sum_field(fc, field):
    """Returns the sum of a field."""
    with arcpy.da.SearchCursor(fc, field) as cur:
        total = 0
        for row in cur:
            total += row[0]
    return total


def list_all_fields(fc):
    """Returns a list of all fields, includes joined fields."""
    fields = [f.name for f in arcpy.Describe(fc).fields]
    return fields


def list_joins(fc):
    """Returns a set of tables currently joined to a feature class."""
    fields = list_all_fields(fc)
    s = set()
    [s.add(j.split("$")[0]) for j in fields if "$" in j]
    return s


def regex_fields(fc, field_regex, escape_tables=True):
    """Returns a list of field names matching a regular expression."""
    for f in arcpy.Describe(fc).fields:
        if escape_tables:
            field_regex = field_regex.replace("$.", "\\$\\.")
        if re.findall(field_regex, f.name):
            yield f.name


# =============================================================================
# FIELD MAPS
# Note: a field map is a string describing a field and its merge rules
# Note: a field mapping is a list of field maps joined by ';'

class EZFieldMap(object):
    def __init__(self, fc):
        self.fc = fc
        self._mapping = arcpy.FieldMappings()
        self._mapping.addTable(self.fc)
        self._str = ""

    @property
    def as_str(self):
        """Mapping as string."""
        if self._str == "":
            self._str = self._mapping.exportToString()
        return self._str

    @property
    def as_list(self):
        """Mapping as list."""
        return self.as_str.split(";")

    @property
    def current_order(self):
        """The current order of fields in mapping."""
        order = []
        for i in self.as_list:
            order.append((self.as_list.index(i), i.split(" ")[0]))
        return order

    @property
    def field_count(self):
        """Number of fields in mapping."""
        return len(self.current_order)

    def reorder(self, new_order, drop=False):
        """Reindexes the order of fields.
        Args:
            new_order (list): assign new index by position in list
            drop (bool): allows dropping of fields on reorder; default False
        Example:
            >>> e.current_order
            [(0, u'Overlay'), (1, u'FullName'), (2, u'Notes')]
            >>> e.reorder([2, 0, 1])
            >>> e.current_order
            [(0, u'Notes'), (1, u'Overlay'), (2, u'FullName')]
        """
        if not drop and len(new_order) != self.field_count:
            err_msg = ("Option to drop fields is disabled; "
                       "Requires list of length: {}".format(self.field_count))
            raise AttributeError(err_msg)
        li = []
        for n in new_order:
            li.insert(new_order.index(n), self.as_list[n])
        self._str = ";".join(li)
        return

    def rename(self, field_name, new_name):
        """Renames a field."""
        regex_name = re.sub("\$\.", "\\$\\.", field_name)
        regex = "{}(?!,)".format(regex_name)
        self._str = re.sub(regex, new_name, self._str)
        return

    def get_field_type(self, field):
        """Returns a set of value types found within a field."""
        s = set()
        with arcpy.da.SearchCursor(self.fc, field) as cur:
            for row in cur:
                s.add(type(row[0]).__name__)
        return s

    def export_fc(self, location, output_name, qry=""):
        """Calls fc2fc using the Field Mapping."""
        # TODO: validation?
        arcpy.FeatureClassToFeatureClass_conversion(
            self.fc, location, output_name, qry, self.as_str)
        return

    def __str__(self):
        return self._str

'''
import archacks
mem = archacks.MemoryWorkspace()
mem.add_layer("MSLAZONE")
# Add field

e = archacks.EZFieldMap("mem_MSLAZONE")
e.reorder([34, 32, 33, 12, 15, 16, 17, 18, 21, 19, 20], True)
e.rename("base_fixed", "Base")
e.rename("overlay_fixed", "Overlay")
e.rename("zoning_new", "Zoning")
e.export_fc(gdb, "CityZoning")
'''


def get_fieldmap(fc):
    """Get current fieldmapping as list."""
    mappings = arcpy.FieldMappings()
    mappings.addTable(fc)


def make_fieldmap(fc, field, rename=None, merge_rule="First"):
    """Easy manipulation of FieldMap/Mappings. Not a valid FieldMap object."""
    m = arcpy.FieldMap()
    m.mergeRule = merge_rule
    maps = arcpy.FieldMappings()
    full_f_name = list(regex_fields(fc, field))[0]
    m.addInputField(fc, full_f_name)
    maps.addFieldMap(m)
    s = maps.exportToString()
    if rename:
        regex_name = re.sub("\$\.", "\\$\\.", full_f_name)
        regex = "{}(?!,)".format(regex_name)
        s = re.sub(regex, rename, s)
    return s


def make_fieldmaps(fc, fields):
    if isinstance(fields, dict):
        for field, rename in fields.items():
            yield make_fieldmap(fc, field, rename)
    else:
        for field in fields:
            yield make_fieldmap(fc, field)


def join_fieldmaps(maps):
    return ";".join(maps)


def get_field_type(fc, field):
    """Returns a set of value types found within a field."""
    s = set()
    with arcpy.da.SearchCursor(fc, field) as cur:
        for row in cur:
            s.add(type(row[0]).__name__)
    return s


# =============================================================================
# SELECTION METHODS

def diminished_intersection(target, source, dim_val=5, dim_unit="FOOT"):
    """Shrink the source feature to prevent intersecting with shared lines.
    Args:
        target (str): features to select
        source (str): data to select by
        dim_val (int): measurement to reduce source features by (e.g. 5)
        dim_unit (str): measurement unit (e.g. 'FOOT')
    """
    tmp_fc = "in_memory/diminished_source_tmp"
    arcpy.Buffer_analysis(source, tmp_fc, dim_val, dim_unit)
    arcpy.SelectLayerByLocation_management(target, "INTERSECT", tmp_fc)
    arcpy.Delete_management(tmp_fc)
    arcpy.RefreshTOC()
    return


# TODO: 'spatial join' that copies a field from the selected to the
#  intersecting features

# =============================================================================
# WRAPPERS

def fc2fc(in_fc, full_out_path, where=None, limit_fields=None):
    """Wraps 'arcpy.FeatureClassToFeatureClass_conversion with a short name."""
    full_out_path = full_out_path.replace("\\", "/")
    out_path, out_name = os.path.split(full_out_path)
    mapping = None
    # TODO:
    #if limit_fields:
    #    mapping = limit_fields(in_fc, limit_fields)
    return arcpy.FeatureClassToFeatureClass_conversion(
        in_fc, out_path, out_name, where, mapping)


# =============================================================================
# CONVENIENCE OBJECTS

class _SpatialRelations(object):
    __doc__ = """
        INTERSECT - The features in the join features will be matched if they intersect a target feature. This is the default. Specify a distance in the search_radius parameter.
        INTERSECT_3D - The features in the join features will be matched if they intersect a target feature in three-dimensional space (x, y, and z). Specify a distance in the search_radius parameter.
        WITHIN_A_DISTANCE - The features in the join features will be matched if they are within a specified distance of a target feature. Specify a distance in the search_radius parameter.
        WITHIN_A_DISTANCE_GEODESIC - Same as WITHIN_A_DISTANCE except that geodesic distance is used rather than planar distance. Choose this if your data covers a large geographic extent or the coordinate system of the inputs is unsuitable for distance calculations.
        WITHIN_A_DISTANCE_3D - The features in the join features will be matched if they are within a specified distance of a target feature in three-dimensional space. Specify a distance in the search_radius parameter.
        CONTAINS - The features in the join features will be matched if a target feature contains them. The target features must be polygons or polylines. For this option, the target features cannot be points, and the join features can only be polygons when the target features are also polygons.
        COMPLETELY_CONTAINS - The features in the join features will be matched if a target feature completely contains them. Polygon can completely contain any feature. Point cannot completely contain any feature, not even a point. Polyline can completely contain only polyline and point.
        CONTAINS_CLEMENTINI - This spatial relationship yields the same results as COMPLETELY_CONTAINS with the exception that if the join feature is entirely on the boundary of the target feature (no part is properly inside or outside) the feature will not be matched. Clementini defines the boundary polygon as the line separating inside and outside, the boundary of a line is defined as its end points, and the boundary of a point is always empty.
        WITHIN - The features in the join features will be matched if a target feature is within them. It is opposite to CONTAINS. For this option, the target features can only be polygons when the join features are also polygons. Point can be join feature only if point is target.
        COMPLETELY_WITHIN - The features in the join features will be matched if a target feature is completely within them. This is opposite to COMPLETELY_CONTAINS.
        WITHIN_CLEMENTINI - The result will be identical to WITHIN except if the entirety of the feature in the join features is on the boundary of the target feature, the feature will not be matched. Clementini defines the boundary polygon as the line separating inside and outside, the boundary of a line is defined as its end points, and the boundary of a point is always empty.
        ARE_IDENTICAL_TO - The features in the join features will be matched if they are identical to a target feature. Both join and target feature must be of same shape type—point-to-point, line-to-line, and polygon-to-polygon.
        BOUNDARY_TOUCHES - The features in the join features will be matched if they have a boundary that touches a target feature. When the target and join features are lines or polygons, the boundary of the join feature can only touch the boundary of the target feature and no part of the join feature can cross the boundary of the target feature.
        SHARE_A_LINE_SEGMENT_WITH - The features in the join features will be matched if they share a line segment with a target feature. The join and target features must be lines or polygons.
        CROSSED_BY_THE_OUTLINE_OF - The features in the join features will be matched if a target feature is crossed by their outline. The join and target features must be lines or polygons. If polygons are used for the join or target features, the polygon's boundary (line) will be used. Lines that cross at a point will be matched, not lines that share a line segment.
        HAVE_THEIR_CENTER_IN - The features in the join features will be matched if a target feature's center falls within them. The center of the feature is calculated as follows: for polygon and multipoint the geometry's centroid is used, and for line input the geometry's midpoint is used. Specify a distance in the search_radius parameter.
        CLOSEST - The feature in the join features that is closest to a target feature is matched. See the usage tip for more information. Specify a distance in the search_radius parameter.
        CLOSEST_GEODESIC - Same as CLOSEST except that geodesic distance is used rather than planar distance. Choose this if your data covers a large geographic extent or the coordinate system of the inputs is unsuitable for distance calculations.
        """

    def __init__(self):
        self.all = []
        self.definitions = {}
        self._set_defs()
        self._set_attrs()

    def _set_defs(self):
        self.definitions = {
            pair[0].strip(): pair[1].strip() for pair in
                [line.split(" - ") for line in self.__doc__.split("\n")]
            if pair[0].strip()}

    def _set_attrs(self):
        for k in self.definitions.keys():
            self.all.append(k)
            setattr(self, k, k)
        self.all.sort()

SpatialRelations = _SpatialRelations()


def tabulate_SRIDs():
    conn = lite.connect(":memory:")
    conn.enable_load_extension(True)
    conn.load_extension("spatialite400x")
    cur = conn.cursor()
    cur.execute("SELECT InitSpatialMetaData()")
    cur.execute("SELECT * FROM spatial_ref_sys")
    headers = [col[0] for col in cur.description]
    rows = cur.fetchall()
    types = (type(col).__name__ for col in rows)
    # Dataframe stuff
    frames = []
    for row in rows:
        row_df = pd.DataFrame(list(row)).T
        row_df.columns = headers
        frames.append(row_df)
    # Make a single dataframe from the list
    df = pd.concat(frames)
    df.reset_index(inplace=True, drop=True)
    cur.close()
    conn.close()
    del cur, conn
    # Make Arc Table
    #arcpy.CreateTable_management("in_memory", "SRIDs")
    #for pair in zip(headers, types):
    #    arcpy.AddField_management("SRIDs", pair[0], map_field_type(pair[1]),
    return df
