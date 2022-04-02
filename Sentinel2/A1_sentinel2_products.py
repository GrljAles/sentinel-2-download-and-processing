import os, sys
from osgeo import gdal
from osgeo.gdalconst import GA_ReadOnly
import numpy as np
import json
import logging
import datetime as dt
from osgeo import ogr
import shutil

def createOutFolder(outFolder):
    """
    Creates new folders from given path.
    
    Parameters (str): Path new nested folders to be created.
    """
    if not os.path.isdir(outFolder):
        os.makedirs(outFolder)
    else:
        pass

def getRequiredBandsPaths(product, imageryDate, requiredBands, rawInput, outFolder, resolution):
    """
    Returns object defining the input and output paths for product calculation.
    
    Parameters:
        product: Name of the product.
        imageryDate: YYYMMDD date of the imagery to be processed.
        requiredBands: Bands needed for this product.
        rawInput: Path to folder containing downloaded imagery.
        outFolder: Path to the folder that contains processed index tiles.
        resolution: Resolution of the input data (must match S2 resolution speification e.g. R10m for 10 m res.)
    """
    
    ## Empty return dict.
    processingPaths = {}
    ## Current date data folder.
    rawBandFolder = os.path.join(rawInput, imageryDate)
    ## List of .safe directories.
    safeFolders = os.listdir(rawBandFolder)
    ii = 0
    ## Iterate .safe directories to get input paths.
    for safeFolder in safeFolders:
        ## Navigate to folders where the actual data is stored.
        granuleFolder = os.path.join(rawBandFolder, safeFolder, "GRANULE")
        try:
            fFolder = os.listdir(granuleFolder)[0]
        except Exception as e:
            logging.error(f"{granuleFolder} is empty.")
            logging.error("e")
            break

        pathToRaw = os.path.join(granuleFolder, fFolder, "IMG_DATA", resolution)
        ## List the raw bands.
        rawBands = os.listdir(pathToRaw)
        processingPaths[ii] = {}
        ## Iterate required bands to get the correct datasets.
        for band in requiredBands.keys():
            processingPaths[ii][requiredBands[band]] = {}
            ## Iterate all bands to find the matching ones.
            for rawBand in rawBands:
                rawBandStr = rawBand.split("_")[2]
                if rawBandStr == requiredBands[band]:
                    ## Construct the matching bands paths and putput name.
                    inRaster = os.path.join(pathToRaw, rawBand)
                    outNameList = rawBand.split("_")[:2]
                    outName = f"{outNameList[0]}_{outNameList[1]}_{product}_{ii}.tif"
                    projectedBandPath = os.path.join(outFolder, imageryDate, product)
                    processingPaths[ii][requiredBands[band]] = inRaster
                    processingPaths[ii]["outFolder"] = projectedBandPath
                    processingPaths[ii]["outName"] = outName
        ii += 1
    return processingPaths

def openRasterOneBand(inRasterP):
    """
    Opens single band raster and returns its data and metadata.
    Paramerters:
        inRasterP - path to raster file.
     Returns:
        inArray - numpy array of input band.
        inCols - number of input data columns.
        inRows - number of input data rows.
        inBands - number of input data bands.
        inNoData - no data value of input raster.
        inExtension - extension of input raster.
        inDriver - gdal driver of input raster
        inGeotransform - list of six affine transform C describing the relationship between raster positions (in pixel/line coordinates) and georeferenced coordinates.
        inProj - georeferencing coordinate system of input data.
        inProjRef - projection coordinate system of the image in OpenGIS WKT format.
    """
    inRaster = gdal.Open(inRasterP, GA_ReadOnly)
    inBand = inRaster.GetRasterBand(1)
    inNoData = inBand.GetNoDataValue()
    if inNoData == None:
        inNoData = -9999.9
    inArray = inBand.ReadAsArray().astype("float32")
    inExtension = os.path.splitext(inRasterP)[1]
    inCols = inRaster.RasterXSize
    inRows = inRaster.RasterYSize
    inBands = inRaster.RasterCount
    inDriver = inRaster.GetDriver().ShortName
    inGeotransform = inRaster.GetGeoTransform()
    inProj = inRaster.GetProjection()
    inProjRef = inRaster.GetProjectionRef()
    del inRaster
    del inBand
    return (inArray, inCols, inRows, inBands, inNoData, inExtension, inDriver, inGeotransform, inProj, inProjRef)

