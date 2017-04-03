# ArcHacks (WIP)
Extensions and wrappers for ESRI's `arcpy` Python package (not included).  

## Purpose
This work-in-progress suite of wrappers and utilities was primarily created for
working with ESRI ArcMap/Catalog on a virtual machine (or any painfully slow computer).  
Further, this package is engineered to prevent lag when using the Python Window
interactively by skipping ESRI's built-in parameter validation.  
These tools can be used in ArcMap or in stand-alone scripts.  

The highlight of this package is in-memory processing using object-oriented data objects.  
This allows us, for instance, to wrap JOIN and SELECT operations as a methods
of the in-memory data like so:  

    import archacks
    # Instantiate the memory workspace
    mem = archacks.MemoryWorkspace()
    # Add the data; this method renames the data to "mem_<data>" by default  
    mem.add_layer("C:/workspace/parcels.shp")  
    # Get the data as a MemoryLayer (an object-oriented data object)  
    parcels = mem.get_memorylayer("mem_parcels")  
    # Add a table to memory
    mem.add_table("C:/workspace/OwnerInfo.csv")
    # Join parcel layer to OwnerInfo table  
    parcels.join("mem_OwnerInfo", "ParcelID", "StateGeo")  
    # Select by intersection with city_limits data object  
    # Assume we've done the same sequence of steps for a city limits layer
    parcels.selection.Intersect(city_limits)  
    # Make a selection using a query  
    parcels.selection.where('"Subdivision" LIKE \'APPLE%\'")  

Convenient, right?  

Then there's the problem of reordering and editing the schema of the attribute
table -- which ESRI calls a Field Mapping for some reason... ArcHacks makes this
easy by wrapping the nonsensical FieldMap and FieldMapping objects (which are
really just strings). Let's take our joined parcels-owner data from above and
limit the fields to only those we want in our output data:  

    # Get the field mapping/schema  
    schema = archacks.EZFieldMap(parcels)  
    # Set the new order of fields by index; by name is planned
    new_order = [0, 14, 15, 16, 17, 18, 20, 21, 22, 23]  
    schema.reorder(new_order, drop=True)  
    # Export the data using the new schema
    schema.export("parcel_owners.shp", "C:/workspace")  
    
Re-mapping the fields by name is planned, but not yet available. Get the current
order of the fields using the `.current_order` property. The export method supports
selections and only those selected features are exported with the new schema.  
    
    
## Installation
Unzip this repository and place in your Python's `site-packages` folder.  
e.g.  
`C:\Python27\ArcGIS10.3\Lib\site-packages\archacks`  

## Brief Overview of Current Features
* Integration with Pandas
* Makes use of the `in_memory` workspace and treats it as a Python object  
* Get field names by regular expression (available, but WIP)  
* Sane field-mapping handlers (see above)  
* Data as "MemoryLayer" objects  
* A Service object (available, but WIP)  


## Brief List of Planned Features
* Remap schema/field mapping by field name rather than just index  
* Use osgeo as faster alternative to common arcpy bottlenecks  
* MXD and PDF metadata handler (and append MXD metadata to PDF on export)  
* Some kind of testing suite  
* Documentation  
