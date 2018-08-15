# -*- coding: utf-8 -*-
"""
Misc ArcPy Addons
Author: Garin Wally
License: MIT
"""

import os
import re
import sys
#from time import sleep
from queue import Queue
from subprocess import Popen, PIPE
from collections import OrderedDict
from xml.dom import minidom as DOM
from ConfigParser import RawConfigParser

import pandas as pd
import numpy as np
import ogr

import arcpy

#from archacks import DIR

DIR = os.path.abspath(os.path.dirname(__file__))
NEW_GROUP_LAYER = os.path.join(DIR, "NewGroupLayer.lyr")


type_map = {
    "int": ["Double", "Integer", "ShortInteger"],
    "long": ["Float"],
    "str": ["Text", "String"]}


# TODO: not the best...
def is_active(exe="arcmap"):
    regex = "(?i){}.exe".format(exe)
    if re.findall(regex, sys.executable.replace("\\", "/")):
        return True
    return False


# MapDocument() cannot be called from within classes and must be global
if is_active():
    MXD = arcpy.mapping.MapDocument("CURRENT")
else:
    MXD = None


class GDB(object):
    def __init__(self, gdb_path, srid=0, datasets=[], default_queue_ds=""):
        """Geodatabase Object.
        Args:
            gdb_path (str): path to new/existing Geodatabase
            srid (int): Spatial Reference ID to use for datasets only
            datasets (list): dataset names to create using SRID
            default_queue_ds (str): dataset name to use as default for queue
        """
        self.path = gdb_path
        if not self.path.endswith(".gdb"):
            raise AttributeError("Not a Geodatabase")
        self.parent_folder = os.path.dirname(self.path)
        self.name = os.path.basename(self.path)
        self.srid = srid
        self.sr = arcpy.SpatialReference(self.srid)
        self.datasets = datasets
        self.default_queue_ds = default_queue_ds
        self.data_queue = Queue()

    def build(self):
        """Builds gdb, creates datasets, adds queued data."""
        if not os.path.exists(self.path):
            arcpy.CreateFileGDB_management(self.parent_folder, self.name)
        arcpy.RefreshCatalog(self.path)
        arcpy.env.workspace = self.path
        for ds in self.datasets:
            arcpy.CreateFeatureDataset_management(self.path, ds, self.srid)
            arcpy.RefreshCatalog(os.path.join(self.path, ds))
        if self.data_queue:
            self.load_queued_data()
        return

    def add(self, in_data_path, data_name="", dataset=""):
        """Adds input featureclass to geodatabase.
        Args:
            in_data_path (str): path to input data
            data_name (str): optionally rename entered data
            dataset (str): dataset to send imported data
        """
        if not data_name:
            data_name = os.path.basename(in_data_path)
        if "sde" in data_name.lower():
            data_name = data_name.split(".")[-1]
        elif "." in data_name:
            data_name = data_name.split(".")[0]
        out = os.path.join(self.path, dataset).strip("\\").strip("/")
        arcpy.FeatureClassToFeatureClass_conversion(
            in_data_path, out, data_name)
        # Easily access data paths by fc name
        setattr(self, data_name.lower(),
                os.path.join(self.path, dataset, data_name))
        return

    def add_many(self, data_mapping={}, data_list=[], dataset=""):
        """Adds a list or dict of input feature classes.
        Args:
            data_mapping (dict): dictionary of {data_name: data_path}
            data_list (list): list of data paths to import
            dataset (str): destination dataset for imported data
        """
        if data_mapping:
            for k, v in data_mapping.items():
                self.add(v, k)
        if data_list:
            for fc_path in data_list:
                self.add(fc_path, dataset=dataset)
        return

    def load_queued_data(self):
        """Alias of 'add_many' for importing all data in the data_queue."""
        # Remove path from queue
        while self.data_queue.qsize() > 0:
            self.add(self.data_queue.get(), "", dataset=self.default_queue_ds)
        return

    # Debilitatingly slow
    '''
    def add_table(self, table_path, table_name="", where=""):
        if not table_name:
            table_name = os.path.basename(table_path)
        if "sde" in table_name.lower():
            table_name = table_name.split(".")[-1]
        elif "." in table_name:
            table_name = table_name.split(".")[0]
        arcpy.TableToGeodatabase_conversion(table_path, self.path)#, table_name)
        return
    '''