def createMemoryRaster(outArray, outRaster, outCols, outRows, outNoData, outDriver, outGeotransform, outProj):
    """
    Creates in memory raster to immediatey process it without saving to disk.
    Paramerters:
        outArray: NumPy array containing raster data.
        outRaster: Should be path to location on distk but in ths case is just empty string.
        outCols: Number of the columns the raster will contain, should match outArray dimensions.
        outRows: Number of the rows the raster will contain, should match outArray dimensions.
        outNoData: No data value to be assigned to output raster.
        outDriver: Couldd be any gdal supported raster format but must be MEM if we want to save to ram.
        outGeotransform: Geotransform matrix to be assigned to output raster.
        outProj: Projection of the output raster.
    Returns:
        A reference to the raster in the memory, can be used in further gdal functions.
    """
    outDriver = gdal.GetDriverByName(outDriver)
    outRaster = outDriver.Create(outRaster, outCols, outRows, 1, gdal.GDT_Float32)
    outRaster.SetGeoTransform(outGeotransform)
    outRaster.SetProjection(outProj)
    outBand = outRaster.GetRasterBand(1)
    outBand.WriteArray(outArray)
    outBand.FlushCache()
    outBand.SetNoDataValue(outNoData)
    del outBand, outArray, outCols, outRows, outNoData, outDriver, outGeotransform, outProj
    return outRaster

def calculateEVI(B08, B04, B02):
    """
    Calculates Enhanced Vegetation Index from near infrared and red bands.
    Paramerters:
        B08: Sentinel-2 near infrared band.
        B04: Sentinel-2 red band.
        B02: Sentinel-2 BLUE band.
    """
    ## Equation taken from https://www.indexdatabase.de/search/?s=EVI
    EVI = 2.5 * (((B08 / 10000) - (B04 / 10000)) / (((B08 / 10000) + 6.0 * (B04 / 10000) - 7.5 * (B02 / 10000)) + 1))
    ## -9999 is the agreed no data value and it is assigned to any weird values.
    EVI[np.isnan(EVI)] = -9999.0
    EVI[np.isinf(EVI)] = -9999.0
    EVI[B08 == 0.0] = -9999.0
    EVI[B04 == 0.0] = -9999.0
    EVI[B02 == 0.0] = -9999.0
    EVI[EVI > 1.25] = -9999.0
    EVI[EVI < -1] = -9999.0
    return EVI

def calculateNDMI(B8A, B11):
    """
    Calculates Normalized Difference Moisture Index from near infrared and red bands.
    Paramerters:
        B08: Sentinel-2 near infrared band.
        B11: Sentinel-2 short wave infrared band.
    """
    ## Equation taken from https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/ndmi/
    NDMI = ((B8A / 10000) - (B11 / 10000)) / ((B8A / 10000) + (B11 / 10000))

    ## -9999 is the agreed no data value and it is assigned to any weird values.
    NDMI[np.isnan(NDMI)] = -9999.0
    NDMI[np.isinf(NDMI)] = -9999.0
    NDMI[B8A == 0.0] = -9999.0
    NDMI[B11 == 0.0] = -9999.0
    NDMI[NDMI > 1] = -9999.0
    NDMI[NDMI < -1] = -9999.0
    return NDMI

def calculateNDWI(B03, B08):
    """
    Calculates Normalized Difference Water Index.
    Paramerters:
        B03: Sentinel-2 green band.
        B08: Sentinel-2 near infrared band.
    """
    ## Equation taken from https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/ndwi/
    NDWI = ((B03 / 10000) - (B08 / 10000)) / ((B03 / 10000) + (B08 / 10000))

    ## -9999 is the agreed no data value and it is assigned to any weird values.
    NDWI[np.isnan(NDWI)] = -9999.0
    NDWI[np.isinf(NDWI)] = -9999.0
    NDWI[B03 == 0.0] = -9999.0
    NDWI[B08 == 0.0] = -9999.0
    NDWI[NDWI > 1] = -9999.0
    NDWI[NDWI < -1] = -9999.0
    return NDWI

