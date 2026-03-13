"""
Configuration for the DDR Report Generation System.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = BASE_DIR / "uploads"
EXTRACTED_IMAGES_DIR = OUTPUT_DIR / "extracted_images"

# Create directories
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
EXTRACTED_IMAGES_DIR.mkdir(exist_ok=True)

# ─── Gemini API ──────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# ─── Report Settings ────────────────────────────────────────────────
REPORT_TITLE = "Detailed Diagnostic Report (DDR)"
COMPANY_NAME = "Building Diagnostics & Inspection Services"
MIN_IMAGE_SIZE = 5000  # Minimum image size in bytes to include (filters out tiny artifacts)
MAX_IMAGE_WIDTH = 800  # Max image width in pixels for report embedding

# ─── Flask Settings ──────────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "ddr-report-generator-secret-key-2024")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload
