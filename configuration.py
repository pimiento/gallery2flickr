import imp
from flickrapi import FlickrAPI
__all__ = ["DOMAIN", "GALLERY", "FAST_MODE", "API_KEY", "SECRET", "TOKEN",
           "USER_ID", "get_flickr"]
CONF_FILE = "config"

config = imp.load_source("config", CONF_FILE).__dict__

DOMAIN = config.get('DOMAIN', 'www.example.com')
GALLERY = config.get('GALLERY', '/gallery/v/example/')
FAST_MODE = config.get('FAST_MODE', 0)
API_KEY = config.get('API_KEY', None)
SECRET = config.get('SECRET', None)
TOKEN = config.get('TOKEN', None)
USER_ID = config.get('USER_ID', None)

def get_flickr(API_KEY, SECRET, TOKEN=None):
    if TOKEN is None:
        flickr = FlickrAPI(API_KEY, SECRET)
        (token, frob) = flickr.get_token_part_one(perms='write')
        if not token:
            raw_input("Press ENTER after you authorized this program")
        flickr.get_token_part_two((token, frob))
    else:
        flickr = FlickrAPI(api_key=API_KEY, secret=SECRET, token=TOKEN)
    return flickr
