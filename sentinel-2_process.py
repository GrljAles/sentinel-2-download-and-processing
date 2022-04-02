import sys
import logging
import datetime as dt
from publishNewDatasetAvailable import publishNewDataset
from Sentinel2 import A0_sentinel2_download
from Sentinel2 import A1_sentinel2_products


def main(dataSource):
    """
    Main function that executes the process of new satellite imagery download and calculation of products.
    Paramaters for individual scripts are handeled by those scrips. 
    
    Paramters:
        dataSource (str): Curretnly accepts only one value: <sentinel-2>. 
    """
    if dataSource == "sentinel-2":
        # First download latest imagery and return date that it was downloaded for.
        imageryDate = A0_sentinel2_download.sentinelImageryDownloader()
        
        # Calculate products for downloaded imagery.
        newProducts = A1_sentinel2_products.sentinelProductCalculator(
            imageryDate)
        
        # Submit new availabe dates of products to database.
        for prId in newProducts.keys():
            publishNewDataset(
                newProducts[prId]["name"], newProducts[prId]["newDate"])


if __name__ == "__main__":
    # Logging configuration
    today = dt.date.today().strftime("%Y%m%d")
    logging.basicConfig(format="%(asctime)s %(levelname)s : %(message)s",
                        level=logging.DEBUG, filename=f"{today}_dataProcessing.log")

    # Argument 1 should specify the satellite platform name.
    dataSource = sys.argv[1]
    main(dataSource)
