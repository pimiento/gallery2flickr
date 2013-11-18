import imp
__all__ = ["DOMAIN", "GALLERY", "FAST_MODE", "API_KEY", "SECRET", "TOKEN"]
CONF_FILE = "config"

config = imp.load_source("config", CONF_FILE).__dict__

DOMAIN = config.get('DOMAIN', 'www.example.com')
GALLERY = config.get('GALLERY', '/gallery/v/example/')
FAST_MODE = config.get('FAST_MODE', 0)
API_KEY = config.get('API_KEY', None)
SECRET = config.get('SECRET', None)
TOKEN = config.get('TOKEN', None)
