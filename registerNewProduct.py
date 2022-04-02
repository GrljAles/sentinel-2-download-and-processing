import requests, json

def getParameters():
    """
    Reads json containing parameters for new dataset registration.
    """
    with open("registerNewProduct_P.json", "r") as read_file:
        data = json.load(read_file)
    return data

def registerNewProduct():
    """
    Adds new product to database.
    """
    # Fetch parametrs from accompanying json.
    data = getParameters()
    # Build request URL string.
    resource = f"{data['url']}{data['endPoint']}"
    # Post new available date for current product.
    x = requests.post(resource, data=data)
    
if __name__ == "__main__":
    registerNewProduct()