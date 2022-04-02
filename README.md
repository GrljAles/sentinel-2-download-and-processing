# Sentinel-2 data download and processing (spectral indices calculation)

Requires user to have an account at Copernicus SciHub, GDAL and its Python bindings.

The program is used to download Sentinel-2 imagery over selected area. It can download images for multiple dates in the past. It first queries SciHub for imagery xml that is parsed for data relevant for download e.g. filenames. Secondly it downloads selected images.

Second part of the program calculates spectral indices from S-2 spectral bands. If area of interest is large or overlaps multiple granule areas and multiple granules were downloaded for the same date, they are mosaicked by generating .vrt file.

EVI, NDMI, NDWI, and NDVI are calculated by default but additional functions for additional indices can be added to 
A1_sentinel2_products.py following the template of the existiong functions. Names of this additional indices must be added to parameters jsons, required by the script. Similarly the names can be removed from this json to skip the calculation.

Repo contains also scripts for registring newly added indices and publishing dates of newly calculated indices to the API that writes this information to database. Publishing of new dates is called automatically from main function while registring new priduct must be called before adding new indices.

Is a part of a larger system for processing, displaying and disseminaton of this type of data.