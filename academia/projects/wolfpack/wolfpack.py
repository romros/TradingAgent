#!/usr/bin/env python3
"""Build a deterministic factual brief for the Wolfpack council."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from summarize_cross_venue_diary import summarize as summarize_diary

PRIMARY = {"EUR/USD", "US500/USD", "XAU/USD"}
CLOSES = {"Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade"}


def read_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_brief(diary_rows: list[dict], follow_rows: list[dict], pack: dict, council: dict) -> dict:
    diary = summarize_diary(diary_rows)
    primary = [row for row in follow_rows if row.get("pair") in PRIMARY]
    close_rows = [row for row in primary if row.get("action") in CLOSES]
    latencies = sorted(float(row["detection_latency_seconds"]) for row in primary
                       if row.get("detection_latency_seconds") is not None)
    wallets = Counter(row.get("wallet_sha256") for row in primary if row.get("wallet_sha256"))
    assets = Counter(row.get("pair") for row in primary if row.get("pair"))
    liquidations = sum(row.get("action") == "Liquidation" for row in primary)
    observed_days = len({str(row.get("captured_at", ""))[:10] for row in diary_rows
                         if len(str(row.get("captured_at", ""))) >= 10})
    complete_snapshots = sum(1 for row in diary_rows
                             if all(row.get("sources", {}).get(source)
                                    for source in ("ostium", "hyperliquid_xyz", "hyperliquid_mkts"))
                             and not row.get("errors"))
    max_criticality = "C1"
    blockers = []
    if observed_days < 20:
        blockers.append(f"only {observed_days}/20 minimum diary days")
    if complete_snapshots < 300:
        blockers.append(f"only {complete_snapshots}/300 complete market snapshots")
    if len(close_rows) < 30:
        blockers.append(f"only {len(close_rows)}/30 closed primary signals")
    if len(wallets) < 2:
        blockers.append(f"only {len(wallets)}/2 contributing wallets")
    if liquidations:
        blockers.append(f"{liquidations} followed liquidations require rejection review")
    if not blockers:
        max_criticality = "C2"
    anomalies = []
    for day, cells in diary["days"].items():
        for key, cell in cells.items():
            basis = cell.get("mark_oracle_basis_bps_median")
            if basis is not None and abs(basis) >= 10:
                anomalies.append({"day": day, "type": "mark_oracle_basis", "market": key,
                                  "value_bps": basis, "interpretation": "observe_only"})
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "FACTUAL_BRIEF_NO_LIVE_SIGNAL",
        "pack": {"members": len(pack["members"]), "frozen_until": pack["frozen_until"],
                 "statuses": dict(Counter(item["status"] for item in pack["members"]))},
        "coverage": {"diary_days": observed_days, "diary_snapshots": diary["snapshot_rows"],
                     "complete_market_snapshots": complete_snapshots,
                     "primary_follow_events": len(primary), "primary_closed_signals": len(close_rows),
                     "contributing_wallets": len(wallets), "liquidations": liquidations},
        "replicability": {"detection_latency_seconds_median": None if not latencies else latencies[len(latencies)//2],
                          "detection_latency_seconds_maximum": None if not latencies else max(latencies)},
        "activity": {"events_by_asset": dict(assets), "events_by_wallet_hash": dict(wallets)},
        "anomalies": anomalies[-20:],
        "data_errors": diary["errors_by_day_and_source"],
        "criticality_ceiling": max_criticality,
        "promotion_blockers": blockers,
        "council_contract_version": council["schema_version"],
        "decision": "OBSERVE" if blockers else "READY_TO_FORM_HYPOTHESES",
        "live_trading_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    brief = sub.add_parser("brief")
    brief.add_argument("--diary", type=Path)
    brief.add_argument("--follows", type=Path)
    brief.add_argument("--pack", type=Path, default=Path(__file__).with_name("pack.json"))
    brief.add_argument("--council", type=Path, default=Path(__file__).with_name("council.json"))
    brief.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_brief(read_jsonl(args.diary), read_jsonl(args.follows),
                         json.loads(args.pack.read_text()), json.loads(args.council.read_text()))
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
