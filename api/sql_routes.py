"""CRUD + time-series endpoints backed by MySQL (schema: database/mysql/schema.sql).

Reads use the view `v_hourly_readings`, which already returns one row per hour
in the API record shape (weather values averaged over the hour's reports).

Writes touch up to four tables in one transaction:
    traffic_readings      (the hourly row: date_time, traffic_volume, holiday_id)
    weather_observations  (one row per weather condition reported in that hour)
    weather_conditions    (created on first use of a new main/description pair)
    holidays              (created on first use of a new holiday date)
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from .db import sql_engine
from .schemas import (DeleteResult, RecordList, TrafficRecord, TrafficRecordCreate,
                      TrafficRecordUpdate)

router = APIRouter(prefix="/sql/records", tags=["SQL (MySQL)"])

WEATHER_FIELDS = ["temp", "rain_1h", "snow_1h", "clouds_all", "weather"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _fetch(conn: Connection, where: str = "", params: Optional[dict] = None,
           order: str = "r.date_time DESC", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Pick the reading ids on the indexed base table, then read those hours from the view."""
    sql = f"SELECT r.reading_id FROM traffic_readings r {where} ORDER BY {order} LIMIT :limit OFFSET :offset"
    ids = conn.execute(text(sql), {**(params or {}), "limit": limit, "offset": offset}).scalars().all()
    if not ids:
        return []
    view_sql = text("""
        SELECT reading_id, date_time, traffic_volume, holiday, temp, rain_1h, snow_1h, clouds_all, weather
        FROM v_hourly_readings WHERE reading_id IN :ids
    """).bindparams(bindparam("ids", expanding=True))
    rows = {r["reading_id"]: r for r in conn.execute(view_sql, {"ids": list(ids)}).mappings()}
    records = []
    for i in ids:
        r = rows[i]
        weather = json.loads(r["weather"]) if isinstance(r["weather"], str) else (r["weather"] or [])
        records.append({
            "id": r["reading_id"],
            "date_time": r["date_time"],
            "traffic_volume": r["traffic_volume"],
            "temp": None if r["temp"] is None else float(r["temp"]),
            "rain_1h": float(r["rain_1h"] or 0),
            "snow_1h": float(r["snow_1h"] or 0),
            "clouds_all": None if r["clouds_all"] is None else int(r["clouds_all"]),
            "holiday": r["holiday"],
            # LEFT JOIN gives {main: null} when an hour has no observations
            "weather": [w for w in weather if w.get("main") is not None],
        })
    return records


def _get_one(conn: Connection, record_id: int) -> dict[str, Any]:
    rows = _fetch(conn, "WHERE r.reading_id = :id", {"id": record_id}, limit=1)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
    return rows[0]


def _holiday_id(conn: Connection, name: Optional[str], ts: datetime) -> Optional[int]:
    """Get or create the holidays row for this date."""
    if not name:
        return None
    conn.execute(text("""
        INSERT INTO holidays (holiday_date, holiday_name) VALUES (:d, :n)
        ON DUPLICATE KEY UPDATE holiday_name = VALUES(holiday_name)
    """), {"d": ts.date(), "n": name})
    return conn.execute(text("SELECT holiday_id FROM holidays WHERE holiday_date = :d"), {"d": ts.date()}).scalar_one()


def _set_weather(conn: Connection, reading_id: int, rec: dict[str, Any]) -> None:
    """Replace the weather observations of a reading: one row per condition,
    each carrying the hour's temp / rain / snow / clouds values."""
    conn.execute(text("DELETE FROM weather_observations WHERE reading_id = :id"), {"id": reading_id})
    seen = set()
    for c in rec["weather"]:
        key = (c["main"], c["description"])
        if key in seen:
            continue
        seen.add(key)
        conn.execute(text("""
            INSERT IGNORE INTO weather_conditions (main, description) VALUES (:m, :d)
        """), {"m": c["main"], "d": c["description"]})
        cid = conn.execute(text("""
            SELECT condition_id FROM weather_conditions WHERE main = :m AND description = :d
        """), {"m": c["main"], "d": c["description"]}).scalar_one()
        conn.execute(text("""
            INSERT INTO weather_observations (reading_id, condition_id, temp, rain_1h, snow_1h, clouds_all)
            VALUES (:r, :c, :temp, :rain_1h, :snow_1h, :clouds_all)
        """), {"r": reading_id, "c": cid, "temp": rec["temp"], "rain_1h": rec["rain_1h"],
               "snow_1h": rec["snow_1h"], "clouds_all": rec["clouds_all"]})


