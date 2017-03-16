# -*- coding: utf-8 -*-
"""
_patches.py -- Monkey Patches for Arcpy objects.
"""

import types

import arcpy


def _join(self, pkey, fkey, tbl):
    arcpy.JoinField_management(self.name, pkey, tbl, fkey)
    return # arcpy.Describe(self).name


arcpy._mapping.Layer.join = types.MethodType(_join, arcpy._mapping.Layer)