def df2tbl(df, out_path):
    # Convert dataframe to array
    a = np.array(np.rec.fromrecords(df.values))
    # Add field names to array
    a.dtype.names = tuple(df.columns.tolist())
    # Sort of surprised ESRI thought of this
    arcpy.da.NumPyArrayToTable(a, out_path)
    # ...and of course we have to call this...
    arcpy.RefreshCatalog(out_path)
    return


def domains2df(workspace):
    """Converts all domains into a dict of dataframes."""
    domain_obj = arcpy.da.ListDomains(workspace)
    domdict = {
        d.name: pd.DataFrame.from_dict(d.codedValues, orient="index").sort()
        for d in domain_obj
        }
    for key in domdict:
        domdict[key].reset_index(inplace=True)
        domdict[key].columns = ["Key", "Value"]
    return domdict


def domain2tbl(workspace, domain, output):
    domdict = domains2df(workspace)
    df2tbl(domdict[domain], output)
    return





class DataFramesWrapper(object):
    """Container for dataframes that is index-able by name and index."""
    def __init__(self, mxd):
        self.mxd = mxd

    @property
    def _dict(self):
        return OrderedDict([(df.name, df) for df
                            in arcpy.mapping.ListDataFrames(self.mxd)])

    @property
    def _list(self):
        return self._dict.values()

    def __getitem__(self, index):
        if type(index) is int:
            return self._list[index]
        return self._dict[index]

    def __iter__(self):
        """All dataframe objects."""
        return self._dict.itervalues()

    def __str__(self):
        return str(self._dict)

    def __repr__(self):
        return str(self._dict)


class Map(object):
    def __init__(self):
        try:
            self.mxd = MXD
        except:  #
            self.mxd = None

    @property
    def dataframes(self):
        return DataFramesWrapper(MXD)

    @property
    def count_dataframes(self):
        return len(self.dataframes._list)

    @property
    def df_layers(self):
        return OrderedDict([(df.name, arcpy.mapping.ListLayers(df)) for df
                            in self.dataframes])

    @property
    def layers(self):
        all_lyrs = []
        for lyr_list in self.df_layers.values():
            all_lyrs.extend(lyr_list)
        return {lyr.name: lyr for lyr in all_lyrs}

    @property
    def layer_names(self):
        return self.layers.keys()

    def as_object(self, layer_name):
        """Returns the input layer name as an object.
        Args:
            layer_name (str): name of layer
        Use:
            city = m.as_object("City Limits")
        """
        return self.layers[layer_name]

    def rename_layer(self, old_name, new_name, dataframe=0):
        self.layers[old_name].name = new_name
        self.refresh()
        return

    def refresh(self):
        arcpy.RefreshTOC()
        arcpy.RefreshActiveView()
        return

    def add_group_lyr(self, name, dataframe=0):
        group_lyr = arcpy.mapping.Layer(NEW_GROUP_LAYER)
        arcpy.mapping.AddLayer(self.dataframes[dataframe], group_lyr, "TOP")
        self.rename_layer("New Group Layer", name)
        self.refresh()
        return

    def toggle_on(self, layer_name="*"):
        """Toggles the input or all ("*") layer's visibility to on."""
        if layer_name != "*":
            self.layers[layer_name].visible = True
        else:
            for lyr in self.layers.values():
                lyr.visible = True
        self.refresh()
        return

    def toggle_off(self, layer_name="*"):
        """Toggles the input or all ("*") layer's visibility to off."""
        if layer_name != "*":
            self.layers[layer_name].visible = False
        else:
            for lyr in self.layers.values():
                lyr.visible = False
        self.refresh()
        return






