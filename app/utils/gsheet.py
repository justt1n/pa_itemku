import os

from dotenv import load_dotenv
from gspread.auth import service_account

from app.utils.paths import SRC_PATH

load_dotenv("setting.env")
g_client = service_account(SRC_PATH.joinpath(os.getenv("KEYS_PATH")))

spreadsheet = g_client.open_by_key(os.environ["SPREADSHEET_KEY"])

worksheet = spreadsheet.worksheet(os.environ["SHEET_NAME"])
