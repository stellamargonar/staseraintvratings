import os

DATABASE_URL = os.getenv("DATABASE_URL", "")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "")

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "")