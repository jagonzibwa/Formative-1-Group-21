"""Load the raw dataset into MySQL (Task 2).

Usage (from the repository root, after running database/mysql/schema.sql):
    python -m scripts.load_mysql

The script empties the four tables and reloads them, so it can be re-run.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from src.db import load_raw_for_db, mysql_engine, split_raw_for_db

# Parents before children, so foreign keys always point at existing rows.
LOAD_ORDER = ["holidays", "weather_conditions", "traffic_readings", "weather_observations"]


def main() -> None:
    start = time.time()
    raw = load_raw_for_db()
    tables = split_raw_for_db(raw)
    print(f"Raw rows after removing exact duplicates: {len(raw):,}")

    engine = mysql_engine()
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for name in reversed(LOAD_ORDER):
            conn.execute(text(f"TRUNCATE TABLE {name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

        for name in LOAD_ORDER:
            tables[name].to_sql(name, conn, if_exists="append", index=False,
                                chunksize=5000, method="multi")
            count = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            print(f"  {name:<22} {count:>7,} rows")

    print(f"Done in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
