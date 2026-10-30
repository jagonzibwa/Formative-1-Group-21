"""Conversions between the API record shape and the MongoDB document shape.

API / flat record (same for SQL and MongoDB endpoints):
    {
      "date_time": "2018-09-30T23:00:00",
      "traffic_volume": 954,
      "temp": 282.12, "rain_1h": 0.0, "snow_1h": 0.0, "clouds_all": 90,
      "holiday": null,
      "weather": [{"main": "Clouds", "description": "overcast clouds"}]
    }

MongoDB document (collection `traffic_readings`):
    {
      "_id": ObjectId(...),
      "timestamp": ISODate("2018-09-30T23:00:00Z"),
      "traffic_volume": 954,
      "weather": {"temp_k": 282.12, "rain_1h_mm": 0.0, "snow_1h_mm": 0.0,
                  "clouds_pct": 90,
                  "conditions": [{"main": "Clouds", "description": "overcast clouds"}]},
      "holiday": null,
      "calendar": {"year": 2018, "month": 9, "day": 30, "hour": 23,
                   "day_of_week": 6, "is_weekend": true}
    }
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def calendar_fields(ts: datetime) -> dict[str, Any]:
    """Pre-computed calendar parts so aggregations can group without $dateToParts."""
    return {
        "year": ts.year, "month": ts.month, "day": ts.day, "hour": ts.hour,
        "day_of_week": ts.weekday(),          # Monday = 0
        "is_weekend": ts.weekday() >= 5,
    }


def record_to_document(rec: dict[str, Any]) -> dict[str, Any]:
    ts = rec["date_time"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    ts = ts.replace(tzinfo=None)
    return {
        "timestamp": ts,
        "traffic_volume": int(rec["traffic_volume"]),
        "weather": {
            "temp_k": None if rec.get("temp") is None else float(rec["temp"]),
            "rain_1h_mm": float(rec.get("rain_1h") or 0.0),
            "snow_1h_mm": float(rec.get("snow_1h") or 0.0),
            "clouds_pct": int(rec.get("clouds_all") or 0),
            "conditions": [
                {"main": c["main"], "description": c["description"]}
                for c in rec.get("weather") or []
            ],
        },
        "holiday": rec.get("holiday"),
        "calendar": calendar_fields(ts),
    }


def document_to_record(doc: dict[str, Any]) -> dict[str, Any]:
    w = doc.get("weather", {})
    return {
        "id": str(doc["_id"]) if "_id" in doc else None,
        "date_time": doc["timestamp"],
        "traffic_volume": doc["traffic_volume"],
        "temp": w.get("temp_k"),
        "rain_1h": w.get("rain_1h_mm"),
        "snow_1h": w.get("snow_1h_mm"),
        "clouds_all": w.get("clouds_pct"),
        "holiday": doc.get("holiday"),
        "weather": w.get("conditions", []),
    }
