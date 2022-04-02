import xml.etree.ElementTree as ET
import os
import sys
import requests, zipfile, io
import json
import logging
import datetime as dt

def createOutFolder(outFolder):
    """
    Creates new folders from given path.
    
    Parameters (str): Path new nested folders to be created.
    """
    if not os.path.isdir(outFolder):
        os.makedirs(outFolder)
    else:
        pass

def getProductXML(user, password, extent, platform, daysback):
    """
    Performs a query to https://scihub.copernicus.eu/dhus/search to retrieve and parse the response containing information on available imagery.
    
    Parameters:
        user (str): Your user name at copernicus scihub.
        password (str): Your password for copernicus scihub.
        extent (str): WKT string of a polygon covering the area of interest.
        platform (str): Sentinel-2 for Sentinel-2 imagery.
        daysback (str): How many days in the past from today would you like to search for imagery. Must be in format <positive int>DAYS.
    """
    
    logging.info(f'Starting fetch available products xml as user {user}.')
    logging.info(f'Used arguments are: {extent}, {platform}, {daysback}.')
    
    # Construct the query url for copernicus scihub.
    URL = f'https://scihub.copernicus.eu/dhus/search?start=0&rows=100&q=(footprint:%22Intersects({extent})%22%20AND%20platformname:{platform}%20AND%20ingestiondate:%5bNOW-{daysback}%20TO%20NOW%5d)'
    i = 0
    try:
        # Fetch xml.
        response = requests.get(URL, auth=(user, password))
        logging.info(f'Xml fetched.')
        
        # Sometimes more requests are needed to succesfully obtain xml...
        while response.status_code != 200:
            logging.warning(f'Got invalid response status code ({response.status_code}). Retrying. Attempt no.{i}/15.')
            logging.info(f'Starting fetch available products xml as user {user}.')
            logging.info(f'Used arguments are: {extent},{platform},{daysback}.')
            response = requests.get(URL, auth=(user, password))
            i += 1
            
            # ...but we should not repeat them indefinitely.
            if i > 15:
                logging.error(f'Exceeded number of allowed attempts.')
                break
        return response.content
    except Exception as e:
        logging.error(f'An error occured while fetching xml.')
        logging.error(e)

def getProductParams(productXML, processinglevel, relativeorbitnumber):
    """
    Parses the retrieved xml for data relevant for imagery download and returns a dict containing this information.
    
    Parameters:
        productXML (xml): Xml downloaded from copernicus scihub returned by getProductXML().
        processinglevel (str): "Level-2A" or "Level-1C" - Indicates processing level of S-2 imagery.
        relativeorbitnumber: Relative satellite orbit number over requested area. 
    """
    
    logging.info(f'Starting parsing product .xml.')
    # Acces xml root.
    try:
        root = ET.fromstring(productXML)
    except Exception as e:
        logging.error('Error occured while parsing xml.')
        logging.error(e)

    i = 0
    # Results container.
    queryDict = {}
    logging.info(f'Starting queryng product .xml for imagery related info.')
    for child in root:
        # Single element results dict.
        queryDictEl = {}
        for entry in child:
            # Check relevant attributes and save their values to single element results dict.
            if entry.attrib == {'name': 'filename'}:
                filename = entry.text
                queryDictEl['filename'] = filename
            if entry.attrib == {'name': 'processinglevel'}:
                pLevel = entry.text
                queryDictEl['pLevel'] = pLevel
            if entry.attrib == {'name': 'uuid'}:
                uuid = entry.text
                queryDictEl['uuid'] = uuid
            if entry.attrib == {'name': 'relativeorbitnumber'}:
                roNumber = entry.text
                queryDictEl['roNumber'] = roNumber

        # If anything was returned add to results dict.
        if len(queryDictEl) > 0:
            queryDict[str(i)] = queryDictEl
            logging.info(f'Succesfully queried {i}: {queryDictEl}.')
            i += 1
        else:
            pass
    logging.info(f'Succesfully queried {len(queryDict)} imagery related entries.')
    
    # Final results container.
    productsToDownload = {}
    logging.info(f'Starting queryng product .xml for processing level: {processinglevel} and relative orbit no.: {relativeorbitnumber}.')
    i = 0
    # Second pass to select imagery matching <processinglevel> and <relativeorbitnumber>.
    try:
        for productNo in queryDict.keys():
            if processinglevel in queryDict[productNo].values() and relativeorbitnumber in queryDict[productNo].values():
                productsToDownload[str(i)] = queryDict[productNo]
                logging.info(f'Succesfully queried {i}: {queryDict[productNo]}.')
                i += 1
        logging.info(f'Succesfully queried {len(productsToDownload)} entries that match input arguments.')
        return productsToDownload
    except Exception as e:
        logging.error(f'Something went wrong while querying for desired imagery in iteration no. {i} of {len(queryDict)}. Entry {queryDict[productNo]} caused this.')
        logging.error(e)

