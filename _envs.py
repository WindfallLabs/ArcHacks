# -*- coding: utf-8 -*-
"""
_envs.py -- Environment Classes and Object-Orientification of ArcPy.
Author: Garin Wally; March 2017

Object Oriented in-memory processing using arcpy.
"""

import os
import re

import arcpy

from archacks import tbl2df, is_active, TOC, refresh

__all__ = ["Env", "MemoryWorkspace", "EZFieldMap", "_SpatialRelations",
           "MemoryLayer"]

'''
Supports nested selections:
    mains.selection.Within(nhoods.selection.where("Name = 'Northside'"))
All tests pass in and outside of arcmap

'''

arcpy.env.overwriteOutput = True


class Env(object):
    """Environment object."""
    def __init__(self, path):
        self.path = path
        self.activate()
        if self.datasets:
            self._load_datasets()

    def activate(self):
        arcpy.env.workspace = self.path

    def _load_datasets(self):
        for dataset in self.datasets:
            ds = dataset.split(".")[-1]
            setattr(self, ds, Env(dataset))

    @property
    def on_filesystem(self):
        self.activate()
        return os.path.exists(self.path)

    @property
    def tables(self):
        self.activate()
        return arcpy.ListTables()

    @property
    def features(self):
        self.activate()
        return arcpy.ListFeatureClasses()

    @property
    def datasets(self):
        self.activate()
        for dataset, dirs, fcs in list(arcpy.da.Walk(self.path))[1:]:
            ds = dataset.split(self.path.split("\\")[1])[1]
            yield "{}{}".format(self.path, ds)

    @property
    def dataset_names(self):
        self.activate()
        for dataset in self.datasets:
            ds = dataset.split(".")[-1]
            yield ds

    @property
    def rasters(self):
        self.activate()
        return arcpy.ListRasters()

    @property
    def contents(self):
        self.activate()
        data = []
        data.extend(self.tables)
        data.extend(self.features)
        data.extend(self.rasters)
        return data

    def get(self, data):
        for d in self.contents:
            if re.findall(data, d):
                return os.path.join(self.path, d)


class MemoryWorkspace(Env):
    """MemoryWorkspace."""
    def __init__(self):
        Env(self.path)
        # NOTE: don't trust the workspace variable:
        # always excplicately state 'in_memory', or use self.path
        arcpy.env.workspace = self.path

    @property
    def path(self):
        """Read-only"""
        return "in_memory"

    def add_layer(self, fc, rename=None, limit_fields=None, hide_old=True):
        """Adds a feature class to memory."""
        prefix = "mem_{}"
        if rename:
            out_name = prefix.format(rename)
        else:
            name = arcpy.Describe(fc).name
            if len(re.findall("\.", name)) > 1:
                name = name.split(".")[-1]
            out_name = prefix.format(name)
        arcpy.FeatureClassToFeatureClass_conversion(
            fc, self.path, out_name)
        # Try to stylize new layer after the non-memory layer's symbology
        #if is_active() and fc in TOC.contents.keys():
        #    apply_symbology(out_name, fc_name, hide_old)
        return

    def add_table(self, tbl, rename=None):
        """Adds a table to memory."""
        prefix = "mem_{}"
        if rename:
            out_name = prefix.format(rename)
        else:
            name = arcpy.Describe(tbl).name
            name = name.replace("$", "")
            if len(re.findall("\.", name)) > 1:
                name = name.split(".")[-1]
            out_name = prefix.format(name)
        arcpy.TableToTable_conversion(tbl, "in_memory", out_name)
        return

    def remove(self, fc):
        """Erases a feature class from in memory."""
        self.activate()
        if os.path.dirname(fc) != "in_memory" or fc.startswith("mem_"):
            raise IOError("Must be in memory")
        arcpy.Delete_management(fc)

    def get_memorylayer(self, data):
        """Returns data in memory as a MemoryLayer object."""
        return MemoryLayer(self.get(data))


