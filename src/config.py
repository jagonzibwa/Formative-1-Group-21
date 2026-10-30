"""Project-wide paths and settings.

Database credentials are read from environment variables (or a local `.env`
file, see `.env.example`) so that no secrets live in the repository.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT_DIR = Path(__file__).resolve().parents[1]

if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env")

# ---- File locations ---------------------------------------------------------
RAW_DATA_PATH = ROOT_DIR / "data" / "raw" / "Metro_Interstate_Traffic_Volume.csv.gz"
PROCESSED_DATA_PATH = ROOT_DIR / "data" / "processed" / "traffic_hourly_clean.csv.gz"
MODEL_DIR = ROOT_DIR / "models"
MODEL_PATH = MODEL_DIR / "traffic_model.joblib"
MODEL_METADATA_PATH = MODEL_DIR / "model_metadata.json"
FIGURES_DIR = ROOT_DIR / "outputs" / "figures"
QUERY_RESULTS_DIR = ROOT_DIR / "outputs" / "query_results"

# ---- Databases --------------------------------------------------------------
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "traffic_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "metro_traffic")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "metro_traffic")
MONGO_COLLECTION = "traffic_readings"

# ---- API --------------------------------------------------------------------
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def mysql_url(include_db: bool = True) -> str:
    """SQLAlchemy connection URL for MySQL (PyMySQL driver)."""
    from urllib.parse import quote_plus

    db = f"/{MYSQL_DATABASE}" if include_db else ""
    return (
        f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}{db}?charset=utf8mb4"
    )
