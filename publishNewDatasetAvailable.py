import requests, json, logging

def getParameters():
    """
    Reads json containing parameters for new dataset upload.
    """
    logging.info("Fetching product date database update arguments.")
    with open("publishNewDatasetAvailable_P.json", "r") as read_file:
        data = json.load(read_file)
    logging.info("Done.")
    return data

def publishNewDataset(productName, newDate):
    """
    When product for new date is calculated the new available date is sent to the database with this function.
    
    Parameters:
        productName (str): Name of the product.
        newDate (str): New available data in YYYYMMDD format.
    """
    # Fetch parametrs from accompanying json.
    data = getParameters()
    logging.info(f"Publishing new dataset: Product: {productName}, Date: {newDate}.")
    
    # Build request URL string.
    resource = f"{data['url']}{data['endPoint']}"
    # Add parameters for API to correctly update database.
    data["productName"] = productName
    data["newDate"] = newDate
    # Post new available date for current product.
    x = requests.post(resource, data=data)
    logging.info(f"Done with response: {x}.")

if __name__ == "__main__":
    pass