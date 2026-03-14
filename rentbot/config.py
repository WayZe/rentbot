"""
Configuration and constants for rentbot application.
"""
import os
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_MONTHLY_RENT = Decimal("47700.00")

# Admin system
ADMIN_USER_IDS = set(map(int, os.getenv("ADMIN_USER_IDS", "").split(","))) if os.getenv("ADMIN_USER_IDS") else set()

# Database configuration
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

# Event types
EVENT_RENT_CHARGE = "rent_charge"
EVENT_UTILITY_CHARGE = "utility_charge"
EVENT_TENANT_PAYMENT = "tenant_payment"

# Button texts
BUTTON_BALANCE = "📊 Текущий долг"
BUTTON_TENANT_PAYMENT = "💰 Внести платёж жильца"
BUTTON_UTILITY_CHARGE = "🧾 Внести ЖКХ"
BUTTON_HISTORY = "📜 Получить историю"
BUTTON_DB_RESTORE = "🔄 Восстановить БД"