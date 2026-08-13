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

CLOSES = {"Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade"}
EXCEPTIONAL_MIN_CLOSED = 30
EXCEPTIONAL_MIN_PROFIT_FACTOR = 1.5
EXCEPTIONAL_MAX_DRAWDOWN_PCT = 15.0
EXCEPTIONAL_MAX_SINGLE_TRADE_PROFIT_SHARE_PCT = 35.0
PAPER_EQUITY_USDC = 500.0


def read_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def exceptional_wallets(close_rows: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """Qualify one-wallet evidence using copied, net, prospective outcomes only."""
    grouped: dict[str, list[dict]] = {}
    for row in close_rows:
        wallet = row.get("wallet_sha256")
        if wallet:
            grouped.setdefault(wallet, []).append(row)
    qualified, blockers = [], {}
    for wallet, rows in grouped.items():
        reasons = []
        if len(rows) < EXCEPTIONAL_MIN_CLOSED:
            reasons.append(f"only {len(rows)}/{EXCEPTIONAL_MIN_CLOSED} closed signals")
        pnl = [row.get("copy_net_pnl_usdc") for row in rows]
        if any(value is None for value in pnl):
            reasons.append("missing copied net PnL after observed delay and costs")
            blockers[wallet] = reasons
            continue
        pnl = [float(value) for value in pnl]
        gross_profit = sum(max(value, 0.0) for value in pnl)
        gross_loss = -sum(min(value, 0.0) for value in pnl)
        profit_factor = None if gross_loss == 0 else gross_profit / gross_loss
        if profit_factor is None or profit_factor < EXCEPTIONAL_MIN_PROFIT_FACTOR:
            reasons.append("profit factor below robust threshold or no observed losses")
        midpoint = len(pnl) // 2
        if midpoint == 0 or sum(pnl[:midpoint]) <= 0 or sum(pnl[midpoint:]) <= 0:
            reasons.append("copied expectancy is not positive in both halves")
        equity = peak = PAPER_EQUITY_USDC
        max_drawdown = 0.0
        for value in pnl:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100 if peak else 100.0)
        if max_drawdown > EXCEPTIONAL_MAX_DRAWDOWN_PCT:
            reasons.append(f"drawdown {max_drawdown:.2f}% exceeds limit")
        largest_win_share = (max([value for value in pnl if value > 0], default=0.0)
                             / gross_profit * 100 if gross_profit else 100.0)
        if largest_win_share > EXCEPTIONAL_MAX_SINGLE_TRADE_PROFIT_SHARE_PCT:
            reasons.append("profit is too concentrated in one trade")
        if any(row.get("action") == "Liquidation" for row in rows):
            reasons.append("observed liquidation")
        if reasons:
            blockers[wallet] = reasons
        else:
            qualified.append({"wallet_sha256": wallet, "closed_signals": len(rows),
                              "copy_net_pnl_usdc": sum(pnl), "profit_factor": profit_factor,
                              "maximum_drawdown_pct": max_drawdown,
                              "largest_win_share_pct": largest_win_share})
    return qualified, blockers


def build_brief(diary_rows: list[dict], follow_rows: list[dict], pack: dict, council: dict,
                paper_rows: list[dict] | None = None) -> dict:
    diary = summarize_diary(diary_rows)
    eligible = [row for row in follow_rows if row.get("pair")]
    close_rows = [row for row in eligible if row.get("action") in CLOSES]
    latencies = sorted(float(row["detection_latency_seconds"]) for row in eligible
                       if row.get("detection_latency_seconds") is not None)
    wallets = Counter(row.get("wallet_sha256") for row in eligible if row.get("wallet_sha256"))
    assets = Counter(row.get("pair") for row in eligible if row.get("pair"))
    liquidations = sum(row.get("action") == "Liquidation" for row in eligible)
    exceptional, exceptional_blockers = exceptional_wallets(
        close_rows if paper_rows is None else paper_rows)
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
        blockers.append(f"only {len(close_rows)}/30 closed eligible signals")
    validation_route = "multi_wallet_consensus" if len(wallets) >= 2 else (
        "exceptional_single_wallet" if exceptional else "none")
    if validation_route == "none":
        blockers.append(f"only {len(wallets)}/2 contributing wallets and no exceptional wallet")
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
                     "eligible_follow_events": len(eligible), "eligible_closed_signals": len(close_rows),
                     "contributing_wallets": len(wallets), "liquidations": liquidations},
        "replicability": {"detection_latency_seconds_median": None if not latencies else latencies[len(latencies)//2],
                          "detection_latency_seconds_maximum": None if not latencies else max(latencies)},
        "activity": {"events_by_asset": dict(assets), "events_by_wallet_hash": dict(wallets)},
        "validation": {"route": validation_route, "exceptional_wallets": exceptional,
                       "exceptional_wallet_blockers": exceptional_blockers},
        "alert": {"level": "WATCH", "action": "observe_only",
                  "reason": "No entry is authorized by a factual brief."},
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
    brief.add_argument("--paper", type=Path)
    brief.add_argument("--pack", type=Path, default=Path(__file__).with_name("pack.json"))
    brief.add_argument("--council", type=Path, default=Path(__file__).with_name("council.json"))
    brief.add_argument("--output", type=Path)
    args = parser.parse_args()
    paper_rows = None
    paper_realism_pass = False
    if args.paper and args.paper.exists():
        paper_data = json.loads(args.paper.read_text())
        paper_rows = paper_data.get("closed", [])
        paper_realism_pass = paper_data.get("execution_realism_pass", False)
    result = build_brief(read_jsonl(args.diary), read_jsonl(args.follows),
                         json.loads(args.pack.read_text()), json.loads(args.council.read_text()),
                         paper_rows)
    if not paper_realism_pass:
        result["validation"]["exceptional_wallets"] = []
        if result["validation"]["route"] == "exceptional_single_wallet":
            result["validation"]["route"] = "none"
        result["validation"]["execution_realism_pass"] = False
        result["promotion_blockers"].append("paper execution realism gate has not passed")
        result["criticality_ceiling"] = "C1"
        result["decision"] = "OBSERVE"
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
