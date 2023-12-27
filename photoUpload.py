import os
import sys
import json
import pickle
from attr import NOTHING
from httplib2 import Credentials
import requests

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
#from flask import Flask, request, redirect

####
# Example Usage
#
# python photoUpload.py /c/Users/steve/Google\ Drive/Google\ Photos/2014/
####

reset = False
debug = False
accessToken = ''
creds = None
server = 'localhost:5000'

urls = {'albums':'https://photoslibrary.googleapis.com/v1/albums',
    'uploads':'https://photoslibrary.googleapis.com/v1/uploads',
    'create':'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
}

#app = Flask(__name__)
#app.config['SERVER_NAME'] = server

def getHeader():

    if not creds.valid:
        getAuth()

    return {'Content-type': 'application/json', 'Authorization': 'Bearer %s'%(accessToken)}

def getInteractiveAuthorization():

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file('credentials.json', scopes=['https://www.googleapis.com/auth/photoslibrary'], redirect_uri='http://'+server+'/authorize')

    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')

    # urlParts = authorization_url.split('&')

    # urlDict = {}
    # for p in urlParts:
    #     kv = p.split('=')
    #     urlDict[kv[0]] = kv[1]

    # for k,v in urlDict.items():
    #     print(k, ': ', v)

    print('Go to the following URL to grant access:')
    print(authorization_url)

    code = input('Enter the authorization code: ')

    token = flow.fetch_token(code=code)

    credentials = flow.credentials

    print(token)
    print("CREDENTIALS", credentials)

    #tokenJson = json.loads(token)

    return credentials
    #return token['access_token']

def createAlbum(albumName):
    global urls
    postData = {"album": {"title": albumName}}
    retVal = requests.post(urls['albums'], data=json.dumps(postData), headers=getHeader())

    print(retVal.text)

    return json.loads(retVal.text)['id']

def getAlbums():
    global urls
    albums = []
    pageSize = 50
    search = True
    nextPageToken = ''

    while search:
        url = urls['albums'] + '?pageSize=%s'%(pageSize)

        if nextPageToken != '':
            url = url + "&pageToken=%s"%(nextPageToken)

        r = requests.get(url, headers=getHeader())

        albumJson = json.loads(r.text)

        for a in albumJson['albums']:
            albums.append(a)

        if 'nextPageToken' not in albumJson:
            search = False
        else:
            nextPageToken = albumJson['nextPageToken']

    print('Found %s albums'%(len(albums)))

    return albums

def findAlbumId(albumName):
    albums = getAlbums();

    for a in albums:
        if a['title'] == albumName:
            return a['id']

    return ''

def uploadPhoto(photoPath, fileName):
    global urls
    print('uploadPhoto', photoPath, fileName)
    headers = getHeader()
    headers['Content-type'] = 'application/octet-stream'
    headers['X-Goog-Upload-File-Name'] = fileName
    headers['X-Goog-Upload-Protocol'] = 'raw'

    data = open(photoPath, 'rb').read()

    r = requests.post(urls['uploads'], data=data, headers=headers)

    if r.status_code == 200:
        print('Upload Id: ', r.text)
        return r.text
    else:
        print('Failed to upload %s'%(photoPath))
        return ''

def createMediaItem(albumId, fileName, uploadToken):
    global urls
    body = {}
    body['albumId'] = albumId

    mediaItems = []

    newMediaItem = {}
    newMediaItem['description'] = fileName

    simpleMediaItem = {}
    simpleMediaItem['uploadToken'] = uploadToken

    newMediaItem['simpleMediaItem'] = simpleMediaItem

    mediaItems.append(newMediaItem)

    body['newMediaItems'] = mediaItems

    print(body)

    r = requests.post(urls['create'], data=json.dumps(body), headers=getHeader())

    print(r.status_code)

    statusReturn = json.loads(r.text)

    print(r.text)

    return statusReturn["newMediaItemResults"][0]["status"]['message'] == "Success"

