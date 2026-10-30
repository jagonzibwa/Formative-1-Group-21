"""End-to-end check of every API endpoint for both databases.

Start the API first (uvicorn api.main:app), then run:
    python scripts/test_api.py

For /sql and /mongo it runs: POST -> GET by id -> GET latest -> GET range ->
PUT -> GET list -> DELETE -> GET (expects 404), plus error cases (duplicate
POST 409, bad range 400, invalid body 422). Every request and response is
written to outputs/api_test_results.md as evidence.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import API_URL  # noqa: E402

OUT = ROOT / "outputs" / "api_test_results.md"
NEW_RECORD = {
    "date_time": "2018-10-01T00:00:00",
    "traffic_volume": 612,
    "temp": 281.4, "rain_1h": 0.0, "snow_1h": 0.0, "clouds_all": 75,
    "holiday": None,
    "weather": [{"main": "Clouds", "description": "broken clouds"}],
}

log: list[str] = []
failures = 0


def call(method: str, path: str, expect: int, **kwargs):
    global failures
    r = requests.request(method, API_URL + path, timeout=30, **kwargs)
    ok = r.status_code == expect
    failures += not ok
    body = r.json() if r.content else None
    shown = body
    if isinstance(body, dict) and isinstance(body.get("records"), list) and len(body["records"]) > 3:
        shown = {**body, "records": body["records"][:3] + [f"... {len(body['records']) - 3} more"]}
    req = f"\n\nBody:\n```json\n{json.dumps(kwargs['json'], indent=2)}\n```" if "json" in kwargs else ""
    log.append(f"### {'PASS' if ok else 'FAIL'} `{method} {path}` -> {r.status_code} (expected {expect}){req}\n\n"
               f"Response:\n```json\n{json.dumps(shown, indent=2, default=str)}\n```\n")
    print(f"{'PASS' if ok else 'FAIL'}  {method:<6} {path:<60} {r.status_code}")
    return body


def run_suite(prefix: str) -> None:
    log.append(f"\n## `{prefix}` endpoints\n")
    created = call("POST", f"{prefix}/records", 201, json=NEW_RECORD)
    rid = created["id"]
    call("POST", f"{prefix}/records", 409, json=NEW_RECORD)                         # duplicate hour
    call("GET", f"{prefix}/records/{rid}", 200)
    latest = call("GET", f"{prefix}/records/latest", 200)
    assert latest["date_time"].startswith("2018-10-01T00:00"), "latest should be the new record"
    call("GET", f"{prefix}/records/range?start=2018-09-30T20:00:00&end=2018-10-01T00:00:00", 200)
    call("GET", f"{prefix}/records/range?start=2018-10-02T00:00:00&end=2018-10-01T00:00:00", 400)
    call("PUT", f"{prefix}/records/{rid}", 200,
         json={"traffic_volume": 655, "clouds_all": 90,
               "weather": [{"main": "Rain", "description": "light rain"}, {"main": "Mist", "description": "mist"}]})
    call("PUT", f"{prefix}/records/{rid}", 422, json={"clouds_all": 150})            # validation error
    call("GET", f"{prefix}/records?limit=2", 200)
    call("DELETE", f"{prefix}/records/{rid}", 200)
    call("GET", f"{prefix}/records/{rid}", 404)


def main() -> None:
    health = call("GET", "/", 200)
    print("Health:", health)
    for prefix in ["/sql", "/mongo"]:
        run_suite(prefix)
    header = (f"# API test results\n\n_Generated {datetime.now():%Y-%m-%d %H:%M} by `scripts/test_api.py` "
              f"against {API_URL}. Failures: {failures}._\n")
    OUT.write_text(header + "\n".join(log), encoding="utf-8")
    print(f"\n{'All checks passed' if failures == 0 else f'{failures} check(s) failed'} -> {OUT.relative_to(ROOT)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
