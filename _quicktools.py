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

REQUIRED = "Required"
OPTIONAL = "Optional"
DERRIVED = "Derrived"

INPUT = "Input"


# =============================================================================
# BASE TOOL CLASS

#TODO: set main
class Tool(object):
    """Base Tool Class."""
    def __init__(self):
        self.label = "LABEL"
        self.description = "DESC"
        self.is_licensed = True
        self.validate = False
        self.main = None
        self.params = []

    def subclass(new_tool_self):
        """Initializes a subclass of the base Tool class."""
        # NOTE: look, we know about super and such, but I argue this for ease
        Tool.__init__(new_tool_self)

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
        self.main(parameters)
        return


# =============================================================================
# INPUTS -- wrappers for arcpy.Parameter()
# These sort of behave like classes hence the TitleCase
# TODO: move to arcpy.tools.inputs ?

def String(label, name, required=True):
    """String Tool Parameter."""
    if required:
        required = REQUIRED
    else:
        required = OPTIONAL
    param = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype="GPString",
        parameterType="Required",
        direction=INPUT)
    return param


def Double(label, name, required=True):
    """Double (number) Tool Parameter."""
    if required:
        required = REQUIRED
    else:
        required = OPTIONAL
    param = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype="GPDouble",
        parameterType="Required",
        direction=INPUT)
    return param


def ValueList(label, name, columns, values, required=True):
    """ValueTable Tool Parameter."""
    if required:
        required = REQUIRED
    else:
        required = OPTIONAL
    param = arcpy.Parameter(
        displayName=label,
        name=name,
        datatype="GPValueTable",
        parameterType=required,
        direction=INPUT)
    param.columns = columns
    param.filters[0].type = "ValueList"
    param.values = []
    param.filters[0].list = values
    return param


# =============================================================================
# EXAMPLES

# Layout of a (non-functional) tool using archacks
'''
class TestTool(archacks.Tool):
    def __init__(self):
        archacks.Tool.subclass(self)
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
