# -*- coding: utf-8 -*-
"""
_session.py -- ArcHacks Table Tools
Author: Garin Wally
License: MIT

These functions/classes are only for use within an ArcMap session though the
Python Window.
"""

import os

import arcpy
import pythonaddins

from _core import fc2fc, TOC


# =============================================================================
# GLOBALS

MXD = arcpy.mapping.MapDocument("CURRENT")


def env_switch(env="in_memory"):
    arcpy.env.workspace = env
    return


def refresh():
    arcpy.RefreshTOC()
    arcpy.RefreshActiveView()
    return


def add_all(source):
    """Adds all contents from a source geodatabase."""
    if ".gdb" not in source:
        raise AttributeError("Can only accept GDB workspaces")
    for workspaces, dfs, contents in arcpy.da.Walk(source):
        for content in contents:
            lyr_path = "{}\\{}".format(workspaces, content)
            try:
                lyr = arcpy.mapping.Layer(lyr_path)
                arcpy.mapping.AddLayer(TOC.dataframes[0], lyr)
            except ValueError:
                lyr = arcpy.mapping.TableView(lyr_path)
                arcpy.mapping.AddTableView(TOC.dataframes[0], lyr)
    refresh()
    return


def export_selected_lyr(out_path, where=None, limit_fields=None):
    """Shortcut for exporting the feature class selected in the TOC."""
    fc = pythonaddins.GetSelectedTOCLayerOrDataFrame()
    fc2fc(fc, out_path, where, limit_fields)
    return


# TODO: test
def apply_symbology(in_fc, src_symbology, hide_old=True):
    refresh()
    arcpy.ApplySymbologyFromLayer_management(in_fc, src_symbology)
    if hide_old:
        lyr = [f for f in TOC.contents.values() if f.name == src_symbology][0]
        lyr.visible = False
    refresh()
    return


def remove_lyr(rm_lyr):
    """Wrapper for arcpy.mapping.RemoveLayer()."""
    for df in TOC.dataframes:
        try:
            arcpy.mapping.RemoveLayer(df, TOC.contents[rm_lyr])
        except:
            pass
    return

'''
def remove(self):
    """Wrapper for arcpy.mapping.RemoveLayer()."""
    for df in TOC.dataframes:
        try:
            arcpy.mapping.RemoveLayer(df, TOC[self.name])
        except:
            pass
    return
'''
'''
def join_all(fc, uid, to_field=None):
        """Attempts to join a feature class with every table in the TOC."""
        if arcpy.Describe(fc).path != "in_memory":
            raise IOError("Cannot permanently join data out of 'in_memory'")
        if not to_field:
            to_field = uid
        TOC.refresh()
        all_tbls = [lyr for lyr in TOC.values()
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


class MemoryWorkspace(object):
    """MemoryWorkspace; not to be used in scripts."""
    def __init__(self):
        self.path = "in_memory"
        arcpy.env.workspace = self.path

    # def dump(self):
    # """Saves workspace to disk."""

    @property
    def layers(self):
        return arcpy.ListFeatureClasses()

    def add_layer(self, fc, rename=None, limit_fields=None, hide_old=True):
        prefix = "mem_{}"
        fc_name = os.path.basename(fc).split(".")[0]
        if rename:
            out_name = prefix.format(rename)
        else:
            out_name = prefix.format(fc_name.replace(" ", "_"))
        fc2fc(fc, "/".join([self.path, out_name]), limit_fields)
        # TODO: catch error if path is used
        apply_symbology(out_name, fc_name, hide_old)
        return

    def remove(self, fc):
        pass

    def join_all(self, fc, uid, to_field=None):
        """Attempts to join a feature class with every table in the TOC."""
        if arcpy.Describe(fc).path != "in_memory":
            raise IOError("Cannot permanently join data out of 'in_memory'")
        if not to_field:
            to_field = uid
        refresh()
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
