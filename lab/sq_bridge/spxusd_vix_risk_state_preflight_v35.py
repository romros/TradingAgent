#!/usr/bin/env python3
"""No-performance official VIX data and timing preflight for US500 v35."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


def audit(config: dict[str, Any]) -> dict[str, Any]:
    forbidden = ("strategy_rule_defined", "spx_performance_accessed", "validation_accessed",
                 "oos_accessed", "holdout_accessed", "sqcli_authorized",
                 "paper_authorized", "live_authorized")
    if any(config.get(field) is not False for field in forbidden):
        raise ValueError("VIX preflight requires performance, SQ and trading to remain sealed")
    source = config["source"]
    path = Path(source["path"])
    raw = path.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        parsed = []
        invalid = 0
        inconsistent_ohlc = 0
        weekends = 0
        for row in reader:
            try:
                stamp = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
                values = {key: float(row[key]) for key in ("OPEN", "HIGH", "LOW", "CLOSE")}
                if not math.isfinite(values["CLOSE"]) or values["CLOSE"] <= 0:
                    raise ValueError
            except (KeyError, ValueError):
                invalid += 1
                continue
            if (not all(math.isfinite(value) and value > 0 for value in values.values())
                    or values["LOW"] > min(values["OPEN"], values["CLOSE"])
                    or values["HIGH"] < max(values["OPEN"], values["CLOSE"])
                    or values["LOW"] > values["HIGH"]):
                inconsistent_ohlc += 1
            weekends += stamp.weekday() >= 5
            parsed.append((stamp, values))
    dates = [row[0] for row in parsed]
    gate = config["gate"]
    checks = {
        "sha256": actual_hash == source["sha256"],
        "columns": columns == source["expected_columns"],
        "minimum_rows": len(parsed) >= gate["minimum_rows"],
        "first_date": bool(dates) and min(dates).isoformat() <= gate["minimum_first_date"],
        "last_date": bool(dates) and max(dates).isoformat() >= gate["minimum_last_date"],
        "unique_dates": (not gate["require_unique_dates"] or len(dates) == len(set(dates))),
        "weekdays": (not gate["require_weekdays"] or weekends == 0),
        "valid_close": (not gate["require_valid_close"] or invalid == 0),
        "no_same_session_use": config["timing_policy"]["same_session_use_allowed"] is False,
    }
    passed = all(checks.values())
    gaps = [(right - left).days for left, right in zip(sorted(dates), sorted(dates)[1:])]
    return {"schema_version": 1, "campaign_id": config["campaign_id"],
            "stage": "risk_state_data_preflight", "decision": "PASS_VIX_DATA_TIMING" if passed else "BLOCK_VIX_DATA",
            "checks": checks, "rows": len(parsed), "invalid_close_rows": invalid,
            "quarantined_inconsistent_non_close_ohlc_rows": inconsistent_ohlc,
            "duplicate_dates": len(dates) - len(set(dates)), "weekend_rows": weekends,
            "first_date": min(dates).isoformat() if dates else None,
            "last_date": max(dates).isoformat() if dates else None,
            "maximum_calendar_gap_days": max(gaps) if gaps else None,
            "source_sha256": actual_hash, "timing_policy": config["timing_policy"],
            "permitted_next_action": "WAIT_FOR_US500_EXECUTION_COST_GATE" if passed else "REPAIR_DATA_ONLY",
            "strategy_rule_defined": False, "spx_performance_accessed": False,
            "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False,
            "sqcli_used": False, "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_raw = args.config.read_bytes()
    result = audit(json.loads(config_raw))
    result["config_sha256"] = hashlib.sha256(config_raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("decision", "rows", "first_date", "last_date")}, indent=2))


if __name__ == "__main__":
    main()
