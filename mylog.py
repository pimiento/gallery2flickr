import logging
__all__ = ["my_log", "LOG_FILE"]

LOG_FILE = "logging"

logger = logging.getLogger('i2s')
formatter = logging.Formatter("%(asctime)s-:-%(message)s")
hndler = logging.FileHandler(LOG_FILE)
hndler.setFormatter(formatter)
logger.addHandler(hndler)
logger.setLevel(logging.INFO)

def my_log(text, filename=LOG_FILE):
    text = text.replace('\n', '\\n')
    logger.info(text)
