"""Shared preprocessing + feature-engineering pipeline.

The same functions are used by:
  * notebooks/01_eda_preprocessing.ipynb   (exploration)
  * notebooks/02_model_training.ipynb      (training)
  * scripts/predict.py                     (inference on records fetched from the API)

so the model always sees features built in exactly the same way.

Pipeline overview
-----------------
raw rows (one per hour *per weather condition*)
    -> clean_raw()            fix invalid readings, spread holiday to the whole day,
                              collapse duplicate timestamps to one row per hour
    -> to_hourly_grid()       reindex to a regular hourly grid, fill short gaps,
                              flag imputed rows, leave long gaps as NaN
    -> build_features()       calendar, weather, lag and moving-average features
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

TARGET = "traffic_volume"

# Fixed list so one-hot columns are identical at training and inference time.
WEATHER_CATEGORIES = [
    "Clear", "Clouds", "Drizzle", "Fog", "Haze", "Mist",
    "Rain", "Smoke", "Snow", "Squall", "Thunderstorm",
]

# Weather "severity" order used to pick one primary condition when an hour
# has several (e.g. "Rain" + "Mist" -> "Rain").
WEATHER_PRIORITY = [
    "Thunderstorm", "Squall", "Snow", "Rain", "Drizzle",
    "Fog", "Smoke", "Haze", "Mist", "Clouds", "Clear",
]

LAGS = [1, 2, 3, 24, 168]          # 1-3 h (momentum), 1 day, 1 week
ROLLING_WINDOWS = [3, 24, 168]     # moving averages over 3 h, 1 day, 1 week

# Physically impossible readings found during EDA.
MIN_VALID_TEMP_K = 223.15          # -50 C; Minneapolis record low is about -41 C
MAX_VALID_RAIN_MM = 100.0          # one row reports 9831 mm in one hour

# Gaps of up to this many consecutive hours are interpolated.
MAX_INTERP_GAP = 3

NUMERIC_COLS = ["temp", "rain_1h", "snow_1h", "clouds_all", TARGET]


# --------------------------------------------------------------------------- #
# 1. Cleaning
# --------------------------------------------------------------------------- #
def load_raw(path) -> pd.DataFrame:
    """Read the original Kaggle/UCI CSV (gzipped or plain)."""
    df = pd.read_csv(path)
    df["date_time"] = pd.to_datetime(df["date_time"])
    return df


def _primary_weather(conditions: Iterable[str]) -> str:
    conds = set(conditions)
    for w in WEATHER_PRIORITY:
        if w in conds:
            return w
    return "Clouds"


def clean_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw rows into exactly one valid row per observed hour.

    Steps
    1. Invalid sensor values -> NaN (0 K temperatures, the 9831 mm rain value).
    2. `holiday` is only filled at 00:00 in the source data; spread it to all
       24 hours of that date and create a binary `is_holiday`.
    3. Duplicate timestamps (one row per weather condition) are merged:
       numeric columns are averaged (they are identical or near-identical),
       and the most severe weather condition is kept as `weather_main`.
    """
    df = df.copy()
    df["date_time"] = pd.to_datetime(df["date_time"])

    df.loc[df["temp"] < MIN_VALID_TEMP_K, "temp"] = np.nan
    df.loc[df["rain_1h"] > MAX_VALID_RAIN_MM, "rain_1h"] = np.nan

    df["holiday"] = df["holiday"].replace({"None": np.nan})
    day = df["date_time"].dt.normalize()
    holiday_by_day = df.dropna(subset=["holiday"]).groupby(day)["holiday"].first()
    df["holiday"] = day.map(holiday_by_day)

    agg = (
        df.groupby("date_time")
        .agg(
            temp=("temp", "mean"),
            rain_1h=("rain_1h", "mean"),
            snow_1h=("snow_1h", "mean"),
            clouds_all=("clouds_all", "mean"),
            traffic_volume=(TARGET, "mean"),
            holiday=("holiday", "first"),
            weather_main=("weather_main", _primary_weather),
            n_conditions=("weather_main", "size"),
        )
        .sort_index()
    )
    agg["is_holiday"] = agg["holiday"].notna().astype(int)
    return agg


# --------------------------------------------------------------------------- #
# 2. Regular hourly grid + missing values
# --------------------------------------------------------------------------- #
def _gap_lengths(missing: pd.Series) -> pd.Series:
    """For every NaN position, the length of the NaN run it belongs to."""
    run_id = (missing != missing.shift()).cumsum()
    run_len = missing.groupby(run_id).transform("size")
    return run_len.where(missing, 0)


def to_hourly_grid(hourly: pd.DataFrame, max_gap: int = MAX_INTERP_GAP) -> pd.DataFrame:
    """Reindex to a complete hourly index and handle missing hours.

    * Gaps of <= `max_gap` hours: numeric columns are linearly interpolated in
      time, categorical columns are forward-filled. These rows get
      `is_imputed = 1`.
    * Longer gaps are left as NaN. They are *not* invented, because filling
      days or months of traffic would create fake patterns; rows whose lag
      features touch such a gap are dropped later by `build_features`.
    * Isolated invalid readings inside observed hours (e.g. a 0 K temperature)
      are interpolated with the same rule.
    """
    full_index = pd.date_range(hourly.index.min(), hourly.index.max(), freq="h")
    grid = hourly.reindex(full_index)
    grid.index.name = "date_time"

    hour_missing = grid[TARGET].isna()
    short_gap = hour_missing & (_gap_lengths(hour_missing) <= max_gap)

    for col in NUMERIC_COLS:
        col_missing = grid[col].isna()
        fillable = col_missing & (_gap_lengths(col_missing) <= max_gap)
        interpolated = grid[col].interpolate(method="time", limit_area="inside")
        grid.loc[fillable, col] = interpolated[fillable]

    for col in ["weather_main"]:
        grid.loc[short_gap, col] = grid[col].ffill()[short_gap]

    # Holiday is a calendar property, so it can be derived for any hour.
    day = grid.index.normalize()
    known = grid["holiday"].groupby(day).first()
    grid["holiday"] = pd.Series(day, index=grid.index).map(known)
    grid["is_holiday"] = grid["holiday"].notna().astype(int)

    grid["n_conditions"] = grid["n_conditions"].fillna(1)
    grid["is_imputed"] = short_gap.astype(int)
    return grid


