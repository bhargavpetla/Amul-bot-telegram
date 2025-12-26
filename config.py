import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Amul API Configuration
AMUL_BASE_URL = "https://shop.amul.com"
AMUL_PROTEIN_URL = f"{AMUL_BASE_URL}/en/browse/protein"
AMUL_API_URL = f"{AMUL_BASE_URL}/api/1/entity/ms.products"
AMUL_PINCODE_URL = f"{AMUL_BASE_URL}/entity/pincode"
AMUL_PREFERENCES_URL = f"{AMUL_BASE_URL}/entity/ms.settings/_/setPreferences"

# Database
DATABASE_PATH = "amul_bot.db"

# Stock Check Interval (in minutes) - 0.5 = 30 seconds
STOCK_CHECK_INTERVAL = 0.5

# Request Headers
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "referer": "https://shop.amul.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}
