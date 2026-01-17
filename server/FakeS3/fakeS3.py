import random


validURLs = set()
fakeStorage = {}

def generateURL():
    random_number = random.randint(1000, 9999)
    url = f"https://fake-s3-url.com/{random_number}"
    return url

def storeFile(url, file):
    if url in validURLs:
        fakeStorage[url] = file
        return True
    return False

