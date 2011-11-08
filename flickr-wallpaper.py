#!/usr/bin/python
"""Usage: python flickr-wallpaper.py CONFIG_PATH

ARGUMENTS:
  -c or --config : path to config file ('./config')

Config File must have the following format:
    groups = Comma-separated list of Flickr Group IDs (ex. 796617@N22)
    image_root = PATH to where downloaded files should go (ex. ~/wallpapers)
    api_key = API KEY from Flickr

"""

import sys
import urllib
import hashlib
import os
import string    

from urllib import urlencode, urlopen
from xml.dom import minidom
from pprint import pprint
from configobj import ConfigObj
from time import time
from datetime import datetime

HOST = 'http://flickr.com'
API = '/services/rest'
AUTH = False
debug = False

CONFIG_FILENAME = ''
API_KEY = ''

def main(*argv):
    from getopt import getopt, GetoptError

    global API_KEY
    global CONFIG_FILENAME

    try:
        (opts, args) = getopt(argv[1:],\
                              'c:',\
                              ['config'])
    except GetoptError, e:
        print e
        print __doc__
        return 1

    for o, a in opts:
        if o in ('-c' , '--config'):
            CONFIG_FILENAME = a
        else:
            print "Unknown argument: %s" % o
            print __doc__
            return 1

    if (CONFIG_FILENAME == ''):
        CONFIG_FILENAME = '~/.flickr-wallpaper-config'

    CONFIG_FILENAME = os.path.expandvars(CONFIG_FILENAME)
    CONFIG_FILENAME = os.path.expanduser(CONFIG_FILENAME)
    print 'Using Config file: %s' % CONFIG_FILENAME
    
    API_KEY = get_api_key()
    if (API_KEY == ''):
        print "Missing API KEY, must have a line in config file for Flickr API Key, ex. api_key = dddddddd"
        print __doc__
        return 1

    image_root = get_image_root()
    if (image_root == ''):
        print "Missing image_root, must have a line in config file for image root, ex. image_root = /path/to/download"
        print __doc__
        return 1

    if not os.path.exists(image_root):
        print 'Image root path not found, creating path: ' + image_root
        os.makedirs(image_root)
    
    for groupid in get_groups():
        min_upload_date = get_min_upload_date(groupid)
        download_photos_from_group(image_root, groupid, min_upload_date)
        set_min_upload_date(groupid);

def photos_search(user_id='', auth=False,  tags='', tag_mode='', text='',\
                  min_upload_date='', max_upload_date='',\
                  min_taken_date='', max_taken_date='', \
                  license='', per_page='', page='', sort='',\
                  safe_search='', content_type='', 
                  extras='', group_id=''):
    """Returns a list of Photo objects.

    If auth=True then will auth the user.  Can see private etc
    """
    method = 'flickr.photos.search'

    data = _doget(method, auth=auth, user_id=user_id, tags=tags, text=text,\
                  min_upload_date=min_upload_date,\
                  max_upload_date=max_upload_date, \
                  min_taken_date=min_taken_date, \
                  max_taken_date=max_taken_date, \
                  license=license, per_page=per_page,\
                  page=page, sort=sort,  safe_search=safe_search, \
                  content_type=content_type, \
                  extras=extras, group_id=group_id, \
                  tag_mode=tag_mode)

    return data
 
def _doget(method, auth=False, **params):
    #uncomment to check you aren't killing the flickr server
    #print "***** do get %s" % method

    params = _prepare_params(params)
    url = '%s%s/?api_key=%s&method=%s&%s%s'% \
          (HOST, API, API_KEY, method, urlencode(params),
                  _get_auth_url_suffix(method, auth, params))

    #another useful debug print statement
    if (debug): print "_doget", url
    
    return minidom.parse(urlopen(url))

def _prepare_params(params):
    """Convert lists to strings with ',' between items."""
    for (key, value) in params.items():
        if isinstance(value, list):
            params[key] = ','.join([item for item in value])
    return params

def _get_auth_url_suffix(method, auth, params):
    """Figure out whether we want to authorize, and if so, construct a suitable
    URL suffix to pass to the Flickr API."""
    authentication = False

    # auth may be passed in via the API, AUTH may be set globally (in the same
    # manner as API_KEY, etc). We do a few more checks than may seem necessary
    # because we allow the 'auth' parameter to actually contain the
    # authentication token, not just True/False.
    if auth or AUTH:
        token = userToken()
        authentication = True;
    elif auth != False:
        token = auth;
        authentication = True;
    elif AUTH != False:
        token = AUTH;
        authentication = True;

    # If we're not authenticating, no suffix is required.
    if not authentication:
        return ''

    full_params = params
    full_params['method'] = method

    return '&auth_token=%s&api_sig=%s' % (token, _get_api_sig(full_params) )

def build_photo(photo):
    url = photo.getAttribute('url_o')
    height = photo.getAttribute('height_o')
    width = photo.getAttribute('width_o')
    title = photo.getAttribute('title')
    id = photo.getAttribute('id')
    return (url, height, width, title, id)

def get_min_upload_date(groupid):
    """Figure out the last time this script was run, so we only get recent pictures"""
    if (os.path.exists(CONFIG_FILENAME)):
        config = ConfigObj(CONFIG_FILENAME)
        try: 
            return config[groupid]['min_upload_date']
        except KeyError:
            return '0'
    else:
        return '0'

def set_min_upload_date(groupid):
    config = ConfigObj(CONFIG_FILENAME)
    config[groupid] = {}
    config[groupid]['min_upload_date'] = time()
    config.write()

def get_groups():
    config = ConfigObj(CONFIG_FILENAME)
    return config['groups']

def sanitize_filename(filename):
    import unicodedata
    validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)

def download_photos_from_group(image_root, groupid, min_upload_date):
    print 'Finding pictures for group: ' + groupid + ' since: ' + datetime.fromtimestamp(float(min_upload_date)).strftime("%Y-%m-%d %H:%M:%S")
    photos = photos_search(group_id=groupid, min_upload_date=min_upload_date, extras='url_o, original_format')

    for photo in photos.getElementsByTagName('photo'):
        (url, height, width, title, id) = build_photo(photo)
        if (url != '' and height != '' and int(height) > 900):
            try:
                image = urlopen(url)
                picture = image.read()                
                filename = os.path.join(image_root, id + '-' + sanitize_filename(string.replace(title, ' ', '-')) + url[-4:])
                if not os.path.exists(filename):
                    fout = open(filename, 'wb')
                    fout.write(picture)
                    fout.close()
                    print 'Saved ' + filename
                else:
                    print 'Skipped ' + filename
            except IOError:
                print 'Error on url: ' + url + ', skipping'

def get_image_root():
    config = ConfigObj(CONFIG_FILENAME)
    return config['image_root']

def get_api_key():
    config = ConfigObj(CONFIG_FILENAME)
    return config['api_key']

if __name__ == '__main__':
    sys.exit(main(*sys.argv))
