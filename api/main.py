"""FastAPI application: CRUD + time-series endpoints for MySQL and MongoDB.

Run from the repository root:
    uvicorn api.main:app --reload

Interactive docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from . import mongo_routes, sql_routes
from .db import mongo_collection, sql_engine

app = FastAPI(
    title="Metro Interstate Traffic API",
    version="1.0.0",
    description=(
        "Hourly I-94 traffic volume + weather, stored in **MySQL** (`/sql/...`) and **MongoDB** "
        "(`/mongo/...`). Both expose the same record shape and the same endpoints: "
        "POST, GET (list / by id / latest / date range), PUT and DELETE."
    ),
)
app.include_router(sql_routes.router)
app.include_router(mongo_routes.router)


@app.exception_handler(OperationalError)
async def mysql_down(_: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "MySQL is unavailable", "error": str(exc.orig)})


@app.exception_handler(ServerSelectionTimeoutError)
async def mongo_down(_: Request, exc: PyMongoError):
    return JSONResponse(status_code=503, content={"detail": "MongoDB is unavailable"})


@app.get("/", tags=["Health"], summary="Service and database status")
def health():
    status = {"api": "ok"}
    try:
        with sql_engine().connect() as conn:
            status["mysql_records"] = conn.execute(text("SELECT COUNT(*) FROM traffic_readings")).scalar_one()
    except Exception as exc:  # noqa: BLE001
        status["mysql"] = f"unavailable: {exc.__class__.__name__}"
    try:
        status["mongodb_records"] = mongo_collection().estimated_document_count()
    except Exception as exc:  # noqa: BLE001
        status["mongodb"] = f"unavailable: {exc.__class__.__name__}"
    return status