# --------------------------------------------------------------------------- #
# CREATE
# --------------------------------------------------------------------------- #
@router.post("", response_model=TrafficRecord, status_code=status.HTTP_201_CREATED,
             summary="Create an hourly record")
def create_record(body: TrafficRecordCreate):
    data = body.model_dump()
    try:
        with sql_engine().begin() as conn:
            hid = _holiday_id(conn, data["holiday"], data["date_time"])
            result = conn.execute(text("""
                INSERT INTO traffic_readings (date_time, traffic_volume, holiday_id)
                VALUES (:date_time, :traffic_volume, :hid)
            """), {**data, "hid": hid})
            new_id = result.lastrowid
            _set_weather(conn, new_id, data)
            return _get_one(conn, new_id)
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A record for {data['date_time']} already exists")


# --------------------------------------------------------------------------- #
# READ (time-series routes are declared before /{record_id})
# --------------------------------------------------------------------------- #
@router.get("", response_model=RecordList, summary="List records (newest first, paginated)")
def list_records(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    with sql_engine().connect() as conn:
        recs = _fetch(conn, limit=limit, offset=offset)
    return {"count": len(recs), "records": recs}


@router.get("/latest", response_model=TrafficRecord, summary="Latest record (most recent hour)")
def latest_record():
    with sql_engine().connect() as conn:
        recs = _fetch(conn, limit=1)
    if not recs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No records")
    return recs[0]


@router.get("/range", response_model=RecordList, summary="Records in a date range (oldest first)")
def records_in_range(start: datetime = Query(..., examples=["2018-09-24T00:00:00"]),
                     end: datetime = Query(..., examples=["2018-09-30T23:00:00"]),
                     limit: int = Query(1000, ge=1, le=10000)):
    if start > end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "start must be <= end")
    with sql_engine().connect() as conn:
        recs = _fetch(conn, "WHERE r.date_time BETWEEN :start AND :end",
                      {"start": start.replace(tzinfo=None), "end": end.replace(tzinfo=None)},
                      order="r.date_time ASC", limit=limit)
    return {"count": len(recs), "records": recs}


@router.get("/{record_id}", response_model=TrafficRecord, summary="Get one record by reading_id")
def get_record(record_id: int):
    with sql_engine().connect() as conn:
        return _get_one(conn, record_id)


# --------------------------------------------------------------------------- #
# UPDATE
# --------------------------------------------------------------------------- #
@router.put("/{record_id}", response_model=TrafficRecord, summary="Update a record (only the fields sent)")
def update_record(record_id: int, body: TrafficRecordUpdate):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    try:
        with sql_engine().begin() as conn:
            current = _get_one(conn, record_id)
            merged = {**current, **changes}
            sets = {k: merged[k] for k in ["date_time", "traffic_volume"]}
            if "holiday" in changes or "date_time" in changes:
                sets["holiday_id"] = _holiday_id(conn, merged["holiday"], merged["date_time"])
            assignments = ", ".join(f"{k} = :{k}" for k in sets)
            conn.execute(text(f"UPDATE traffic_readings SET {assignments} WHERE reading_id = :id"),
                         {**sets, "id": record_id})
            if any(f in changes for f in WEATHER_FIELDS):
                _set_weather(conn, record_id, merged)
            return _get_one(conn, record_id)
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Another record already uses that date_time")


# --------------------------------------------------------------------------- #
# DELETE
# --------------------------------------------------------------------------- #
@router.delete("/{record_id}", response_model=DeleteResult, summary="Delete a record")
def delete_record(record_id: int):
    with sql_engine().begin() as conn:
        current = _get_one(conn, record_id)
        # weather_observations rows are removed by ON DELETE CASCADE
        conn.execute(text("DELETE FROM traffic_readings WHERE reading_id = :id"), {"id": record_id})
    return {"deleted": True, "record": current}
