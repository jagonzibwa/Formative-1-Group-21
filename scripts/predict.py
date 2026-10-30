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


# --------------------------------------------------------------------------- #
# 2. Preprocess
# --------------------------------------------------------------------------- #
def build_grid(records: list[dict]) -> pd.DataFrame:
    raw = pp.records_to_raw_frame(records)
    return pp.to_hourly_grid(pp.clean_raw(raw))


def features_for(grid: pd.DataFrame, target_ts: pd.Timestamp | None) -> pd.DataFrame:
    """Feature row for `target_ts` (back-test) or for the hour after the last record."""
    if target_ts is None:
        return pp.next_hour_features(grid)
    g = grid.copy()
    g.loc[target_ts, pp.TARGET] = np.nan        # hide the actual value from the features
    return pp.build_features(g, dropna=False).loc[[target_ts]]


# --------------------------------------------------------------------------- #
# 3. Load model
# --------------------------------------------------------------------------- #
def load_model():
    if not MODEL_PATH.exists():
        sys.exit(f"ERROR: {MODEL_PATH} not found - run notebooks/02_model_training.ipynb first")
    model = joblib.load(MODEL_PATH)
    meta = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))
    if meta["features"] != pp.FEATURE_COLUMNS:
        sys.exit("ERROR: model features do not match src/preprocessing.FEATURE_COLUMNS - retrain the model")
    return model, meta


# --------------------------------------------------------------------------- #
# 4. Predict
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["mongo", "sql"], default="mongo", help="database behind the API")
    ap.add_argument("--api-url", default=API_URL)
    ap.add_argument("--at", help="back-test: forecast this hour (ISO time) from the history before it")
    ap.add_argument("--history-hours", type=int, default=HISTORY_HOURS)
    args = ap.parse_args()

    print(f"[1/4] Fetching data from {args.api_url}/{args.source}/records ...")
    if args.at:
        target_ts = pd.Timestamp(args.at).floor("h")
        records = fetch_history(args.api_url, args.source, target_ts.to_pydatetime(), args.history_hours + 1)
        if not records or pd.Timestamp(records[-1]["date_time"]) != target_ts:
            sys.exit(f"ERROR: no record at {target_ts} to back-test against")
        actual = records[-1]["traffic_volume"]
    else:
        latest = api_get(args.api_url, f"/{args.source}/records/latest")
        print(f"      latest record: {latest['date_time']}  volume={latest['traffic_volume']}")
        records = fetch_history(args.api_url, args.source, datetime.fromisoformat(latest["date_time"]),
                                args.history_hours)
        target_ts, actual = None, None
    print(f"      fetched {len(records)} hourly records "
          f"({records[0]['date_time']} -> {records[-1]['date_time']})")

    print("[2/4] Preprocessing (clean -> hourly grid -> lag / moving-average features) ...")
    grid = build_grid(records)
    print(f"      grid: {len(grid)} hours, {int(grid.is_imputed.sum())} imputed, "
          f"{int(grid[pp.TARGET].isna().sum())} still missing")
    X = features_for(grid, target_ts)
    missing = X[pp.FEATURE_COLUMNS].columns[X[pp.FEATURE_COLUMNS].isna().any()].tolist()
    if missing:
        sys.exit(f"ERROR: not enough continuous history to build {missing}. "
                 f"Try a larger --history-hours or a time without long data gaps.")

    print("[3/4] Loading model ...")
    model, meta = load_model()
    print(f"      {meta['model']} (experiment {meta['experiment']}, test MAE {meta['test_metrics']['test_mae']} veh/h)")

    print("[4/4] Forecasting ...")
    pred = float(model.predict(X[pp.FEATURE_COLUMNS])[0])
    ts = X.index[0]
    row = X.iloc[0]
    result = {
        "forecast_for": ts.isoformat(),
        "predicted_traffic_volume": round(pred),
        "source": args.source,
        "model": meta["model"],
        "context": {
            "last_hour_volume": None if pd.isna(row["lag_1"]) else int(row["lag_1"]),
            "same_hour_last_week": None if pd.isna(row["lag_168"]) else int(row["lag_168"]),
            "avg_last_24h": round(float(row["roll_mean_24"])),
            "weather_used": row["weather_main"],
            "is_holiday": bool(row["is_holiday"]),
            "weather_assumption": "observed weather for that hour" if target_ts is not None
                                  else "persistence (latest observed weather carried forward)",
        },
    }
    if actual is not None:
        result["actual_traffic_volume"] = int(actual)
        result["absolute_error"] = round(abs(pred - actual))

    print("\n" + "=" * 60)
    print(f" Forecast for {ts:%A %d %b %Y, %H:%M}")
    print(f"   predicted traffic volume : {round(pred):>6,} vehicles/hour")
    if actual is not None:
        print(f"   actual traffic volume    : {int(actual):>6,} vehicles/hour  (error {abs(pred - actual):,.0f})")
    print(f"   previous hour            : {result['context']['last_hour_volume']:>6,}")
    print(f"   same hour last week      : {result['context']['same_hour_last_week']:>6,}")
    print("=" * 60)

    OUTPUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved -> {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
