# -*- coding: utf-8 -*-
"""
Misc ArcPy Addons
Author: Garin Wally
License: MIT

"""
import os
import re
import sys
from subprocess import Popen, PIPE
from xml.dom import minidom as DOM

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
    def features_selected(self): # TODO: assert actually selected not total
        sel = {}
        for lyr in self.contents.values():
            d = {lyr.name: int(arcpy.GetCount_management(lyr).getOutput(0))}
            sel.update(d)
        return sel

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
# FIELD MAPS
# Note: a field map is a string describing a field and its merge rules
# Note: a field mapping is a list of field maps joined by ';'
# TODO: remove?

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