# --------------------------------------------------------------------------- #
# 3. Feature engineering
# --------------------------------------------------------------------------- #
def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index
    df["hour"] = idx.hour
    df["day_of_week"] = idx.dayofweek          # Monday = 0
    df["month"] = idx.month
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    # Cyclical encodings so 23:00 is "close" to 00:00 for linear models.
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    return df


def add_weather_features(df: pd.DataFrame) -> pd.DataFrame:
    df["temp_c"] = df["temp"] - 273.15
    for cat in WEATHER_CATEGORIES:
        df[f"weather_{cat.lower()}"] = (df["weather_main"] == cat).astype(int)
    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lagged target values and moving averages.

    Everything is shifted by at least one hour, so a row only uses traffic that
    was already known *before* the hour being predicted (no leakage).
    """
    y = df[TARGET]
    for lag in LAGS:
        df[f"lag_{lag}"] = y.shift(lag)
    past = y.shift(1)
    for w in ROLLING_WINDOWS:
        df[f"roll_mean_{w}"] = past.rolling(w, min_periods=w).mean()
    df["roll_std_24"] = past.rolling(24, min_periods=24).std()
    return df


FEATURE_COLUMNS = (
    ["hour", "day_of_week", "month", "is_weekend", "is_holiday",
     "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
    + ["temp_c", "rain_1h", "snow_1h", "clouds_all"]
    + [f"weather_{c.lower()}" for c in WEATHER_CATEGORIES]
    + [f"lag_{l}" for l in LAGS]
    + [f"roll_mean_{w}" for w in ROLLING_WINDOWS]
    + ["roll_std_24"]
)


def build_features(grid: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """Add all model features to a regular hourly grid.

    With `dropna=True` rows with a missing target or feature are removed
    (training). With `dropna=False` they are kept (inference, where the
    last row has no target yet).
    """
    df = grid.copy()
    df = add_calendar_features(df)
    df = add_weather_features(df)
    df = add_lag_features(df)
    if dropna:
        df = df.dropna(subset=FEATURE_COLUMNS + [TARGET])
    return df


def preprocess(raw: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """Full pipeline: raw rows -> feature table."""
    return build_features(to_hourly_grid(clean_raw(raw)), dropna=dropna)


# --------------------------------------------------------------------------- #
# 4. Inference helpers (used by scripts/predict.py)
# --------------------------------------------------------------------------- #
def records_to_raw_frame(records: list[dict]) -> pd.DataFrame:
    """Convert API JSON records into the raw-CSV column layout.

    An API record holds a *list* of weather conditions; it is expanded to one
    row per condition, exactly like the original CSV, so `clean_raw` can be
    reused unchanged.
    """
    rows = []
    for r in records:
        conditions = r.get("weather") or [{"main": "Clouds", "description": "unknown"}]
        for c in conditions:
            rows.append({
                "holiday": r.get("holiday"),
                "temp": r.get("temp"),
                "rain_1h": r.get("rain_1h"),
                "snow_1h": r.get("snow_1h"),
                "clouds_all": r.get("clouds_all"),
                "weather_main": c.get("main"),
                "weather_description": c.get("description"),
                "date_time": r.get("date_time"),
                TARGET: r.get(TARGET),
            })
    df = pd.DataFrame(rows)
    df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_localize(None)
    for col in ["temp", "rain_1h", "snow_1h", "clouds_all", TARGET]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _federal_holiday_name(ts: pd.Timestamp) -> str | None:
    cal = USFederalHolidayCalendar()
    hols = cal.holidays(start=ts.normalize(), end=ts.normalize(), return_name=True)
    return None if hols.empty else str(hols.iloc[0])


def next_hour_features(grid: pd.DataFrame) -> pd.DataFrame:
    """Build the feature row for the hour right after the last observation.

    Weather for the next hour is unknown, so the latest observed weather is
    carried forward (persistence forecast). Holidays for the new hour come from
    the data if it is the same day, otherwise from the US federal calendar.
    """
    last_ts = grid.index.max()
    next_ts = last_ts + pd.Timedelta(hours=1)
    new_row = grid.iloc[[-1]].copy()
    new_row.index = pd.DatetimeIndex([next_ts], name="date_time")
    new_row[TARGET] = np.nan
    new_row["is_imputed"] = 0
    if next_ts.normalize() != last_ts.normalize():
        name = _federal_holiday_name(next_ts)
        new_row["holiday"] = name
        new_row["is_holiday"] = int(name is not None)
    extended = pd.concat([grid, new_row])
    feats = build_features(extended, dropna=False)
    return feats.iloc[[-1]]
