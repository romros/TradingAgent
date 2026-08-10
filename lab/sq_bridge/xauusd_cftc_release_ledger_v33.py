#!/usr/bin/env python3
"""Build a fail-closed CFTC Gold historical availability ledger."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lab.sq_bridge.xauusd_cftc_flow_preflight_v32 import DATE_FIELDS, _clean, _report_date


def gold_dates(path: Path, expected: dict[str, str]) -> list[date]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"{path}: expected one archive member")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            fields = reader.fieldnames or []
            candidates = [field for field in DATE_FIELDS if field in fields]
            if len(candidates) != 1:
                raise ValueError(f"{path}: ambiguous report date field")
            field = candidates[0]
            rows = [row for row in reader
                    if _clean(row.get("CFTC_Contract_Market_Code")) ==
                    expected["cftc_contract_market_code"]]
            identities = {(_clean(row.get("Market_and_Exchange_Names")),
                           _clean(row.get("CFTC_Commodity_Code"))) for row in rows}
            wanted = {(expected["market_and_exchange_name"], expected["cftc_commodity_code"])}
            if identities != wanted:
                raise ValueError(f"{path}: Gold identity mismatch: {identities}")
            return [_report_date(row, field) for row in rows]


def exclusion_for(stamp: date, exclusions: list[dict[str, str]]) -> dict[str, str] | None:
    matches = [row for row in exclusions
               if date.fromisoformat(row["start"]) <= stamp <= date.fromisoformat(row["end"])]
    if len(matches) > 1:
        raise ValueError(f"overlapping exclusions for {stamp}")
    return matches[0] if matches else None


def build(config: dict[str, Any]) -> dict[str, Any]:
    forbidden = ("strategy_rule_defined", "xau_performance_accessed", "validation_accessed",
                 "oos_accessed", "holdout_accessed", "sqcli_authorized",
                 "paper_authorized", "live_authorized")
    if any(config.get(field) is not False for field in forbidden):
        raise ValueError("ledger construction cannot access strategy performance or trading")
    paths = sorted(Path().glob(config["source_glob"]))
    by_year = {int(path.stem.rsplit("_", 1)[1]): path for path in paths}
    if sorted(by_year) != config["expected_years"]:
        raise ValueError(f"year coverage mismatch: {sorted(by_year)}")
    hashes = {str(year): hashlib.sha256(path.read_bytes()).hexdigest()
              for year, path in by_year.items()}
    if hashes != config["expected_sha256"]:
        raise ValueError("archive hashes do not match the frozen manifest")
    dates = [stamp for year in sorted(by_year)
             for stamp in gold_dates(by_year[year], config["expected_identity"])]
    if len(dates) != len(set(dates)):
        raise ValueError("duplicate Gold report dates across annual archives")
    policy = config["availability_policy"]
    hour, minute, second = map(int, policy["time_local"].split(":"))
    zone = ZoneInfo(policy["timezone"])
    rows = []
    for stamp in sorted(dates):
        exclusion = exclusion_for(stamp, config["exclusions"])
        if exclusion:
            rows.append({"report_date": stamp.isoformat(), "status": "EXCLUDED",
                         "available_at": None, "reason": exclusion["reason"],
                         "source": exclusion["source"]})
        else:
            available_date = stamp + timedelta(days=policy["lag_calendar_days"])
            available = datetime.combine(available_date, time(hour, minute, second), zone)
            rows.append({"report_date": stamp.isoformat(), "status": "AVAILABLE_CONSERVATIVE",
                         "available_at": available.isoformat(), "reason": "frozen_conservative_lag",
                         "source": policy["source"]})
    available = sum(row["status"] == "AVAILABLE_CONSERVATIVE" for row in rows)
    excluded = len(rows) - available
    return {
        "schema_version": 1, "campaign_id": config["campaign_id"],
        "stage": "historical_availability_ledger", "decision": "PASS_CONSERVATIVE_LEDGER",
        "instrument": config["instrument"], "archive_sha256": hashes,
        "first_report_date": rows[0]["report_date"], "last_report_date": rows[-1]["report_date"],
        "report_count": len(rows), "available_count": available, "excluded_count": excluded,
        "policy": policy, "exclusions": config["exclusions"], "ledger": rows,
        "strategy_rule_defined": False, "xau_performance_accessed": False,
        "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False,
        "sqcli_used": False, "paper_authorized": False, "live_authorized": False
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    result = build(json.loads(raw))
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "report_count", "available_count", "excluded_count")}, indent=2))


if __name__ == "__main__":
    main()
