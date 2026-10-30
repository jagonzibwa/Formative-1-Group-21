"""Database helpers shared by the loaders, the query runner and the API.

* `mysql_engine()` / `mongo_collection()` open connections using src/config.py.
* `split_raw_for_db()` turns the raw CSV into the four relational tables.
* `hourly_documents()` turns the raw CSV into one MongoDB document per hour.

Both databases store the *raw* recorded values (one hour, its traffic count
and every weather report in that hour). Cleaning and feature engineering stay
in src/preprocessing.py, so the prediction script can fetch raw records from
the API and preprocess them exactly like the training data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


# --------------------------------------------------------------------------- #
# Connections
# --------------------------------------------------------------------------- #
def mysql_engine(include_db: bool = True):
    """SQLAlchemy engine for MySQL (PyMySQL driver)."""
    from sqlalchemy import create_engine

    return create_engine(config.mysql_url(include_db), pool_pre_ping=True)


def mongo_client():
    from pymongo import MongoClient

    return MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)


def mongo_collection(client=None):
    """The `traffic_readings` collection."""
    client = client or mongo_client()
    return client[config.MONGO_DATABASE][config.MONGO_COLLECTION]


# --------------------------------------------------------------------------- #
# Raw CSV -> database rows
# --------------------------------------------------------------------------- #
def load_raw_for_db(path=config.RAW_DATA_PATH) -> pd.DataFrame:
    """Read the raw CSV and remove the 17 rows that are exact duplicates.

    Rows that share a timestamp but differ in weather are *kept*: they are
    separate weather reports for the same hour.

    Weather descriptions are lower-cased first: the source spells one
    condition both "Sky is Clear" and "sky is clear" (and "SQUALLS").
    """
    raw = pd.read_csv(path)
    raw["weather_description"] = raw["weather_description"].str.lower()
    raw = raw.drop_duplicates().reset_index(drop=True)
    raw["date_time"] = pd.to_datetime(raw["date_time"])
    raw["holiday"] = raw["holiday"].replace({"None": np.nan})
    return raw


def split_raw_for_db(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split raw rows into holidays, weather_conditions, traffic_readings and
    weather_observations, with IDs assigned so the foreign keys line up."""
    # holidays: the source labels only the 00:00 row of each holiday date
    holidays = (
        raw.dropna(subset=["holiday"])
        .assign(holiday_date=lambda d: d["date_time"].dt.date)
        .groupby("holiday_date", as_index=False)["holiday"].first()
        .rename(columns={"holiday": "holiday_name"})
        .sort_values("holiday_date")
        .reset_index(drop=True)
    )
    holidays.insert(0, "holiday_id", np.arange(1, len(holidays) + 1))

    conditions = (
        raw[["weather_main", "weather_description"]]
        .drop_duplicates()
        .sort_values(["weather_main", "weather_description"])
        .rename(columns={"weather_main": "main", "weather_description": "description"})
        .reset_index(drop=True)
    )
    conditions.insert(0, "condition_id", np.arange(1, len(conditions) + 1))

    # traffic_readings: one row per hour; traffic is identical within an hour
    readings = (
        raw.groupby("date_time", as_index=False)["traffic_volume"].first()
        .sort_values("date_time")
        .reset_index(drop=True)
    )
    readings.insert(0, "reading_id", np.arange(1, len(readings) + 1))
    holiday_by_date = dict(zip(holidays["holiday_date"], holidays["holiday_id"]))
    readings["holiday_id"] = (
        readings["date_time"].dt.date.map(holiday_by_date).astype("Int64")
    )

    # weather_observations: every remaining raw row is one weather report
    obs = raw.merge(readings[["reading_id", "date_time"]], on="date_time").merge(
        conditions,
        left_on=["weather_main", "weather_description"],
        right_on=["main", "description"],
    )
    observations = (
        obs[["reading_id", "condition_id", "temp", "rain_1h", "snow_1h", "clouds_all"]]
        .sort_values(["reading_id", "condition_id"])
        .reset_index(drop=True)
    )
    observations.insert(0, "observation_id", np.arange(1, len(observations) + 1))

    return {
        "holidays": holidays,
        "weather_conditions": conditions,
        "traffic_readings": readings,
        "weather_observations": observations,
    }


def hourly_documents(raw: pd.DataFrame) -> list[dict]:
    """One MongoDB document per hour, in the API record shape that
    `preprocessing.records_to_raw_frame()` expects.

    Weather values are averaged over the hour's reports (the same rule as
    `clean_raw()`); the individual conditions are kept in the `weather` array.
    """
    tables = split_raw_for_db(raw)
    hol = tables["holidays"].set_index("holiday_id")["holiday_name"]
    readings = tables["traffic_readings"]
    obs = tables["weather_observations"].merge(tables["weather_conditions"], on="condition_id")

    weather_avg = obs.groupby("reading_id")[["temp", "rain_1h", "snow_1h", "clouds_all"]].mean()
    weather_list = obs.groupby("reading_id").apply(
        lambda g: [{"main": m, "description": d} for m, d in zip(g["main"], g["description"])],
        include_groups=False,
    )

    docs = []
    for row in readings.itertuples(index=False):
        w = weather_avg.loc[row.reading_id]
        docs.append({
            "date_time": row.date_time.to_pydatetime(),
            "traffic_volume": int(row.traffic_volume),
            "holiday": None if pd.isna(row.holiday_id) else hol[row.holiday_id],
            "temp": round(float(w["temp"]), 2),
            "rain_1h": round(float(w["rain_1h"]), 2),
            "snow_1h": round(float(w["snow_1h"]), 2),
            "clouds_all": int(round(w["clouds_all"])),
            "weather": weather_list[row.reading_id],
            "source": "csv_import",
        })
    return docs
