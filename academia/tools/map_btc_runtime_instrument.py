#!/usr/bin/env python3
"""Map BTCUSDT history to an Ostium execution instrument in an isolated SQ DB."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def map_instrument(db_path: Path, execute: bool) -> dict:
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        data = db.execute("SELECT * FROM DATA WHERE SYMBOL='BTCUSDT'").fetchone()
        source = db.execute("SELECT * FROM INSTRUMENTS WHERE INSTRUMENT='BTCUSDT'").fetchone()
        broker = db.execute("SELECT * FROM BROKER WHERE ID=12").fetchone()
        if data is None or source is None or broker is None:
            raise ValueError("runtime lacks BTCUSDT data, BTCUSDT instrument or Ostium broker 12")
        before = {"instrument": data["INSTRUMENT"], "broker_id": data["BROKER_ID"]}
        if execute:
            columns = [item[1] for item in db.execute("PRAGMA table_info(INSTRUMENTS)")]
            values = dict(source)
            values.update({
                "INSTRUMENT": "BTCUSDOST", "DESCRIPTION": "BTCUSDT history mapped to Ostium BTC/USD",
                "DEFAULTSPREAD": 5.0, "DEFAULTSLIPPAGE": 5.0, "ORDERSIZESTEP": 0.001,
                "BROKER_ID": 12, "DATATYPE": 3,
            })
            placeholders = ",".join("?" for _ in columns)
            db.execute(f"INSERT OR REPLACE INTO INSTRUMENTS ({','.join(columns)}) VALUES ({placeholders})", [values[name] for name in columns])
            db.execute("UPDATE DATA SET INSTRUMENT='BTCUSDOST', BROKER_ID=12 WHERE SYMBOL='BTCUSDT'")
            db.commit()
        after = {"instrument": "BTCUSDOST", "broker_id": 12} if execute else before
    return {"database": str(db_path), "mode": "execute" if execute else "dry_run", "before": before, "after": after, "prices_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute and "academia/runtime" not in args.db.as_posix():
        raise ValueError("refusing to modify a database outside academia/runtime")
    print(json.dumps(map_instrument(args.db, args.execute), indent=2))


if __name__ == "__main__":
    main()
