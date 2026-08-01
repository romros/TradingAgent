#!/usr/bin/env python3
"""Audita i, opcionalment, reconcilia l'estat agregat del paper probe."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.portfolio.db import get_state, get_trade_summary, init_db, reconcile_runtime_state
from packages.shared import config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=config.DB_PATH)
    parser.add_argument("--capital-initial", type=float, default=config.CAPITAL_INITIAL)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    conn = init_db(str(db_path))
    try:
        before = get_state(conn)
        summary = get_trade_summary(conn)
        report = {
            "db": str(db_path),
            "applied": False,
            "trade_rows_modified": 0,
            "before": {
                "capital": before.capital,
                "total_pnl": before.total_pnl,
                "settled_count": before.settled_count,
            },
            "canonical_summary": summary,
        }
        if args.apply:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = db_path.with_name(f"{db_path.name}.before_cost_reconcile_{stamp}.bak")
            conn.commit()
            backup_conn = sqlite3.connect(str(backup))
            try:
                conn.backup(backup_conn)
            finally:
                backup_conn.close()
            after = reconcile_runtime_state(conn, args.capital_initial)
            report["applied"] = True
            report["backup"] = str(backup)
            report["after"] = {
                "capital": after.capital,
                "total_pnl": after.total_pnl,
                "settled_count": after.settled_count,
                "consecutive_losses": after.consecutive_losses,
            }
        print(json.dumps(report, indent=2, default=str))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
