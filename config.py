import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Database directory
DB_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DB_DIR, exist_ok=True)

# USB Drive configuration (for production)
USB_MOUNT_PATH = os.getenv("USB_MOUNT_PATH", os.path.join(BASE_DIR, "data", "usbdrive"))
USB_DB_PATH = os.path.join(USB_MOUNT_PATH, "pos_db.sqlite")

# Use local database by default, USB path if USB_STORAGE is enabled
USE_USB_STORAGE = os.getenv("USE_USB_STORAGE", "false").lower() == "true"
DB_PATH = USB_DB_PATH if USE_USB_STORAGE else os.path.join(DB_DIR, "pos_db.sqlite")

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Square API configuration
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")  # Change to 'production' in prod

# Printer configuration
RECEIPT_PRINTER_ENABLED = os.getenv("RECEIPT_PRINTER_ENABLED", "true").lower() == "true"
KITCHEN_SCREEN_ENABLED = os.getenv("KITCHEN_SCREEN_ENABLED", "true").lower() == "true"

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")  # Change in production
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24 hours

# Database
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(BASE_DIR, "logs", "pos_backend.log")

# Create required directories
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True) 