class TableOfContents(object):
    """Table of Contents Object."""
    def __init__(self, mxd="CURRENT"):
        self.mxd_name = mxd
        self.mxd = None
        if self.mxd_name:
            self.set_mxd(self.mxd_name)

    def set_mxd(self, mxd):
        self.mxd_name = mxd
        self.mxd = arcpy.mapping.MapDocument(self.mxd_name)

    def as_featurelyr(self, layer_name):
        """Gets a layer as a feature layer (e.g. make selections on it)."""
        flyr_name = layer_name + "_fclyr"
        arcpy.MakeFeatureLayer_management(self[layer_name], flyr_name)
        return flyr_name

    @property
    def dataframes(self):
        return arcpy.mapping.ListDataFrames(self.mxd)

    @property
    def contents(self):
        cont = {lyr.name: lyr for lyr in arcpy.mapping.ListLayers(self.mxd)}
        cont.update({tbl.name: tbl for tbl in
                     arcpy.mapping.ListTableViews(self.mxd)})
        return cont

    @property
    def features_selected(self):  # TODO: assert actually selected not total
        sel = {}
        for lyr in self.contents.values():
            d = {lyr.name: int(arcpy.GetCount_management(lyr).getOutput(0))}
            sel.update(d)
        return sel

    def add_fc(self, fc_path, df_idx=0, loc="TOP"):
        """Wraps the rediculous process of adding data to an mxd"""
        new_lyr = arcpy.mapping.Layer(fc_path)
        arcpy.mapping.AddLayer(self.dataframes[df_idx], new_lyr, loc)
        return

    def remove(self, layer_name):
        """Removes layer from TOC by name."""
        for df in self.dataframes:
            try:
                arcpy.mapping.RemoveLayer(df, TOC.contents[layer_name])
            except:
                pass
        return

    def __getitem__(self, key):
        """Support dict-style item getting."""
        return self.contents[key]

if is_active():
    TOC = TableOfContents()
else:
    TOC = TableOfContents(None)


# =============================================================================
# LOCKS

def get_locks(gdb):
    """Generates a list of current locks in a gdb."""
    # TODO: change to `glob(os.path.join(gdb, "*.lock"))`
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


def unc_path(drive_path, unc_path):
    """Replaces a mapped network drive with a UNC path.
    Example:
        >>> unc_path('I:/workspace', r'\\cityfiles\stuff')
        '\\\\cityfiles\\stuff\\workspace'
    """
    drive_path = drive_path.replace("/", "\\")
    drive = os.path.splitdrive(drive_path)[0]
    p = Popen("net use", stdout=PIPE, creationflags=0x08000000)
    raw_result = p.communicate()[0]
    result = re.findall("{}(.*)\r".format(drive), raw_result)[0]
    unc = result.strip().split(" ")[0]
    return drive_path.replace(drive, unc)


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


def field_value_set(fc, field):
    s = set()
    with arcpy.da.SearchCursor(fc, field) as cur:
        for row in cur:
            s.add(row[0])
    return s


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


def oid_by_regex(fc, regex, field, oid_field="OBJECTID"):
    """Yields record oids where field value matches regex."""
    with arcpy.da.SearchCursor(fc, [oid_field, field]) as cur:
        for row in cur:
            if row[1] and re.findall(regex, row[1]):
                yield row[0]


def layer_by_regex(regex):
    """Returns the full name of a layer based on a substring or regex."""
    for layer in TOC.contents.keys():
        if re.findall("(?i){}".format(regex), layer):
            return layer


def regex_selection(fc, regex, field, id_field="OBJECTID"):
    """For when LIKE statements just don't cut the '(?i)mustard'."""
    ids = list(oid_by_regex(fc, regex, field, id_field))
    if not ids:
        raise IOError("Nothing found")
    in_qry = "{} IN ({})".format(id_field, ', '.join([str(i) for i in ids]))
    arcpy.SelectLayerByAttribute_management(fc, where_clause=in_qry)
    return


