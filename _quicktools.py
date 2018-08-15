#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Source Name:   devserv_tools.pyt
Version:       ArcGIS Pro / 10.3
Author:        Garin Wally
Description:   Python tools to assist Development Services at the City of
               Missoula, MT.

Working!
* Supports ugly subclassing of base Tool class
* Supports importing of tools: `from mytools import DoStuff` and add that to
your toolbox
* Started making wrappers for arcpy.Parameter

"""

import re
import sys
from string import ascii_uppercase

import pandas as pd

import arcpy


'''
def get_layers():
    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    for f in arcpy.mapping.ListLayers(df):
        yield f.name
'''

# =============================================================================
# GLOBALS

#REQUIRED = "Required"
#OPTIONAL = "Optional"
DERRIVED = "Derrived"

REQUIRED = {True: "required", False: "Optional"}

INPUT = "Input"


tool_template = """
class ToolTemplate(archacks.Tool):
    def __init__(self):
        self.make()
        self.params = [
            archacks.String("user", "Contact Name", True, user),
            archacks.String("board", "Board Acronym", False)]

    def main(self):
        pass
    """


class _Toolbox(object):
    """Basic Toolbox Object."""
    label = ""
    alias = ""
    #name = ""

    @property
    def tools(cls):
        """Dynamic list of tools in Python Toolbox script (.pyt)."""
        return sys.modules["archacks"].Tool.__subclasses__()


def make_toolbox(name):
    """Creates local copy of Toolbox object. Output must be 'Toolbox'.
    Args:
        name (str): name of toolbox (doesn't display in catalog)
    Use:
        Toolbox = archacks.make_toolbox('My Tools')
    """
    # Don't instantiate
    toolbox = _Toolbox
    # Set parameters of class, not instance
    toolbox.label = name
    toolbox.alias = name
    return toolbox


# =============================================================================
# BASE TOOL CLASS

#TODO: set main
class Tool(object):
    """Base Tool Class."""
    def __init__(self):
        self.description = "DESC"
        self.is_licensed = True
        self.validate = False
        self.params = []

    def make(new_tool_self):
        """Initializes a subclass of the base Tool class."""
        # NOTE: must be executed in subclass's __init__
        Tool.__init__(new_tool_self)
        return

    @property
    def label(self):
        """Tool label (adds spaces to class name)."""
        name = re.sub("\W", "", str(type(self)).split(".")[1])
        for letter in name:
            if letter in ascii_uppercase:
                name = name.replace(letter, " {}".format(letter))
        name = re.sub(" {2,}", " ", name)
        return name.strip()

    def getParameterInfo(self):
        return self.params

    def isLicensed(self):
        return self.is_licensed

    def updateParameter(self, parameters):
        if self.validate:
            pass
        else:
            pass

    def updateMessages(self, parameters):
        if self.validate:
            pass
        else:
            pass

    def execute(self, parameters, messages):
        # Add messages for each parameter
        [arcpy.AddMessage("Param: {}".format(p.valueAsText))
         for p in parameters]
        # Execute
        if not hasattr(self, "main") or self.main is None:
            raise AttributeError("Tool does not have 'main' method.")
        self.main(parameters)
        return


# =============================================================================
# INPUTS -- wrappers for arcpy.Parameter()
# These sort of behave like classes hence the TitleCase
# TODO: move to arcpy.tools.inputs ?

from types import MethodType

class _Params(object):
    def __init__(self):
        pass

    def _make_param(self, label, required=True):
        """Tool Parameter."""
        REQUIRED = {True: "required", False: "Optional"}
        param = arcpy.Parameter(
            displayName=label,
            # Name is derrived from label: lowercase and change spaces to '_'
            name=re.sub("\W", "", label.lower().replace(" ", "_")),
            datatype="GPString",
            parameterType=REQUIRED[required],
            direction="Input")
        setattr(param, "is_required", required)
        return param

    def string(self, label, required=True, default_value=None):
        param = self._make_param(label, required)
        # Note: ESRI coded their own value validation
        param.value = default_value
        return param

    def double(self, label, required=True, default_value=None):
        param = self._make_param(label, required)
        param.datatype = "GPDouble"
        try:
            param.value = default_value
        except ValueError:
            pass
        return param

    def valuelist(self, label, name, columns, values, required=True):
        """ValueTable Tool Parameter."""
        param = self._make_param(label, required)
        param.datatype = "GPValueTable"
        param.columns = columns
        param.filters[0].type = "ValueList"
        param.values = []
        param.filters[0].list = values
        return param


params = _Params()

assert params.string("My String", True, "Garin").value == "Garin"
assert params.string("My String", True, None).value is None
assert params.string("My String", True, 100).value == "100"
assert params.string("My String", True, None).is_required is True
assert params.double("My Dub", False, 0).is_required is False
assert params.double("My Dub", False, 0).value == 0.0

'''
def String(label, required=True, default_value=""):
    """String Tool Parameter."""
    param = arcpy.Parameter(
        displayName=label,
        # Name is derrived from label: lowercase and change spaces to '_'
        name=label.lower().replace(" ", "_"),
        datatype="GPString",
        parameterType=REQUIRED[required],
        direction=INPUT)
    if default_value:
        param.value = default_value
    return param


def Double(label, name, required=True):
    """Double (number) Tool Parameter."""
    param = arcpy.Parameter(
        displayName=label,
        name=label.lower().replace(" ", "_"),
        datatype="GPDouble",
        parameterType=REQUIRED[required],
        direction=INPUT)
    return param


def ValueList(label, name, columns, values, required=True):
    """ValueTable Tool Parameter."""
    param = arcpy.Parameter(
        displayName=label,
        name=label.lower().replace(" ", "_"),
        datatype="GPValueTable",
        parameterType=REQUIRED[required],
        direction=INPUT)
    param.columns = columns
    param.filters[0].type = "ValueList"
    param.values = []
    param.filters[0].list = values
    return param
'''

# =============================================================================
# EXAMPLES

# Layout of a (non-functional) tool using archacks
'''
class TestTool(archacks.Tool):
    def __init__(self):
        self.make()
        self.label = "TestTool"
        self.params = [
            # Param0 -- buffer distance
            archacks.Double("Buffer Distance (ft)", "distance"),

            # Param1 -- List of Fields
            archacks.ValueList(
                "Label!", "vtable",
                [['GPString', 'Names'], ['GPString', 'Rename (optional)']],
                ["V1", "V2", "V3"])
            ]
'''

# Layout of "fully" coded, functional tool
'''
class ExportNeighborsToExcel(object):
    """
    Selects the neighboring parcels to a selected parcel by distance.
    Uses the 'City Parcels'.
    """
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Export Neighbors to Excel"
        self.description = ("Uses the 'City Parcels' layer to select other "
                            "parcels within a distance of a selected parcel.")
        self.canRunInBackground = False
        self.helpContext = 50000001  # ???

    def getParameterInfo(self):
        """Define parameter definitions"""

        # Buffer Distance
        param0 = arcpy.Parameter(displayName="Buffer Distance (ft)",
                                 name="distance",
                                 datatype="GPDouble",
                                 parameterType="Required",
                                 direction="Input")

        # List of Fields
        param1 = arcpy.Parameter(displayName="Fields",
                                 name="fields",
                                 datatype="GPValueTable",
                                 parameterType="Required",
                                 direction="Input")
        param1.columns = [['GPString', 'Fields to Include'],
                          ['GPString', 'Rename (optional)']]
        param1.filters[0].type = 'ValueList'
        param1.values = []
        if "City Parcels" in get_layers():
            param1.filters[0].list = [f.name for f
                                      in arcpy.ListFields("City Parcels")]
        else:
            param1.filters[0].list = []

        # Output Name
        excel_title = ("Output Excel Filename (don't include '.xlsx')\n"
                       "Will be saved to DevServices/ArcExlorer/user_data/<your name>/")
        param2 = arcpy.Parameter(displayName=excel_title,
                                 name="out_name",
                                 datatype="GPString",
                                 parameterType="Required",
                                 direction="Input")

        # Return
        params = [param0, param1, param2]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        pass

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        if "City Parcels" not in get_layers():
            parameters[1].setWarningMessage(
                "ERROR: 'City Parcels' layer not found")

        if parameters[0].altered:
            pass
        if parameters[2].altered:
            pass
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        if (any([p.hasWarning() for p in parameters])
            or any([p.value is None for p in parameters])):
            raise IOError("No 'City Parcels' layer")

        # Get inputs
        dist = "{} Feet".format(parameters[0].valueAsText)
        outputDir = parameters[1].valueAsText
        out_name = parameters[2].valueAsText
        fields = [f[0] for f in parameters[1].values]
        fnames = [f[1] for f in parameters[1].values]
        out_path = r"\\cityfiles\DEVServices\ArcExplorer\user_data\{}"
        out_file = out_path.format("{}.xlsx".format(out_name))

        # Debugging
        #debug_out = "{}.txt".format(out_path.format(out_name))
        #debug = open(debug_out, "w")
        #debug.write(out_file + "\n")
        #debug.write(str(fields))
        #debug.write("\n")
        #debug.write(str(fnames))
        #debug.write("\n")

        # Select parcels surrounding the selected parcel
        arcpy.SelectLayerByLocation_management(
            in_layer="City Parcels", overlap_type="INTERSECT",
            select_features="City Parcels", search_distance=dist,
            selection_type="NEW_SELECTION")

        # Unselect right of way
        arcpy.SelectLayerByAttribute_management(
            in_layer_or_view="City Parcels",
            selection_type="REMOVE_FROM_SELECTION",
            where_clause=("County4.dbo.ParcelTable.Owner IS NULL AND "
                          "County4.dbo.ParcelTable.StateGeo IS NULL"))

        # Get record information from selected parcels as DataFrame
        frames = []
        with arcpy.da.SearchCursor("City Parcels", fields) as cur:
            for row in cur:
                row_df = pd.DataFrame(list(row)).T
                row_df.columns = fnames
                frames.append(row_df)
        df = pd.concat(frames)

        # Export dataframe as Excel
        #debug.write(str(df))
        df.to_excel(out_file, index=False)

        #debug.close()
        return
'''
