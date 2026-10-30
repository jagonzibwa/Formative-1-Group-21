"""Request / response models shared by the SQL and MongoDB endpoints.

Both databases expose exactly the same record shape, so a client (e.g.
scripts/predict.py) can switch between `/sql` and `/mongo` without changes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WeatherCondition(BaseModel):
    main: str = Field(..., min_length=1, max_length=20, examples=["Clouds"])
    description: str = Field(..., min_length=1, max_length=50, examples=["overcast clouds"])


def _naive(v: datetime) -> datetime:
    """Store local wall-clock time without tz info (the dataset is local time)."""
    if isinstance(v, datetime) and v.tzinfo is not None:
        v = v.replace(tzinfo=None)
    return v.replace(minute=0, second=0, microsecond=0) if isinstance(v, datetime) else v


class TrafficRecordCreate(BaseModel):
    """Body for POST: one hourly observation."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "date_time": "2018-10-01T00:00:00",
        "traffic_volume": 620,
        "temp": 281.5, "rain_1h": 0.0, "snow_1h": 0.0, "clouds_all": 75,
        "holiday": None,
        "weather": [{"main": "Clouds", "description": "broken clouds"}],
    }})

    date_time: datetime = Field(..., description="Hour of the observation (minutes are truncated)")
    traffic_volume: int = Field(..., ge=0, le=10000, description="Vehicles in the hour")
    temp: float = Field(..., ge=0, le=350, description="Temperature in Kelvin")
    rain_1h: float = Field(0.0, ge=0, description="Rain in mm")
    snow_1h: float = Field(0.0, ge=0, description="Snow in mm")
    clouds_all: int = Field(..., ge=0, le=100, description="Cloud cover %")
    holiday: Optional[str] = Field(None, max_length=50)
    weather: list[WeatherCondition] = Field(..., min_length=1)

    _tz = field_validator("date_time")(_naive)


class TrafficRecordUpdate(BaseModel):
    """Body for PUT: any subset of fields; only the fields sent are changed."""
    model_config = ConfigDict(json_schema_extra={"example": {"traffic_volume": 700, "clouds_all": 90}})

    date_time: Optional[datetime] = None
    traffic_volume: Optional[int] = Field(None, ge=0, le=10000)
    temp: Optional[float] = Field(None, ge=0, le=350)
    rain_1h: Optional[float] = Field(None, ge=0)
    snow_1h: Optional[float] = Field(None, ge=0)
    clouds_all: Optional[int] = Field(None, ge=0, le=100)
    holiday: Optional[str] = Field(None, max_length=50)
    weather: Optional[list[WeatherCondition]] = Field(None, min_length=1)

    @field_validator("date_time")
    @classmethod
    def _tz(cls, v):
        return _naive(v) if v is not None else v


class TrafficRecord(TrafficRecordCreate):
    """Response model: a stored record with its database id."""
    id: Union[int, str] = Field(..., description="reading_id (SQL) or ObjectId (MongoDB)")


class RecordList(BaseModel):
    count: int
    records: list[TrafficRecord]


class DeleteResult(BaseModel):
    deleted: bool
    record: TrafficRecord
