#!/usr/bin/env python3
"""Fail-closed data/timing preflight for official CFTC Gold positioning."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

DATE_FIELDS = ("Report_Date_as_YYYY-MM-DD", "As_of_Date_Form_YYYY-MM-DD",
               "Report_Date_as_MM_DD_YYYY")
IDENTITY_FIELDS = ("Market_and_Exchange_Names", "CFTC_Contract_Market_Code",
                   "CFTC_Commodity_Code")


def _clean(value: Any) -> str:
    return str(value or "").strip().strip('"').strip()


def _report_date(row: dict[str, str], field: str) -> date:
    raw = _clean(row[field])
    # Despite the legacy header name, official annual files observed here use ISO dates.
    try:
        return date.fromisoformat(raw)
    except ValueError:
        month, day, year = (int(value) for value in raw.split("/"))
        return date(year, month, day)


def inspect_archive(path: Path, spec: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1 or not members[0].lower().endswith(".txt"):
            raise ValueError(f"{path} must contain exactly one text member")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            fields = reader.fieldnames or []
            date_candidates = [field for field in DATE_FIELDS if field in fields]
            required = set(IDENTITY_FIELDS) | set(config["required_position_fields"])
            if len(date_candidates) != 1:
                raise ValueError(f"{path} has ambiguous/missing date field: {date_candidates}")
            missing = sorted(required - set(fields))
            gold_rows = [row for row in reader if
                         _clean(row.get("CFTC_Contract_Market_Code")) ==
                         config["expected_identity"]["cftc_contract_market_code"]]
    date_field = date_candidates[0]
    dates = [_report_date(row, date_field) for row in gold_rows]
    identities = sorted({(_clean(row["Market_and_Exchange_Names"]),
                          _clean(row["CFTC_Contract_Market_Code"]),
                          _clean(row["CFTC_Commodity_Code"])) for row in gold_rows})
    expected = config["expected_identity"]
    exact_identity = identities == [(expected["market_and_exchange_name"],
                                     expected["cftc_contract_market_code"],
                                     expected["cftc_commodity_code"])]
    invalid_numeric = 0
    for row in gold_rows:
        for field in config["required_position_fields"]:
            try:
                value = int(_clean(row[field]).replace(",", ""))
            except ValueError:
                invalid_numeric += 1
            else:
                invalid_numeric += value < 0
    return {
        "year": spec["year"], "path": str(path), "url": spec["url"],
        "sha256": raw_hash, "expected_sha256": spec["sha256"],
        "sha256_matches": raw_hash == spec["sha256"], "zip_member": members[0],
        "field_count": len(fields), "date_field": date_field,
        "missing_required_fields": missing, "gold_rows": len(gold_rows),
        "minimum_gold_rows": spec["minimum_gold_rows"],
        "row_count_pass": len(gold_rows) >= spec["minimum_gold_rows"],
        "identities": [list(identity) for identity in identities],
        "exact_identity_pass": exact_identity,
        "duplicate_report_dates": len(dates) - len(set(dates)),
        "first_report_date": min(dates).isoformat() if dates else None,
        "last_report_date": max(dates).isoformat() if dates else None,
        "non_tuesday_report_dates": sorted(stamp.isoformat() for stamp in dates if stamp.weekday() != 1),
        "invalid_numeric_positions": invalid_numeric,
    }


def audit(config: dict[str, Any]) -> dict[str, Any]:
    forbidden = ("strategy_rule_defined", "xau_performance_accessed", "validation_accessed",
                 "oos_accessed", "holdout_accessed", "sqcli_authorized",
                 "paper_authorized", "live_authorized")
    if any(config.get(field) is not False for field in forbidden):
        raise ValueError("preflight requires no strategy, performance, SQ or trading authorization")
    archives = [inspect_archive(Path(spec["path"]), spec, config)
                for spec in config["sample_archives"]]
    gate = config["gate"]
    data_checks = {
        "sample_archives": len(archives) >= gate["minimum_sample_archives"],
        "hashes": all(row["sha256_matches"] for row in archives),
        "schema": all(not row["missing_required_fields"] for row in archives),
        "identity": all(row["exact_identity_pass"] for row in archives),
        "row_counts": all(row["row_count_pass"] for row in archives),
        "unique_dates": all(row["duplicate_report_dates"] == 0 for row in archives),
        "numeric_positions": all(row["invalid_numeric_positions"] == 0 for row in archives),
    }
    data_pass = all(data_checks.values())
    release_ledger = bool(config["publication"]["historical_release_date_list_available"])
    availability_pass = release_ledger or not gate["require_historical_release_ledger_before_rule"]
    decision = ("PASS_DATA_AND_TIMING" if data_pass and availability_pass else
                "BLOCK_RELEASE_LEDGER" if data_pass else "BLOCK_DATA")
    return {
        "schema_version": 1, "campaign_id": config["campaign_id"],
        "stage": "official_flow_data_preflight", "decision": decision,
        "report": config["report"], "instrument": config["instrument"],
        "archives": archives, "data_gate": {"checks": data_checks,
                                               "status": "PASS" if data_pass else "BLOCK"},
        "availability_gate": {
            "status": "PASS" if availability_pass else "BLOCK_HISTORICAL_RELEASE_LEDGER",
            "normal_schedule": config["publication"]["normal_schedule"],
            "historical_release_date_list_available": release_ledger,
            "known_exception_evidence": config["publication"]["known_exception_evidence"],
            "required_before_strategy_rule": config["publication"]["historical_availability_policy"],
        },
        "permitted_next_action": "BUILD_RELEASE_LEDGER_ONLY" if decision == "BLOCK_RELEASE_LEDGER" else None,
        "strategy_rule_defined": False, "xau_performance_accessed": False,
        "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False,
        "sqcli_used": False, "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    result = audit(json.loads(raw))
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "data_gate": result["data_gate"]["status"],
                      "availability_gate": result["availability_gate"]["status"],
                      "gold_rows": sum(row["gold_rows"] for row in result["archives"]),
                      "xau_performance_accessed": result["xau_performance_accessed"]}, indent=2))


if __name__ == "__main__":
    main()
