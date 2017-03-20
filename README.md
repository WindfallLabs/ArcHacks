# ArcHacks (WIP)

## Purpose
This work-in-progress suite of wrappers and utilities was primarily created for
working with ESRI ArcMap/Catalog on a virtual machine (or any painfully slow computer).  
Further, this package is engineered to prevent lag by parameter validation when
using the Python Window interactively, and to enable better in-memory processing.  

## Installation
Unzip this repository and place in your Python's `site-packages` folder.  
e.g.  
`C:\Python27\ArcGIS10.3\Lib\site-packages\archacks`  

## Brief Overview of Current Features
* Integration with Pandas
* Makes use of the `in_memory` workspace and treats it as a Python object  
* Get field names by regular expression  
* Sane field-mapping handlers with handy methods (see below)  
* Data as "MemoryLayer" objects  
* A Service object  


## Brief List of Planned Features
* Use osgeo as faster alternative to common arcpy bottlenecks  
* MXD and PDF metadata handler (and append MXD metadata to PDF on export)  
* Some kind of testing suite  
* Documentation  


## EZFieldMap example

    >>> import archacks
    >>> m = archacks.EZFieldMap("pop2016")  # Load a field mapping into 'm'
    >>> m.field_names  # Lists field names
    [u'GEOID10', u'Name', u'EstTotPop16', u'EstNewHU16', u'ward16',
     u'Shape_Length', u'Shape_Area', u'Scenario1', u'Scenario2', u'Acre',
     u'Scenario3', u'Scenario4', u'Sheet1$_GEOID10', u'Sheet1$_HU2016']
    >>> m.rename_by_split("$_")  # 'Sheet1$_HU2016' becomes 'HU2016'
    >>> m.current_order  # List of tuples of index, field name
    [(0, u'GEOID10'), (1, u'Name'), (2, u'EstTotPop16'), (3, u'EstNewHU16'),
     (4, u'ward16'), (5, u'Shape_Length'), (6, u'Shape_Area'), (7, u'Scenario1'),
     (8, u'Scenario2'), (9, u'Acre'), (10, u'Scenario3'), (11, u'Scenario4'),
     (12, u'GEOID10'), (13, u'HU2016')]
    >>> new = [0, 1, 3, 2, 13, 4, 5, 6, 7, 8, 9]  # new order of fields by index
    >>> m.reorder(new, True)  # True allows dropping fields
    >>> m.rename_field("Name", "NhoodName")
    >>> m.rename_field("HU2016", "EstTotHU16")
    >>> m.current_order
    [(0, u'GEOID10'), (1, u'NhoodName'), (2, u'EstNewHU16'), (3, u'EstTotPop16'),
     (4, u'EstTotHU16'), (5, u'ward16'), (6, u'Shape_Length'), (7, u'Shape_Area'),
     (8, u'Scenario1'), (9, u'Scenario2'), (10, u'Acre')]
    >>> new = [0, 3, 4, 2, 1, 5, 8, 9, 10, 6, 7]
    >>> m.reorder(new)
    >>> m.current_order
    [(0, u'GEOID10'), (1, u'EstTotPop16'), (2, u'EstTotHU16'), (3, u'EstNewHU16'),
     (4, u'NhoodName'), (5, u'ward16'), (6, u'Scenario1'), (7, u'Scenario2'),
     (8, u'Acre'), (9, u'Shape_Length'), (10, u'Shape_Area')]
    >>> loc = r'C:\projects\data\some.gdb\dataset'  # output location
    >>> m.export_fc("pop2016_1", loc)  # Export the mapping as a feature class

## MemoryLayer example

    >>> nhoods_path = r'Database Connections\gisrep.sde\gisrep.SDE.AdministrativeArea\gisrep.SDE.NH_Council_Boundaries'  
    >>> mains_path = r'Database Connections\gisrep.sde\gisrep.SDE.SanitarySewer\gisrep.SDE.ssGravityMain'  
    >>> parcel_path = r'Database Connections\gisrep.sde\gisrep.SDE.Parcels\gisrep.SDE.Parcels'  
    >>> owner_path = r'Database Connections\County4.sde\County4.dbo.View_OwnerAddress'  
    >>> forest_path = r'Database Connections\County4.sde\County4.dbo.AgForest'  
    
    # Create MemoryWorkspace and load data into memory  
    >>> mem = MemoryWorkspace()  
    >>> mem.add_layer(mains_path)  
    >>> mem.add_layer(nhoods_path)  
    >>> mem.add_layer(parcel_path)  
    >>> mem.add_table(owner_path)  
    >>> mem.add_table(forest_path)  
    >>> assert len(mem.contents) == 5  

    # Instantiate MemoryLayer objects  
    >>> mains = mem.get_memorylayer("mem_ssGravityMain")  
    >>> nhoods = mem.get_memorylayer("mem_NH_Council_Boundaries")  
    >>> parcels = mem.get_memorylayer("mem_Parcels")  

    # Test field map edits  
    >>> mains.fmap.reorder([0, 2, 5], True)  
    >>> mains.fmap.update()  
    >>> assert len(mains.fields) == 5  

    # Reduce parcels to intersection with nhoods & join with owners  
    >>> parcels.selection.Intersect(nhoods)  
    >>> parcels.fmap.update()  
    >>> assert parcels.feature_count == 25237  

    # Join parcels with tables in memory and unjoin  
    >>> parcels.join('mem_View_OwnerAddress', "ParcelID", "StateGeo")  
    >>> assert "City" in parcels.fields  
    >>> parcels.join('mem_AgForest', "PropertyID", "PropertyID")  
    >>> assert "ProdCommodity" in parcels.fields  
    >>> parcels.drop_join('mem_View_OwnerAddress')  
    >>> assert "City" not in parcels.fields  

