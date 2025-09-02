import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate('"C:\Users\Sujan\Documents\Major Project Related files\vidhikpath-e9e56-firebase-adminsdk-fbsvc-72b0568245.json"')
default_app = firebase_admin.initialize_app(cred)
