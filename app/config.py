import os

SA_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
DB_PATH = os.environ.get("DB_PATH", "data/app.db")