# TODO: mv to _fields.py
class EZFieldMap(object):
    def __init__(self, parent):
        self.parent = parent
        self._mapping = arcpy.FieldMappings()
        self._mapping.addTable(self.parent.source)
        self._str = ""
        # Ensure it is ready to go
        self.as_str

    def reset(self):
        """Undo staged changes to field map."""
        self.__init__(self.parent)
        return

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
    def field_names(self):  # TODO: Aliases?; get names from current_order?
        return [re.findall('"(.*)"', n)[0] for n in self.as_list]

    @property
    def field_count(self):
        """Number of fields in mapping."""
        return len(self.current_order)

    def add(self, new_fieldmap):
        pass

    def is_safe(self):
        """Returns True if all field names are >= 10 in length."""
        # TODO: check for invalid names, etc
        # Shapefiles cut field names at len 10
        return all([len(f) <= 10 for f in self.field_names])

    def drop(self, field_names):
        """Removes a field from the mapping by name.
        Args:
            field_names (list): the list of fields to drop
        """
        new = []
        for m in self.as_list:
            if m.split(" ")[0] not in field_names:
                new.append(m)
        self._str = ";".join(new)
        return

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

    def rename_field(self, field_name, new_name):
        """Renames a field.
        Args:
            field_name (str): field to rename
            new_name (str): new field name
        """
        # Handle temp and permanent join fields
        regex_name = re.sub("\$\.", "\\$\\.", field_name)
        regex_name = re.sub("\$_", "\\$_", regex_name)
        regex = "{}(?!,)".format(regex_name)
        self._str = re.sub(regex, new_name, self._str)
        return

    def rename_by_split(self, split_seq, case=''):
        """Renames every column by splitting it at an input sequence.
        Args:
            split_seq (str): sequence to split field name by
            case (str; options "UPPER", "LOWER", "TITLE") sets case of string;
                defaults to existing
        Use:
            # Change 'County4_DBREAD_%View_OwnerAddress_<table>' to '<table>'
            >>> m.rename_split("OwnerAddress_")
        """
        for n in self.field_names:
            new_name = n.split(split_seq)[-1]
            if case == "TITLE":
                new_name = new_name.title()
            elif case == "UPPER":
                new_name = new_name.upper()
            elif case == "LOWER":
                new_name = new_name.lower()
            self.rename_field(n, new_name)
        return

    def get_field_type(self, field):
        """Returns a set of value types (Python) found within a field."""
        s = set()
        with arcpy.da.SearchCursor(self.parent, field) as cur:
            for row in cur:
                s.add(type(row[0]).__name__)
        return s

    def update(self):
        """Overwrites the current feature class using the Field Mapping."""
        if os.path.dirname(self.parent.source) != "in_memory":
            raise IOError("Must be in memory")
        # Create data as temp
        tmp_name = self.parent.name + "_fmap"
        arcpy.FeatureClassToFeatureClass_conversion(
            self.parent._lyr, "in_memory", tmp_name,
            field_mapping=self.as_str)
        # Overwrite old data with temp data
        arcpy.FeatureClassToFeatureClass_conversion(
            tmp_name, "in_memory", self.parent.name)
        # Remove temp
        arcpy.Delete_management(tmp_name)
        # Relink the parent object with the new data
        self.parent.__init__(self.parent.name)
        # Re-init the field map
        self.__init__(self.parent)
        return

    def export(self, out_name, out_loc="in_memory"):
        """Exports the current feature class using the Field Mapping."""
        arcpy.FeatureClassToFeatureClass_conversion(
            self.parent._lyr, out_loc, out_name,
            field_mapping=self.as_str)
        return

    def __str__(self):
        return self._str


# TODO: these selections only work on the <obj>.lyr object not what's visible in ArcMap
# Link with TOC objects
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

    def __init__(self, parent):
        self.parent = parent
        self.all = []
        self.definitions = {}
        self._set_defs()
        self._set_attrs()

    def _set_defs(self):
        self.definitions = {
            pair[0].strip(): pair[1].strip() for pair in
                [line.split(" - ") for line in self.__doc__.split("\n")]
            if pair[0].strip()}

    def _select_by_loc(self, sel_type):
        def select(select_features, search_distance=""):
            arcpy.SelectLayerByLocation_management(
                self.parent._lyr, sel_type,
                select_features._lyr, search_distance)
            return self.parent._lyr  # TODO: untested
        return select

    def _set_attrs(self):
        for k in self.definitions.keys():
            self.all.append(k)
            setattr(self, k.title(), self._select_by_loc(k))
        self.all.sort()

    # TODO: selected attrs dataframe

    def where(self, qry):
        sel_method = "NEW_SELECTION"
        if self.parent._lyr.getSelectionSet():
            sel_method = "SUBSET_SELECTION"
        arcpy.SelectLayerByAttribute_management(
            self.parent.name, sel_method, qry)  # parent._lyr
        return self.parent._lyr

    def switch(self):
        """Switches/inverts the current selection."""
        arcpy.SelectLayerByAttribute_management(
            self.parent.name, "SWITCH_SELECTION")
        return self.parent._lyr

    def clear(self):
        """Clears/deselects the current selection."""
        arcpy.SelectLayerByAttribute_management(
            self.parent._lyr, "CLEAR_SELECTION")
        return

    @property
    def count(self):
        """Returns the number of selected features."""
        try:
            return len(self.parent._lyr.getSelectionSet())
        except TypeError:
            return 0


