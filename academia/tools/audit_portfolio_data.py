#!/usr/bin/env python3
"""Audita cobertura del catàleg SQ per a un univers preregistrat, sense escriure dades."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def _date(value: int | None) -> str | None:
    return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc).date().isoformat() if value else None


def audit(db_path: Path, mapping: dict, required_start: str, required_end: str) -> dict:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT SYMBOL,INSTRUMENT,TIMEFRAME,DATEFROM,DATETO,ROWS FROM DATA").fetchall()
    results = []
    for target, candidates in mapping.items():
        matches = []
        for symbol, instrument, timeframe, date_from, date_to, count in rows:
            if symbol in candidates or instrument in candidates:
                start, end = _date(date_from), _date(date_to)
                matches.append({"symbol": symbol, "instrument": instrument, "timeframe": timeframe, "start": start, "end": end, "rows": count})
        exact = [item for item in matches if item["start"] and item["end"] and item["start"] <= required_start and item["end"] >= required_end]
        status = "ready" if exact else "insufficient_history" if matches else "missing"
        results.append({"target": target, "status": status, "matches": matches})
    blockers = [item["target"] for item in results if item["status"] != "ready"]
    return {
        "ready": not blockers,
        "required_window": {"start": required_start, "end": required_end},
        "assets": results,
        "blockers": blockers,
        "decision": "PREPARE_SQ_PROJECTS" if not blockers else "ACQUIRE_OR_REVISE_DATA_BEFORE_BUILDER",
        "limits": "Coincidència de catàleg i dates; encara cal auditar gaps, sessions, timezone i provenance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    result = audit(args.db, json.loads(args.mapping.read_text(encoding="utf-8")), args.start, args.end)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
