#!/usr/bin/env python3
"""Build a point-in-time Item 2.02 calendar without accessing price performance."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from bisect import bisect_left, bisect_right
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
CIK_TO_ASSET = {
    "0000320193": "AAPL", "0001018724": "AMZN", "0001652044": "GOOG",
    "0001326801": "META", "0001045810": "NVDA", "0000019617": "JPM",
    "0000021344": "KO", "0000315189": "DE", "0000200406": "JNJ",
    "0000100885": "UNP", "0000034088": "XOM",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def market_dates(path: Path) -> list[date]:
    dates = []
    with path.open(newline="") as stream:
        first = stream.readline()
        stream.seek(0)
        if first.lower().startswith("date,"):
            dates = [date.fromisoformat(row["date"]) for row in csv.DictReader(stream)]
        else:
            dates = [date.fromisoformat(row.split(",", 1)[0].replace(".", "-")) for row in stream if row.strip()]
    return sorted(stamp for stamp in dates if date(2017, 1, 1) <= stamp <= date(2024, 12, 31))


def filing_columns(document: dict) -> dict:
    return document["filings"]["recent"] if "filings" in document else document


def rows(columns: dict):
    keys = ("accessionNumber", "acceptanceDateTime", "filingDate", "form", "items")
    for values in zip(*(columns[key] for key in keys)):
        yield dict(zip(keys, values))


def first_session_after_acceptance(accepted_date: date,
                                   sessions: list[date]) -> date | None:
    """Return the first available session only for an in-window acceptance."""
    if not sessions or accepted_date < sessions[0] or accepted_date > sessions[-1]:
        return None
    index = bisect_left(sessions, accepted_date)
    return sessions[index] if index < len(sessions) else None


def preflight(sec_root: Path, price_paths: dict[str, Path]) -> dict:
    if set(price_paths) != set(CIK_TO_ASSET.values()):
        raise ValueError("frozen eleven-asset universe required")
    assets = {}
    all_events = []
    for cik, asset in CIK_TO_ASSET.items():
        current_path = sec_root / f"CIK{cik}.json"
        current = json.loads(current_path.read_text())
        documents = [(current_path, current)]
        for descriptor in current["filings"].get("files", []):
            if descriptor["filingTo"] >= "2017-01-01":
                path = sec_root / descriptor["name"]
                documents.append((path, json.loads(path.read_text())))
        sessions = market_dates(price_paths[asset])
        observed = {}
        source_hashes = []
        for path, document in documents:
            source_hashes.append({"path": str(path), "sha256": sha(path)})
            for filing in rows(filing_columns(document)):
                if filing["form"] == "8-K" and "2.02" in filing["items"]:
                    observed[filing["accessionNumber"]] = filing
        events = []
        for filing in observed.values():
            accepted = datetime.fromisoformat(filing["acceptanceDateTime"].replace("Z", "+00:00")).astimezone(NY)
            if not date(2017, 1, 1) <= accepted.date() <= date(2024, 12, 31):
                continue
            if accepted.date() in sessions and accepted.time() < time(16, 0):
                reaction_index = bisect_left(sessions, accepted.date())
            else:
                reaction_index = bisect_right(sessions, accepted.date())
            if reaction_index + 21 >= len(sessions):
                continue
            event = {
                "asset": asset,
                "accession": filing["accessionNumber"],
                "accepted_utc": filing["acceptanceDateTime"],
                "accepted_ny": accepted.isoformat(),
                "reaction_session": str(sessions[reaction_index]),
                "signal_session": str(sessions[reaction_index]),
                "entry_session": str(sessions[reaction_index + 1]),
                "exit_20_session": str(sessions[reaction_index + 21]),
            }
            if "2017-01-01" <= event["reaction_session"] <= "2024-12-31":
                events.append(event)
                all_events.append(event)
        assets[asset] = {
            "market_path": str(price_paths[asset]),
            "market_sha256": sha(price_paths[asset]),
            "first_market_date": str(sessions[0]),
            "last_market_date": str(sessions[-1]),
            "item_202_events": len(events),
            "sec_sources": source_hashes,
        }
    all_events.sort(key=lambda event: (event["reaction_session"], event["asset"], event["accession"]))
    counts = {period: sum(start <= event["reaction_session"] <= end for event in all_events) for period, (start, end) in {
        "train": ("2017-01-01", "2021-12-31"),
        "validation": ("2022-01-01", "2023-12-31"),
        "oos_2024": ("2024-01-01", "2024-12-31"),
    }.items()}
    return {
        "schema_version": 1,
        "decision": "PASS_SEC_POINT_IN_TIME_CALENDAR_PREFLIGHT",
        "performance_accessed": False,
        "universe": sorted(price_paths),
        "events": all_events,
        "event_counts": counts,
        "assets": assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sec-root", required=True, type=Path)
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {name: Path(path) for name, path in (item.split("=", 1) for item in args.asset)}
    result = preflight(args.sec_root, paths)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "event_counts": result["event_counts"], "assets": {key: value["item_202_events"] for key, value in result["assets"].items()}}, indent=2))


if __name__ == "__main__":
    main()