def downoadImagery(user, password, productParams, outFolder):
    """
    Downloads the selected imagery.
    
    Paramters:
        user (str): Your user name at copernicus scihub.
        password (str): Your password for copernicus scihub.
        productParams (dict): Python dict containing parameters for each granule download returned by getProductParams().
        outFolder (str): Path to root data folder.
    """
    
    logging.info(f'Starting downloading selected imagery.')
    logging.info(f'Used arguments are: {productParams}, {outFolder}.')
    
    # Iterate over selected entries of productParams and downnload the imagery.
    for productParam in productParams.keys():
        # Get image acquisition date from its file name.
        imageryDate = productParams[productParam]["filename"].split("_")[2][:8]
        # Create new folder for downloaded granules.
        imageryFolder = f'{outFolder}{imageryDate}\\'
        # Path to save to.
        saveTo = f'{imageryFolder}{productParams[productParam]["filename"]}'
        try:
            logging.info(f'Creating destination folder: {imageryFolder}.')
            createOutFolder(imageryFolder)
            logging.info(f'Success.')
        except Exception as e:
            logging.error(f'Failed to create destination folder: {imageryFolder}.')
            logging.error(e)
            continue 
        # Download url.
        url = f"https://scihub.copernicus.eu/dhus/odata/v1/Products('{productParams[productParam]['uuid']}')//$value"
        # Try to download the image...
        try:
            logging.info(f'Downloading: {productParams[productParam]["filename"]}, from {url}.')
            response = requests.get(url, stream=True, auth=(user, password))
            if response.status_code == 200:
                logging.info(f'Downloaded: {productParams[productParam]["filename"]}, from {url}, proceeding to extract.')
                # ... and extract immediately.
                try:
                    z = zipfile.ZipFile(io.BytesIO(response.content))
                    z.extractall(imageryFolder)
                    logging.info(f'Extraction of: {saveTo} successfull.')
                except Exception as e:
                    logging.error(f'Failed to extract {saveTo}.')
                    logging.error(e)
                    continue
            else:
                logging.warning(f'Download failed. Response code was not 200 but {response.status_code}.')
                logging.warning(response.text)
                continue
        except Exception as e:
            logging.error(f'Something went wrong while retrieving {productParams[productParam]["filename"]}, from {url}.')
            logging.error(e)
            continue
        logging.info(f'Succesfully downlaoded and extracted imagery for {imageryDate}.')
        
    return imageryDate

def sentinelImageryDownloader():
    # open and read paramters from json.
    with open('Sentinel2\\A0P_sentinel2_download.json', 'r') as read_file:
        data = json.load(read_file)
    ## Logging configuration
    today = dt.date.today().strftime('%d%m%Y')
    logging.basicConfig(format='%(asctime)s %(levelname)s : %(message)s', level=logging.DEBUG, filename=f'{data["outFolder"]}{today}_sentinel-2.log')

    productsXML = getProductXML(data['user'], data['password'], data['extent'], data['platform'], data['daysback'])
    productParams = getProductParams(productsXML, data['processinglevel'], data['relativeorbitnumber'])
    imageryDate = downoadImagery(data['user'], data['password'], productParams, data['outFolder'])
    return imageryDate

if __name__ == '__main__':
    # Main function sentinelImageryDownloader() is imported to upper sattiliDataProcessing.py
    pass
