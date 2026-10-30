"""Database connections for the API (created once, reused by every request).

Thin cached wrappers around the shared helpers in src/db.py, so the API uses
the same connection settings (src/config.py / .env) as the loaders.
"""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from sqlalchemy.engine import Engine

from src import db as shared


@lru_cache
def sql_engine() -> Engine:
    return shared.mysql_engine()


@lru_cache
def mongo_client() -> MongoClient:
    return shared.mongo_client()


def mongo_collection() -> Collection:
    return shared.mongo_collection(mongo_client())
