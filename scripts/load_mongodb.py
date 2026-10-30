"""Create the MongoDB `traffic_readings` collection and load the dataset (Task 2).

Usage (from the repository root, with MongoDB running):
    python -m scripts.load_mongodb

Steps
1. Drop and recreate the collection with the $jsonSchema validator in
   database/mongodb/validator.json.
2. Create the indexes:
     date_time      unique  -> one document per hour; "latest" and date-range queries
     weather.main           -> filter by weather condition (multikey on the array)
     holiday        partial -> only holiday documents are indexed
3. Insert one document per hour (40,575).
4. Write a few real documents to database/mongodb/sample_documents.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo import ASCENDING, DESCENDING

from src import config
from src.db import hourly_documents, load_raw_for_db, mongo_client

MONGO_DIR = config.ROOT_DIR / "database" / "mongodb"

# Hours chosen to show the different document shapes.
SAMPLE_HOURS = [
    "2012-10-02 09:00:00",   # first record: ordinary hour, one condition
    "2012-10-08 00:00:00",   # holiday (Columbus Day)
    "2012-10-14 09:00:00",   # several weather conditions in one hour
    "2018-09-30 23:00:00",   # last record
]


def main() -> None:
    start = time.time()
    client = mongo_client()
    db = client[config.MONGO_DATABASE]
    name = config.MONGO_COLLECTION

    validator = json.loads((MONGO_DIR / "validator.json").read_text())
    db.drop_collection(name)
    coll = db.create_collection(name, validator=validator, validationLevel="strict")

    coll.create_index([("date_time", ASCENDING)], unique=True, name="uq_date_time")
    coll.create_index([("weather.main", ASCENDING), ("date_time", DESCENDING)],
                      name="idx_weather_main_date")
    coll.create_index([("holiday", ASCENDING)], name="idx_holiday",
                      partialFilterExpression={"holiday": {"$type": "string"}})

    docs = hourly_documents(load_raw_for_db())
    result = coll.insert_many(docs, ordered=False)
    print(f"Inserted {len(result.inserted_ids):,} documents into {config.MONGO_DATABASE}.{name}")
    print("Indexes:", ", ".join(coll.index_information()))

    from datetime import datetime
    wanted = [datetime.fromisoformat(h) for h in SAMPLE_HOURS]
    samples = list(coll.find({"date_time": {"$in": wanted}}).sort("date_time", 1))
    # Extended-JSON-style output so the file shows the real BSON types.
    for d in samples:
        d["_id"] = {"$oid": str(d["_id"])}
        d["date_time"] = {"$date": d["date_time"].isoformat() + "Z"}
    out = MONGO_DIR / "sample_documents.json"
    out.write_text(json.dumps(samples, indent=2) + "\n")
    print(f"Wrote {len(samples)} sample documents to {out.relative_to(config.ROOT_DIR)}")
    print(f"Done in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
