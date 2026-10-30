"""Task 4 - Forecast the next hour of traffic using records fetched from the API.

Steps
  1. Fetch the latest record and the preceding history from the API
     (GET /{sql|mongo}/records/latest and /{sql|mongo}/records/range)
  2. Preprocess with the *same* pipeline used for training (src/preprocessing.py):
     clean invalid values, de-duplicate, regular hourly grid, short-gap
     interpolation, calendar / weather / lag / moving-average features
  3. Load the trained model (models/traffic_model.joblib)
  4. Predict the traffic volume

Usage (API must be running: uvicorn api.main:app)
  python scripts/predict.py                         # next hour after the latest record (MongoDB)
  python scripts/predict.py --source sql            # same, reading from MySQL
  python scripts/predict.py --at 2018-09-28T17:00   # back-test one hour and compare with the actual value
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import preprocessing as pp  # noqa: E402
from src.config import API_URL, MODEL_METADATA_PATH, MODEL_PATH  # noqa: E402

HISTORY_HOURS = 14 * 24          # two weeks; the features need at least 169 hours
OUTPUT_PATH = ROOT / "outputs" / "latest_forecast.json"


# --------------------------------------------------------------------------- #
# 1. Fetch
# --------------------------------------------------------------------------- #
def api_get(api_url: str, path: str, **params) -> dict:
    try:
        r = requests.get(f"{api_url}{path}", params=params, timeout=60)
    except requests.ConnectionError:
        sys.exit(f"ERROR: cannot reach the API at {api_url}. Start it with: uvicorn api.main:app")
    if r.status_code != 200:
        sys.exit(f"ERROR: GET {path} returned {r.status_code}: {r.text[:300]}")
    return r.json()


def fetch_history(api_url: str, source: str, end: datetime, hours: int) -> list[dict]:
    start = end - timedelta(hours=hours - 1)
    data = api_get(api_url, f"/{source}/records/range",
                   start=start.isoformat(), end=end.isoformat(), limit=10000)
    return data["records"]