def field_by_regex(fc, field_regex, escape_tables=True):
    """Returns a list of field names matching a regular expression."""
    for f in arcpy.Describe(fc).fields:
        if escape_tables:
            field_regex = field_regex.replace("$.", "\\$\\.")
        if re.findall(field_regex, f.name):
            yield f.name


# =============================================================================
# QUERIES

def like_list(field, values, case="", condition="OR"):
    """Make a `<field> LIKE '%value%'` string for list of values.
    Args:
        field (str): field to use in LIKE statement; may need to be quoted
        values (iterable): values to convert to LIKE query
        condition (str): 'AND' or 'OR' (default 'OR')
        case (str): optionally convert values to title, upper, or lower
    Returns joined string.
    Usage:
        >>> like_list('"Subdivision"', ["Ranch", "Apple"], case="upper")
        'Subdivision" LIKE \'%RANCH%\' OR "Subdivision" LIKE \'%APPLE%\'"'
    """
    cond = " {} ".format(condition)
    if case.lower() == 'title':
        values = [v.title() for v in values]
    elif case.lower() == 'upper':
        values = [v.upper() for v in values]
    elif case.lower() == 'lower':
        values = [v.lower() for v in values]
    q = cond.join(["{} LIKE '%{}%'".format(field, v) for v in values])
    return q


