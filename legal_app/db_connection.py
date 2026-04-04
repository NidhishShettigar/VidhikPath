import pymongo

url = 'mongodb+srv://vidhikpath:vidhikpath@cluster0.m2j80to.mongodb.net/'
client =  pymongo.MongoClient(url)

db = client['vidhikpath']