def calculateNDVI(B08, B04):
    """
    Calculates Normalized Difference Vegetation Index.
    Paramerters:
        B04: Sentinel-2 red band.
        B08: Sentinel-2 near infrared band.
    """
    ## Equation taken from https://custom-scripts.sentinel-hub.com/custom-scripts/sentinel-2/ndwi/
    NDVI = ((B08 / 10000) - (B04 / 10000)) / ((B08 / 10000) + (B04 / 10000))

    ## -9999 is the agreed no data value and it is assigned to any weird values.
    NDVI[np.isnan(NDVI)] = -9999.0
    NDVI[np.isinf(NDVI)] = -9999.0
    NDVI[B04 == 0.0] = -9999.0
    NDVI[B08 == 0.0] = -9999.0
    NDVI[NDVI > 1] = -9999.0
    NDVI[NDVI < -1] = -9999.0
    return NDVI

def calculateProducts(params, imageryDate):
    """
    Master Sentinel-2 product calculation function.
    Paramerters:
        params: Parameters object read from parameters json.
        imageryDate: Date of the current processed imagery YYYYMMDD.

    """
    logging.info(f"Fetching arguments.")
    ## Fetch arguments from json.
    rawInput = params["script"]["rawInput"]
    clippingMask = params["script"]["clippingMask"]
    productArgs = params["products"]
    outEPSG = params["script"]["outEPSG"]
    productOutput = params["script"]["productOutput"]
    logging.info(f"Parameters fetched.")

    logging.info(f"Start processing products.")

    newProducts = {}
    ## Iterate the products that can be calculated from Sentinel-2 specified in json
    for prodId in productArgs.keys():
        logging.info(f"Start calculating {productArgs[prodId]['name']}.")
        ## Get product specific parameters.
        resolution = productArgs[prodId]["resolution"]
        bands = productArgs[prodId]["bands"]
        product = productArgs[prodId]["name"]
        newProducts[prodId] = {"name": product}

        logging.info(f"Fetching and constructing input and output datasets paths.")
        ## Get the paths to the input and output datasets (generated) according to the specific bands required.
        try:
            requiredInputOutputPaths = getRequiredBandsPaths(product, imageryDate, bands, rawInput, productOutput, resolution)
            logging.info(f"Fetched.")
        except Exception as e:
            logging.error(f"Error while fetching and calculationg paths for {productArgs[prodId]['name']}")
            logging.error(e)

        logging.info(f"Creating output folders.")
        ## Iterate required tiles to create output folders.
        for tile in requiredInputOutputPaths.keys():
            outFolder = requiredInputOutputPaths[tile]["outFolder"]
            ## ... try to create output folders...
            try:
                createOutFolder(outFolder)
            except Exception as e:
                logging.error(f"Error while creating {outFolder}.")
                logging.error(e)
                continue
        logging.info("Output folders created.")

        logging.info("Starting main calculation loop.")
        ## Iterate required tiles to calculate products.
        tiles = []
        for tile in requiredInputOutputPaths.keys():
            outFolder = requiredInputOutputPaths[tile]["outFolder"]
            outName = requiredInputOutputPaths[tile]["outName"]
            if not os.path.exists(os.path.join(outFolder, outName)):

                ## Identify product name and act accordingly.
                if productArgs[prodId]["name"] == "EVI":
                    logging.info("Opening input bands.")
                    ## Open input raster bands.
                    try:
                        B08 = openRasterOneBand(requiredInputOutputPaths[tile]["B08"])
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B08']}.")
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B08']}.")
                        logging.error(e)
                        continue
                    try:
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B04']}.")
                        B04 = openRasterOneBand(requiredInputOutputPaths[tile]["B04"])
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B04']}.")
                        logging.error(e)
                        continue
                    try:
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B02']}.")
                        B02 = openRasterOneBand(requiredInputOutputPaths[tile]["B02"])
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B02']}.")
                        logging.error(e)
                        continue
                    logging.info("Calcultiong EVI2")
                    ## Calculate Enhanced Vegetation Index 2.
                    try:
                        result = calculateEVI(B08[0], B04[0], B02[0])
                        logging.info("EVI2 calculated")
                    except Exception as e:
                        logging.error(f"Error while calculating EVI2 from {requiredInputOutputPaths[tile]['B08']} and {requiredInputOutputPaths[tile]['B04']} and {requiredInputOutputPaths[tile]['B02']}.")
                        logging.error(e)
                        continue

                    logging.info("Saving calculated dataset to memory.")
                    ## Save resulting array to memory raster using gdal.
                    try:
                        resultRaster = createMemoryRaster(result, "", B08[1], B08[2], -9999.0, "MEM", B08[7], B08[8])
                        logging.info("Saved.")
                    except Exception as e:
                        logging.error(f"Error while creation in memory output for {productArgs[prodId]['name']}.")
                        logging.error(e)
                        continue
                    
                    B02 = None
                    B04 = None
                    B08 = None

                if productArgs[prodId]["name"] == "NDMI":
                    logging.info("Opening input bands.")
                    ## Open input raster bands.
                    try:
                        B8A = openRasterOneBand(requiredInputOutputPaths[tile]["B8A"])
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B8A']}.")
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B8A']}.")
                        logging.error(e)
                        continue
                    
                    try:
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B11']}.")
                        B11 = openRasterOneBand(requiredInputOutputPaths[tile]["B11"])
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B11']}.")
                        logging.error(e)
                        continue
                    
                    logging.info("Calcultiong NDMI")
                    ## Calculate Normalized Difference moisture index.
                    try:
                        result = calculateNDMI(B8A[0], B11[0])
                        logging.info("NDMI calculated")
                    except Exception as e:
                        logging.error(f"Error while calculating NDMI from {requiredInputOutputPaths[tile]['B8A']} and {requiredInputOutputPaths[tile]['B11']}.")
                        logging.error(e)
                        continue

                    logging.info("Saving calculated dataset to memory.")
                    ## Save resulting array to memory raster using gdal.
                    try:
                        resultRaster = createMemoryRaster(result, "", B8A[1], B8A[2], -9999.0, "MEM", B8A[7], B8A[8])
                        logging.info("Saved.")
                    except Exception as e:
                        logging.error(f"Error while creation in memory output for {productArgs[prodId]['name']}.")
                        logging.error(e)
                        continue
                    
                    B11 = None
                    B8A = None

                if productArgs[prodId]["name"] == "NDWI":
                    logging.info("Opening input bands.")
                    ## Open input raster bands.
                    try:
                        B03 = openRasterOneBand(requiredInputOutputPaths[tile]["B03"])
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B03']}.")
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B03']}.")
                        logging.error(e)
                        continue
                    
                    try:
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B08']}.")
                        B08 = openRasterOneBand(requiredInputOutputPaths[tile]["B08"])
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B08']}.")
                        logging.error(e)
                        continue

                    logging.info("Calcultiong NDWI")
                    ## Calculate Normalized Difference Water Index.
                    try:
                        result = calculateNDWI(B03[0], B08[0])
                        logging.info("NDWI calculated")
                    except Exception as e:
                        logging.error(
                            f"Error while calculating NDWI from {requiredInputOutputPaths[tile]['B03']} and {requiredInputOutputPaths[tile]['B08']}.")
                        logging.error(e)
                        continue

                    logging.info("Saving calculated dataset to memory.")
                    ## Save resulting array to memory raster using gdal.
                    try:
                        resultRaster = createMemoryRaster(result, "", B03[1], B03[2], -9999.0, "MEM", B03[7], B03[8])
                        logging.info("Saved.")
                    except Exception as e:
                        logging.error(f"Error while creation in memory output for {productArgs[prodId]['name']}.")
                        logging.error(e)
                        continue
                    
                    B03 = None
                    B08 = None
                    
                if productArgs[prodId]["name"] == "NDVI":
                    logging.info("Opening input bands.")
                    ## Open input raster bands.
                    try:
                        B04 = openRasterOneBand(requiredInputOutputPaths[tile]["B04"])
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B04']}.")
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B04']}.")
                        logging.error(e)
                        continue
                    
                    try:
                        logging.info(f"Opened {requiredInputOutputPaths[tile]['B08']}.")
                        B08 = openRasterOneBand(requiredInputOutputPaths[tile]["B08"])
                    except Exception as e:
                        logging.error(f"Error while opening {requiredInputOutputPaths[tile]['B08']}.")
                        logging.error(e)
                        continue

                    logging.info("Calcultiong NDVI")
                    ## Calculate Normalized Difference Vegetation Index.
                    try:
                        result = calculateNDVI(B08[0], B04[0])
                        logging.info("NDVI calculated")
                    except Exception as e:
                        logging.error(
                            f"Error while calculating NDVI from {requiredInputOutputPaths[tile]['B08']} and {requiredInputOutputPaths[tile]['B04']}.")
                        logging.error(e)
                        continue

                    logging.info("Saving calculated dataset to memory.")
                    ## Save resulting array to memory raster using gdal.
                    try:
                        resultRaster = createMemoryRaster(result, "", B04[1], B04[2], -9999.0, "MEM", B04[7], B04[8])
                        logging.info("Saved.")
                    except Exception as e:
                        logging.error(f"Error while creation in memory output for {productArgs[prodId]['name']}.")
                        logging.error(e)
                        continue
                    
                    B04 = None
                    B08 = None
                    
                logging.info("Clipping and reporjecting output dataset.")
                ## Clip and project product tile to input shp and  to EPSG:3857
                try:
                    gdal.Warp(os.path.join(outFolder, outName), resultRaster, format="GTiff", cutlineDSName=clippingMask, dstNodata=-9999.0, dstSRS=outEPSG)
                    logging.info("Done.")
                except Exception as e:
                    logging.error(f"Error while clipping or reprojecting {productArgs[prodId]['name']}.")
                    logging.error(e)
                    continue
            else:
                pass
            tiles.append(os.path.join(outFolder, outName))

        logging.info("Mosaicing tiles to output")
        mosaicFolder = os.path.join(params["script"]["productOutput"], imageryDate, productArgs[prodId]["name"])
        mosaicName = f"{outName.split('_')[1][:8]}_{outName.split('_')[2]}.vrt"
        ## ... try to create output folders...
        logging.info("Creating mosaic output folder.")
        try:
            createOutFolder(mosaicFolder)
            logging.info("Done.")
        except Exception as e:
            logging.error(f"Error while creating {mosaicFolder}.")
            logging.error(e)
            continue

        mosaicPath = os.path.join(mosaicFolder, mosaicName)

        logging.info(f"Creating tile mosaic {mosaicPath}.")
        try:
            ## Using BuildVRT: It actually creates only virtual mosaic (xml) in the products, actual files are left in processing folder.
            gdal.BuildVRT(mosaicPath, tiles, options=gdal.BuildVRTOptions())
            logging.info(f"Succesfully created mosaic: {mosaicPath}.")
        except Exception as e:
            logging.error("Failed to create mosaic.")
            logging.error(e)
            continue
        
        newProducts[prodId]["newDate"] = imageryDate
        
    logging.info(f"Done.")  
    return newProducts
    

