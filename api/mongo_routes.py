"""CRUD + time-series endpoints backed by MongoDB (collection `traffic_readings`)."""
from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, WriteError

from src.records import document_to_record, record_to_document

from .db import mongo_collection
from .schemas import (DeleteResult, RecordList, TrafficRecord, TrafficRecordCreate,
                      TrafficRecordUpdate)

router = APIRouter(prefix="/mongo/records", tags=["MongoDB"])


def _oid(record_id: str) -> ObjectId:
    try:
        return ObjectId(record_id)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{record_id}' is not a valid ObjectId")


def _get_one(record_id: str) -> dict:
    doc = mongo_collection().find_one({"_id": _oid(record_id)})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
    return doc


def _write_errors(exc: Exception):
    if isinstance(exc, DuplicateKeyError):
        raise HTTPException(status.HTTP_409_CONFLICT, "A record for that date_time already exists")
    if isinstance(exc, WriteError) and exc.code == 121:   # $jsonSchema validation failed
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Document failed collection validation")
    raise exc


# --------------------------------------------------------------------------- #
# CREATE
# --------------------------------------------------------------------------- #
@router.post("", response_model=TrafficRecord, status_code=status.HTTP_201_CREATED,
             summary="Create an hourly record")
def create_record(body: TrafficRecordCreate):
    doc = record_to_document(body.model_dump())
    try:
        result = mongo_collection().insert_one(doc)
    except (DuplicateKeyError, WriteError) as exc:
        _write_errors(exc)
    return document_to_record(mongo_collection().find_one({"_id": result.inserted_id}))


# --------------------------------------------------------------------------- #
# READ
# --------------------------------------------------------------------------- #
@router.get("", response_model=RecordList, summary="List records (newest first, paginated)")
def list_records(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    cur = mongo_collection().find().sort("timestamp", DESCENDING).skip(offset).limit(limit)
    recs = [document_to_record(d) for d in cur]
    return {"count": len(recs), "records": recs}


@router.get("/latest", response_model=TrafficRecord, summary="Latest record (most recent hour)")
def latest_record():
    doc = mongo_collection().find_one(sort=[("timestamp", DESCENDING)])
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No records")
    return document_to_record(doc)


@router.get("/range", response_model=RecordList, summary="Records in a date range (oldest first)")
def records_in_range(start: datetime = Query(..., examples=["2018-09-24T00:00:00"]),
                     end: datetime = Query(..., examples=["2018-09-30T23:00:00"]),
                     limit: int = Query(1000, ge=1, le=10000)):
    if start > end:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "start must be <= end")
    query = {"timestamp": {"$gte": start.replace(tzinfo=None), "$lte": end.replace(tzinfo=None)}}
    cur = mongo_collection().find(query).sort("timestamp", ASCENDING).limit(limit)
    recs = [document_to_record(d) for d in cur]
    return {"count": len(recs), "records": recs}


@router.get("/{record_id}", response_model=TrafficRecord, summary="Get one record by ObjectId")
def get_record(record_id: str):
    return document_to_record(_get_one(record_id))


# --------------------------------------------------------------------------- #
# UPDATE
# --------------------------------------------------------------------------- #
@router.put("/{record_id}", response_model=TrafficRecord, summary="Update a record (only the fields sent)")
def update_record(record_id: str, body: TrafficRecordUpdate):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    current = document_to_record(_get_one(record_id))
    merged = {**current, **changes}
    # Rebuild the whole document so derived `calendar` fields stay consistent.
    new_doc = record_to_document(merged)
    try:
        doc = mongo_collection().find_one_and_replace({"_id": _oid(record_id)}, new_doc,
                                                      return_document=ReturnDocument.AFTER)
    except (DuplicateKeyError, WriteError) as exc:
        _write_errors(exc)
    return document_to_record(doc)


# --------------------------------------------------------------------------- #
# DELETE
# --------------------------------------------------------------------------- #
@router.delete("/{record_id}", response_model=DeleteResult, summary="Delete a record")
def delete_record(record_id: str):
    doc = mongo_collection().find_one_and_delete({"_id": _oid(record_id)})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Record {record_id} not found")
    return {"deleted": True, "record": document_to_record(doc)}
