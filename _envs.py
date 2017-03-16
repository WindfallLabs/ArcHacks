# -*- coding: utf-8 -*-
"""
Experiments
"""

import os
import re

import arcpy

#from archacks import is_active, TOC

class Env(object):
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
        arcpy.env.workspace = self.path

    @property
    def path(self):
        """Read-only"""
        return "in_memory"

    def add_layer(self, fc, rename=None, limit_fields=None, hide_old=True):
        prefix = "mem_{}"
        #fc_name = os.path.basename(fc).split(".")[0]
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
        prefix = "mem_{}"
        if rename:
            out_name = prefix.format(rename)
        else:
            name = arcpy.Describe(tbl).name
            if len(re.findall("\.", name)) > 1:
                name = name.split(".")[-1]
            out_name = prefix.format(name)
        arcpy.TableToTable_conversion(tbl, "in_memory", out_name)
        return

    def remove(self, fc):
        pass

    '''
    def join_all(self, fc, uid, to_field=None):
        """Attempts to join a feature class with every table in the TOC."""
        if arcpy.Describe(fc).path != "in_memory":
            raise IOError("Cannot permanently join data out of 'in_memory'")
        if not to_field:
            to_field = uid
        #refresh()
        all_tbls = [lyr for lyr in TOC.contents.values()
                    if type(lyr).__name__ == "TableView"]
        warnings = []
        for tbl in all_tbls:
            fields = [f.name for f in arcpy.Describe(tbl).fields
                      if f.name != uid]
            try:
                arcpy.JoinField_management(fc, uid, tbl, to_field, fields)
            except:
                warnings.append(tbl.name)
        if warnings:
            print("Could not join with: {}".format(warnings))
        return
    '''