# =============================================================================
# FIELD MAPS
# Note: a field map is a string describing a field and its merge rules
# Note: a field mapping is a list of field maps joined by ';'
# TODO: remove?
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
'''

# TODO: 'spatial join' that copies a field from the selected to the
#  intersecting features


# =============================================================================
# WRAPPERS
# Wrappers are particularly engineered for use in ArcMaps' Python Window

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


class GDBPkg(object):
    def __init__(self, out_location, gdb_name):
        """Create a template for a file geodatabase and make all at once."""
        self.out_location = out_location
        self.name = gdb_name
        if not gdb_name.endswith(".gdb"):
            self.name = gdb_name + ".gdb"
        self.contents = []
        self.datasets = []

        # Validate
        if not os.path.exists(self.out_location):
            raise IOError("Out location does not exist")
        if self.exists:
            raise IOError("GDB already exists")

    @property
    def path(self):
        """Output path for staged GDB."""
        return os.path.join(self.out_location, self.name)

    @property
    def exists(self):
        if os.path.exists(self.path):
            return True
        return False

    def add_feature(self, out_name, feature_path, dataset=""):
        """Stages a feature class for import."""
        self.contents.append([out_name, feature_path, dataset])
        return

    def add_dataset(self, name, refsys=0):
        """Stages a feature dataset for creation."""
        self.datasets.append([name, refsys])
        return

    def make(self):
        """Create the staged GDB."""
        # Create GDB
        arcpy.CreateFileGDB_management(self.out_location, self.name)

        # Create Feature Datasets
        for ds_name, refsys in self.datasets:
            arcpy.CreateFeatureDataset_management(self.path, ds_name, refsys)

        # Import Feature Classes
        for fc_name, f_path, dataset in self.contents:
            if dataset:
                if dataset not in [ds[0] for ds in self.datasets]:
                    raise IOError("{} not a dataset".format(dataset))
                arcpy.FeatureClassToFeatureClass_conversion(
                    f_path, os.path.join(self.path, dataset), fc_name)
            else:
                arcpy.FeatureClassToFeatureClass_conversion(
                    f_path, self.path, fc_name)
        return


class QueryFile(object):
    """Wraps RawConfigParser to make accessing stored queries easy."""
    def __init__(self, path):
        self.path = path
        self._cfg = RawConfigParser()
        self._cfg.read(self.path)

    def get(self, section, option):
        """Gets the option from the section in the file."""
        if option.lower() == "all":
            all_qs = ["({})".format(self._cfg.get(section, opt))
                      for opt in self._cfg.options(section)]
            q = " OR ".join(all_qs)
        else:
            q = self._cfg.get(section, option)
        return q.replace("\n", " ")


# Source:
# https://blogs.esri.com/esri/arcgis/2013/04/23/updating-arcgis-com-hosted-feature-services-with-python/
class Service(object):
    def __init__(self, mxd_file, host="My Hosted Services", con="",
                 service_type="FeatureServer", enable_caching=False,
                 allow_overwrite=True, capabilities=["Query"]):
        """Uploads an MXD as a Web Service."""
        self.mxd = arcpy.mapping.MapDocument(mxd_file)
        if self.mxd.title == "":
            raise IOError("MXD Title (metadata) cannot be blank")

        self.host = host

        if not con:
            self.con = self.host.upper().replace(" ", "_")
        self.sdd = os.path.abspath("{}.sddraft".format(self.mxd.title))
        self.sd = os.path.abspath("{}.sd".format(self.mxd.title))
        self.analysis = arcpy.mapping.CreateMapSDDraft(
            self.mxd, self.sdd, self.mxd.title, self.con)

        if self.analysis["errors"]:
            raise Exception(self.analysis["errors"])

        # DOM Editing
        self.doc = DOM.parse(self.sdd)
        self._set_service_type(service_type)
        self._set_caching(enable_caching)
        self._set_web_capabilities(capabilities)
        self._set_overwrite(allow_overwrite)

    def update_draft(self):
        with open(self.sdd, "w") as f:
            self.doc.writexml(f)
        return

    def _set_caching(self, enable_caching):
        cache = str(enable_caching).lower()
        conf = 'ConfigurationProperties'
        configProps = self.doc.getElementsByTagName(conf)[0]
        propArray = configProps.firstChild
        propSets = propArray.childNodes
        for propSet in propSets:
            keyValues = propSet.childNodes
            for keyValue in keyValues:
                if keyValue.tagName == 'Key':
                    if keyValue.firstChild.data == "isCached":
                        keyValue.nextSibling.firstChild.data = cache
        return

    def _set_service_type(self, service_type):
        typeNames = self.doc.getElementsByTagName('TypeName')
        for typeName in typeNames:
            if typeName.firstChild.data == "MapServer":
                typeName.firstChild.data = service_type
        return

    def _set_web_capabilities(self, capabilities):
        """Sets the web capabilities.
        Args:
            capabilities (list): list of capabilities
        """
        capability = ",".join(capabilities)
        configProps = self.doc.getElementsByTagName('Info')[0]
        propSets = configProps.firstChild.childNodes
        for propSet in propSets:
            keyValues = propSet.childNodes
            for keyValue in keyValues:
                if keyValue.tagName == 'Key':
                    if keyValue.firstChild.data == "WebCapabilities":
                        keyValue.nextSibling.firstChild.data = capability
        return

    def _set_overwrite(self, overwrite):
        replace = "esriServiceDefinitionType_Replacement"
        tagsType = self.doc.getElementsByTagName('Type')
        for tagType in tagsType:
            if tagType.parentNode.tagName == 'SVCManifest':
                if tagType.hasChildNodes():
                    tagType.firstChild.data = replace

        tagsState = self.doc.getElementsByTagName('State')
        for tagState in tagsState:
            if tagState.parentNode.tagName == 'SVCManifest':
                if tagState.hasChildNodes():
                    tagState.firstChild.data = "esriSDState_Published"
        return

    def upload(self):
        self.update_draft()
        arcpy.StageService_server(self.sdd, self.sd)
        arcpy.UploadServiceDefinition_server(
            self.sd, self.host, self.mxd.title,
            "", "", "", "", "OVERRIDE_DEFINITION",
            "SHARE_ONLINE", "PUBLIC", "SHARE_ORGANIZATION")
        return


def get_props(doc):
    configProps = doc.getElementsByTagName('Info')[0]
    propSets = configProps.firstChild.childNodes
    for propSet in propSets:
        keyValues = propSet.childNodes
        for keyValue in keyValues:
            if keyValue.tagName == 'Key':
                if keyValue.firstChild.data == "WebCapabilities":
                    return keyValue.nextSibling.firstChild.data.split(",")
