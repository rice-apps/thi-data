import random
class FakeS3:

    def __init__ (self):
        self.validURLs = set()
        self.fakeStorage = {}
        self.urlToObjectKey = {}

    def generatePresignedURL(self):
        random_number = random.randint(1000, 9999)
        url = f"https://fake-s3-url.com/{random_number}"
        self.validURLs.add(url)
        return url

    def storeFile(self, url, file):
        if url in self.validURLs:
            self.fakeStorage[url] = file
            return True
        return False

    def retrieveFile(self, url):
        return self.fakeStorage.get(url, None)

    def deleteFile(self, url):
        if url in self.fakeStorage:
            del self.fakeStorage[url]
            return True
        return False



