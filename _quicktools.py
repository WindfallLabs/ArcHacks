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

import os
import re
import sys
from datetime import datetime
from glob import glob
# from string import ascii_uppercase

# import pandas as pd

import arcpy
import pybars


'''
def get_layers():
    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    for f in arcpy.mapping.ListLayers(df):
        yield f.name
'''

# =============================================================================
# GLOBALS

DERRIVED = "Derrived"

REQUIRED = {True: "Required", False: "Optional"}

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

# Open metadata template files
_compiler = pybars.Compiler()

# Directory this library lives in
_libdir = os.path.dirname(__file__)

# Tool metadata
_tmdp = os.path.join(_libdir, "tool_metadata_template.xml")
with open(_tmdp, "r") as f:
    metadata_template = _compiler.compile(unicode(f.read()))

# Parameter metadata
_pmdp = os.path.join(_libdir, "param_metadata_template.xml")
with open(_pmdp, "r") as f:
    #param_metadata_template = unicode(f.read())
    param_metadata_template = _compiler.compile(unicode(f.read()))


class _Toolbox(object):
    """Basic Toolbox Object."""
    label = ""
    alias = ""

    @property
    def tools(cls):
        """Dynamic list of tools in Python Toolbox script (.pyt)."""
        # This strange bit of code finds all subclasses of archacks.Tool
        #  and adds them into the Toolbox. Very convenient!
        return sys.modules["archacks"].Tool.__subclasses__()


def make_toolbox(name):
    """Creates local Toolbox object. Must be saved to variable: 'Toolbox'.
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

class Tool(object):
    """Base Tool Class."""
    def __init__(self, toolbox_name=None):
        self.description = "This tool does not have a description."
        self.is_licensed = True
        self.validate = False
        self.params = []
        self.toolbox_name = toolbox_name
        # Metadata attributes
        self.usage = "No useage set."
        self.author = "No author set."
        self.credits = "No credits set."
        self.license = "No license set."
        self.keywords = ["Tool"]
        self.__name__ = re.sub("\W", "", str(self.__class__).split(".")[-1])

    def _get_param_xml(self):
        """Writes XML metadata for each parameter."""
        if len(self.params) > 0:
            xmls = []
            for param in self.params:
                xmls.append(
                    param_metadata_template({
                        "param_name": param.name,
                        "param_label": param.displayName,
                        "param_is_required": param.is_required,
                        "param_direction": param.direction,
                        "param_type": param.datatype,
                        "param_desc": param.description}))
            xml = unicode("".join(xmls))
            xml = xml.replace("&lt;", "<").replace("&gt;", ">")
            return xml
        return

    def write_metadata(self, output_xml):
        kw_xml = u"<keyword>{}</keyword>"
        metadata = metadata_template({
            "date": datetime.now().strftime("%Y%m%d"),
            "time": datetime.now().strftime("%H%M%S00"),
            "year": datetime.now().strftime("%Y"),
            "tool_name": self.__name__,
            "tool_label": self.label,
            "parameters_xml": self._get_param_xml(),
            "summary": self.description,
            "usage": self.usage,
            "keywords_xml": u"".join(
                [kw_xml.format(k) for k in self.keywords]),
            "author": self.author,
            "credits": self.credits
            }
        )
        metadata = metadata.replace("&lt;", "<").replace("&gt;", ">")
        metadata = metadata.replace("&quot;", '"')
        with open(output_xml, "w") as f:
            f.write(metadata)
        return

    def make(new_tool_self):
        """Initializes a subclass of the base Tool class."""
        # NOTE: must be executed in subclass's __init__
        Tool.__init__(new_tool_self)
        return

    ''' # TODO: get parameter access from source code
    @property
    def param_values(self):
        return [p.valueAsText for p in None]
    '''

    '''
    @property
    def label(self):
        """Tool label (adds spaces to class name)."""
        name = re.sub("\W", "", str(type(self)).split(".")[1])
        for letter in name:
            if letter in ascii_uppercase:
                name = name.replace(letter, " {}".format(letter))
        name = re.sub(" {2,}", " ", name)
        return name.strip()
    '''

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
        # TODO: this version does not currently support arcpy Messages
        pass

    def execute(self, parameters, messages):
        """Controls the execution of the 'main' function."""
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
# Tool Parameter Help
'''
https://pro.arcgis.com/en/pro-app/arcpy/geoprocessing_and_python/defining-parameter-data-types-in-a-python-toolbox.htm
'''


class _Params(object):
    def __init__(self):
        self._default_description = "No description for this parameter."

    def _make_param(self, label, is_required=True, description=""):
        """Tool Parameter."""
        REQUIRED = {True: "required", False: "Optional"}
        param = arcpy.Parameter(
            displayName=label,
            # Name is derrived from label: lowercase and change spaces to '_'
            name=re.sub("\W", "", label.lower().replace(" ", "_")),
            datatype="GPString",
            parameterType=REQUIRED[is_required],
            direction="Input")
        setattr(param, "is_required", is_required)
        # Set description to default if none given
        if not description:
            description = self._default_description
        # Create a new attribute on the parameter object
        setattr(param, "description", description)
        return param

    def folder(self, label, is_required=True, default_value=None,
               description=""):
        """Accepts a directory / folder path string."""
        param = self._make_param(label, is_required, description)
        param.datatype = "DEFolder"
        param.value = default_value
        return param

    def file(self, label, is_required=True, default_value=None,
             description=""):
        """Accepts a file path string."""
        param = self._make_param(label, is_required, description)
        param.datatype = "DEFile"
        param.value = default_value
        return param

    def string(self, label, is_required=True, default_value=None,
               description=""):
        """Accepts an input string."""
        param = self._make_param(label, is_required, description)
        # Note: ESRI coded their own value validation
        param.value = default_value
        return param

    def double(self, label, is_required=True, default_value=None,
               description=""):
        """Accepts an input float/double."""
        param = self._make_param(label, is_required, description)
        param.datatype = "GPDouble"
        try:
            param.value = default_value
        except ValueError:
            pass
        return param

    def checkbox(self, label, is_required=True, default_value="false",
                 description=""):
        """Creates a single boolean yes/no checkbox."""
        param = self._make_param(label, is_required, description)
        param.datatype = "GPBoolean"
        param.value = default_value
        return param

    def valuelist(self, label, name, columns, values, is_required=True,
                  description=""):
        """ValueTable Tool Parameter."""
        param = self._make_param(label, is_required, description)
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
