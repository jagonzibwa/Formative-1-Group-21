"""CRUD + time-series endpoints backed by MySQL.

Writes touch up to four tables in one transaction:
    traffic_observations  (the hourly row)
    observation_weather   (its weather conditions)
    weather_conditions    (created on first use of a new condition)
    holidays              (created on first use of a new holiday date)
"""
from __future__ import annotations

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

_SELECT = """
    SELECT o.observation_id, o.date_time, o.traffic_volume, o.temp, o.rain_1h,
           o.snow_1h, o.clouds_all, h.holiday_name
    FROM traffic_observations o
    LEFT JOIN holidays h ON h.holiday_id = o.holiday_id
"""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _fetch(conn: Connection, where: str = "", params: Optional[dict] = None,
           order: str = "o.date_time DESC", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Read observations, then their weather conditions in one extra query."""
    sql = f"{_SELECT} {where} ORDER BY {order} LIMIT :limit OFFSET :offset"
    rows = conn.execute(text(sql), {**(params or {}), "limit": limit, "offset": offset}).mappings().all()
    if not rows:
        return []
    ids = [r["observation_id"] for r in rows]
    cond_sql = text("""
        SELECT ow.observation_id, wc.weather_main, wc.weather_description
        FROM observation_weather ow JOIN weather_conditions wc ON wc.condition_id = ow.condition_id
        WHERE ow.observation_id IN :ids ORDER BY ow.observation_id, ow.condition_rank
    """).bindparams(bindparam("ids", expanding=True))
    weather: dict[int, list] = {i: [] for i in ids}
    for c in conn.execute(cond_sql, {"ids": ids}).mappings():
        weather[c["observation_id"]].append({"main": c["weather_main"], "description": c["weather_description"]})
    return [{
        "id": r["observation_id"],
        "date_time": r["date_time"],
        "traffic_volume": r["traffic_volume"],
        "temp": None if r["temp"] is None else float(r["temp"]),
        "rain_1h": float(r["rain_1h"]),
        "snow_1h": float(r["snow_1h"]),
        "clouds_all": r["clouds_all"],
        "holiday": r["holiday_name"],
        "weather": weather[r["observation_id"]],
    } for r in rows]


def _get_one(conn: Connection, record_id: int) -> dict[str, Any]:
    rows = _fetch(conn, "WHERE o.observation_id = :id", {"id": record_id}, limit=1)
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


def _set_weather(conn: Connection, observation_id: int, conditions: list[dict]) -> None:
    """Replace the weather conditions of an observation (get-or-create lookups)."""
    conn.execute(text("DELETE FROM observation_weather WHERE observation_id = :id"), {"id": observation_id})
    seen = set()
    for rank, c in enumerate(conditions, start=1):
        key = (c["main"], c["description"])
        if key in seen:
            continue
        seen.add(key)
        conn.execute(text("""
            INSERT IGNORE INTO weather_conditions (weather_main, weather_description) VALUES (:m, :d)
        """), {"m": c["main"], "d": c["description"]})
        cid = conn.execute(text("""
            SELECT condition_id FROM weather_conditions WHERE weather_main = :m AND weather_description = :d
        """), {"m": c["main"], "d": c["description"]}).scalar_one()
        conn.execute(text("""
            INSERT INTO observation_weather (observation_id, condition_id, condition_rank) VALUES (:o, :c, :r)
        """), {"o": observation_id, "c": cid, "r": rank})


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
                INSERT INTO traffic_observations
                    (date_time, traffic_volume, temp, rain_1h, snow_1h, clouds_all, holiday_id)
                VALUES (:date_time, :traffic_volume, :temp, :rain_1h, :snow_1h, :clouds_all, :hid)
            """), {**data, "hid": hid})
            new_id = result.lastrowid
            _set_weather(conn, new_id, data["weather"])
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
        recs = _fetch(conn, "WHERE o.date_time BETWEEN :start AND :end",
                      {"start": start.replace(tzinfo=None), "end": end.replace(tzinfo=None)},
                      order="o.date_time ASC", limit=limit)
    return {"count": len(recs), "records": recs}


@router.get("/{record_id}", response_model=TrafficRecord, summary="Get one record by id")
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
            sets = {k: merged[k] for k in ["date_time", "traffic_volume", "temp", "rain_1h", "snow_1h", "clouds_all"]}
            if "holiday" in changes or "date_time" in changes:
                sets["holiday_id"] = _holiday_id(conn, merged["holiday"], merged["date_time"])
            assignments = ", ".join(f"{k} = :{k}" for k in sets)
            conn.execute(text(f"UPDATE traffic_observations SET {assignments} WHERE observation_id = :id"),
                         {**sets, "id": record_id})
            if "weather" in changes:
                _set_weather(conn, record_id, merged["weather"])
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
        # observation_weather rows are removed by ON DELETE CASCADE
        conn.execute(text("DELETE FROM traffic_observations WHERE observation_id = :id"), {"id": record_id})
    return {"deleted": True, "record": current}
