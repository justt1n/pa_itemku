import codecs
import json
import os

KEY_PATH = "key.json"
DATA_PATH = "storage/output.json"
RETRIES_TIME = 20
DEFAULT_URL = "https://www.bijiaqi.com/"

SHEET_NAME = "Sheet1"
BLACKLIST_SHEET_NAME = "Blacklist"
DESTINATION_RANGE = "G{n}:Q{n}"
INFORMATION_RANGE = "G{n}:H{n}"
TIMEOUT = 15
REFRESH_TIME = 10
LOG_FILE = "function_calls.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(message)s"


def read_file_with_encoding(file_path, encoding='utf-8'):
    try:
        with codecs.open(file_path, 'r', encoding=encoding) as file:
            content = json.load(file)
        return content
    except UnicodeDecodeError as e:
        print(f"Error decoding file: {e}")
        return None


BIJ_HOST_DATA = read_file_with_encoding(DATA_PATH, encoding='utf-8')

TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "storage", "pa_template")