def clearIntermediateData(intermediateDataFolder):
    """
    Deletes intermediate data in intermediate processing folder and all of its contents except logs.
    
    Parameters:
        intermediateDataFolder: Path to intermediate folder.
    """
    
    logging.info(f"Starting cleanup of {intermediateDataFolder}.")
    content = os.listdir(intermediateDataFolder)
    for element in content:
        elPath = os.path.join(intermediateDataFolder, element)
        if os.path.isdir(elPath):
            logging.info(f"Atempting to delete {elPath} and its contents.")
            try:
                shutil.rmtree(elPath)
                logging.info(f"Success.")
            except Exception as e:
                logging.error("Failed delete intermediate data.")
                logging.error(e)
                continue
        else:
            logging.info(f"Skipped {elPath}.")



def sentinelProductCalculator(imageryDate):
    ## Get the parameters josn.
    with open("Sentinel2\\A1P_sentinel2_products.json", "r") as read_file:

        data = json.load(read_file)
    ## Imagery date will have to be passed form the master process after the imagery is downloaded.
    ## Logging configuration
    today = dt.date.today().strftime("%Y%m%d")
    logging.basicConfig(format="%(asctime)s %(levelname)s : %(message)s", level=logging.ERROR,
                        filename=f"{data['script']['productOutput']}{today}_sentinel-2.log")
    ## Product calcuation function.
    newProducts = calculateProducts(data, imageryDate)

    return newProducts

if __name__ == "__main__":
    # Main function sentinelProductCalculator() is imported to upper sattiliDataProcessing.py
    pass