def uploadPhotoToAlbum(albumId, photoPath, photoName):
    global debug

    if debug:
        print('Debug mode. Not uploading photos')
        return True

    try:
        uploadId = uploadPhoto(photoPath, photoName)

        if uploadId == '':
            return False

        return createMediaItem(albumId, photoName, uploadId)
    except Exception as e:
        print(e)
        return False

def getUploadedFiles(path):
    uploadedRecordData = ''

    try:
        f = open(path + '/uploaded.txt', 'r')
        uploadedRecordData = f.read()
        f.close()
    except Exception as e:
        print(e)
        print('Folder has not been synced before')

    return uploadedRecordData

def runSync(path, albumId):
    global reset
    global debug
    filesToUpload = 0

    uploadedRecordData = getUploadedFiles(path)
    if reset:
        uploadedRecord = open(path + '/uploaded.txt', 'w+')
    else:
        uploadedRecord = open(path + '/uploaded.txt', 'a+')

    for r, d, f in os.walk(path):
        for file in f:
            #print(r)
            if '.JPG' in file or '.jpg' in file or '.jpeg' in file or '.tif' in file: # or '.ini' in file or '.db' in file or '.MOV' in file:
                fn = r + '/' + file

                if fn in uploadedRecordData:
                    continue
                else:
                    if uploadPhotoToAlbum(albumId, fn, file):
                        uploadedRecord.write(fn + '\n')
                        uploadedRecord.flush()

                    if debug:
                        filesToUpload = filesToUpload + 1
            else:
                if '.ini' in file:
                    continue

                print('File not uploaded: ', file)

    if debug:
        print('Found %s file to upload.'%(filesToUpload))

def getAuth():
    global accessToken
    global creds

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

            if hasattr(creds, 'token'):
                accessToken = creds.token
            else:
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = getInteractiveAuthorization()
        else:
            creds = getInteractiveAuthorization()
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    print("CREDS",creds)
    accessToken = creds.token

# @app.route('/authorize', methods=['GET'])
# def authorize():
#     global creds
#     code = request.form['code']
#     creds = request.form['credentials']

#     with open('token.pickle', 'wb') as token:
#         pickle.dump(creds, token)

#     print('CREDS', creds)
#     accessToken = creds.token

# @app.route('/', methods=['GET'])
# def runApp():
#     main()

def main():
    global debug
    global accessToken
    global reset
    global creds

    if len(sys.argv) == 1:
        print('You must specify a path.')
        exit(1)

    path = sys.argv[1]

    print(path)

    if len(sys.argv) > 2:
        print(sys.argv[2])
        if  sys.argv[2].lower() == 'debug':
            print('Debug Mode turned on')
            debug = True
        elif sys.argv[2].lower() == 'reset':
            print('Reset Mode turned on')
            reset = True

    print('Uploading photos from: ', path)

    if path.endswith('/'):
        path = path[:len(path)-1]

    albumName = path.split('/').pop()

    print('Photos will be uploaded to album: ', albumName)

    if debug:
        albumId = albumName
    else:
        getAuth()

        # Find the album. If it doesn't exist, create it.
        albumId = findAlbumId(albumName)

        if albumId == '':
            albumId = createAlbum(albumName)

    runSync(path, albumId)

if __name__ == '__main__':
    #app.run(debug=True)
    main()

#print('Album ID is: ', albumId)
#credentials = service_account.Credentials.from_service_account_file('photo-uploader-1571866857206-94db35161f3d.json')
#scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/drive'])
# headers = {'', ''}
# with open('credentials.json') as credFile:
#     creds = json.load(credFile)
#     print(creds['installed'])
#print(token)
#print(state)
#https://www.googleapis.com/auth/drive	

# python photoUpload.py /c/Users/steve/Google\ Drive/Google\ Photos/2021/
