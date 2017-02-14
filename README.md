# ArcHacks (WIP)

## Purpose
This work-in-progress suite of wrappers and utilities was primarily created for
working with ESRI ArcMap/Catalog on a virtual machine (or any painfully slow computer).  
Further, this package is engineered to prevent lag by parameter validation when
using the Python Window interactively.  

## Installation
Unzip this repository and place in your Python's `site-packages` folder.  

## Brief Overview of Current Features
* Integration with Pandas
* Makes use of the `in_memory` workspace and treats it as a Python object  
* Get field names by regular expression  
* Sane field-mapping handlers  


## Brief List of Planned Features
* Use osgeo as faster alternative to common arcpy bottlenecks  
* MXD and PDF metadata handler (and append MXD metadata to PDF on export)  
* Some kind of testing suite