class MemoryLayer(object):
    """Object-oriented in-memory data layer."""
    def __init__(self, data):
        desc = arcpy.Describe(data)
        self.source = desc.catalogPath
        if os.path.dirname(self.source) != "in_memory":
            raise IOError("Data is not in memory.")
        self.name = desc.name
        # Set the layer property to that in ArcMap's TOC if open
        if is_active():
            self._lyr = TOC[self.name]
        else:
            self._lyr = arcpy._mapping.Layer(data)
        self.fmap = EZFieldMap(self)
        self.selection = _SpatialRelations(self)
        self._joins = {}

    @property
    def desc(self):
        return arcpy.Describe(self.source)

    @property
    def fields(self):
        return {f.name: f for f in arcpy.Describe(self.source).fields}

    @property
    def attrs(self):  # Note: faster init time, slow when called
        return tbl2df(self.source)

    @property
    def feature_count(self):
        """Returns the number of features, or -1 if there is a selection."""
        if self.selection.count == 0:
            return int(arcpy.GetCount_management(self.source).getOutput(0))
        return -1

    def join(self, tbl, pkey, fkey):
        """Joins the current data with a table."""
        # Create a temp backup of joins dict; re-init-ing kills the old one
        current_joins = self.joins.copy()
        # Get table info
        tbl_desc = arcpy.Describe(tbl)
        tbl_name = tbl_desc.name
        tbl_fields = [f.name for f in tbl_desc.fields]
        # Join
        arcpy.JoinField_management(self.name, pkey, tbl, fkey)
        # Re-init the current object
        self.__init__(self.name)
        # Update the joins dict
        current_joins.update({tbl_name: tbl_fields})
        self._joins = current_joins
        return
        # TODO: spatial join with specified field to keep rather than all

    def drop_join(self, tbl):
        """Drops a joined table's attributes from the current data."""
        # Copy the joins dict
        j = self.joins.copy()
        # Stage the table's fields to be dropped from the field map
        self.fmap.drop(j.pop(tbl))
        # Update the field map
        self.fmap.update()
        self._joins = j
        return

    def add_field(self, f_name, f_type, f_len=10, code_blk="", calc="", alias=""):
        """Add and calc a new field. Using Python of course!
        Args:
            f_name (str): name of new field
            f_type (str): field type
            f_len (int): length of field
            code_blk (str): Python script to execute as pre-logic
            calc (str): the calculation code to populate the field
            alias (str): field alias
        """
        if not alias:
            alias = f_name
        f_name = f_name.replace(" ", "_")
        if f_type.upper() in ["FLOAT", "DOUBLE"]:
            f_len = 0
        try:
            arcpy.AddField_management(
                self.name, f_name, f_type, "", "", f_len, alias)
            if calc:
                arcpy.CalculateField_management(
                    self.name, f_name, calc, "PYTHON", code_blk)
        except Exception as e:
            # If an error with the calculation occurs, delete the created field
            if f_name in self.fields:
                arcpy.DeleteField_management(self.name, f_name)
            raise e
        return

    @property
    def joins(self):
        return self._joins

    @property
    def defquery(self):
        """Returns the layer's definition query."""
        return self._lyr.definitionQuery

    def set_defquery(self, qry=""):
        """Sets the layer's definition query."""
        self._lyr.definitionQuery = qry
        if is_active():
            refresh()
        return

'''
def calc_field(fc, field, func, func_attrs):
    with arcpy.da.UpdateCursor(fc, field) as cur:
        for row in cur:
            row[0] = func(func_attrs)
            cur.updateRow(row)
    return
'''


# TODO: better tests
'''
nhoods_path = r'Database Connections\gisrep.sde\gisrep.SDE.AdministrativeArea\gisrep.SDE.NH_Council_Boundaries'
mains_path = r'Database Connections\gisrep.sde\gisrep.SDE.SanitarySewer\gisrep.SDE.ssGravityMain'
parcel_path = r'Database Connections\gisrep.sde\gisrep.SDE.Parcels\gisrep.SDE.Parcels'
owner_path = r'Database Connections\County4.sde\County4.dbo.View_OwnerAddress'
forest_path = r'Database Connections\County4.sde\County4.dbo.AgForest'
prop_path = r'Database Connections\County4.sde\County4.dbo.Property'

# Load data into memory
mem = archacks.MemoryWorkspace()
#mem.add_layer(mains_path)
#mem.add_layer(nhoods_path)
mem.add_layer(parcel_path)
mem.add_table(owner_path)
mem.add_table(prop_path)
#mem.add_table(forest_path)
#assert len(mem.contents) == 5

#mains = mem.get_memorylayer("mem_ssGravityMain")
#nhoods = mem.get_memorylayer("mem_NH_Council_Boundaries")
parcels = mem.get_memorylayer("mem_Parcels")

# Test field map edits
#mains.fmap.reorder([0, 2, 5], True)
#mains.fmap.update()
#assert len(mains.fields) == 5

# Reduce parcels to intersection with nhoods & join with owners
#parcels.selection.Intersect(nhoods)
#parcels.fmap.update()
#assert parcels.feature_count == 25237

parcels.join('mem_View_OwnerAddress', "ParcelID", "StateGeo")
parcels.join("mem_Property", "PropertyID", "PropertyID")
#assert "City" in parcels.fields
#parcels.join('mem_AgForest', "PropertyID", "PropertyID")
#assert "ProdCommodity" in parcels.fields
#parcels.drop_join('mem_View_OwnerAddress')
#assert "City" not in parcels.fields
'''
