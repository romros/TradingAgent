#!/usr/bin/env python3
"""Local, read-only Wolfpack dashboard backed by ephemeral JSON/JSONL feeds."""

from __future__ import annotations

import argparse
import csv
import io
import importlib.util
import json
import statistics
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def market_overview(rows: list[dict], now: datetime) -> dict:
    """Summarise comparable venue facts; never manufacture a trading signal."""
    instruments: dict[str, list[dict]] = {}
    for row in rows:
        captured = parse_time(row.get("captured_at"))
        for quote in row.get("sources", {}).get("ostium", []):
            name = quote.get("instrument")
            if name and quote.get("mid") is not None:
                instruments.setdefault(name, []).append({**quote, "captured_at": captured})
    output = []
    for name in ("BTC/USD", "US500/USD", "XAU/USD", "EUR/USD"):
        quotes = sorted(instruments.get(name, []), key=lambda item: item["captured_at"] or now)
        if not quotes:
            output.append({"instrument": name, "status": "NO_DATA"})
            continue
        latest = quotes[-1]
        age_seconds = ((now - latest["captured_at"]).total_seconds()
                       if latest["captured_at"] else None)
        changes = {}
        for label, seconds in (("change_1h_pct", 3600), ("change_4h_pct", 14400)):
            cutoff = now.timestamp() - seconds
            prior = min(quotes, key=lambda item: abs((item["captured_at"] or now).timestamp() - cutoff))
            changes[label] = ((float(latest["mid"]) / float(prior["mid"]) - 1) * 100
                              if prior.get("mid") else None)
        output.append({"instrument": name, "status": "STALE" if age_seconds is None or age_seconds > 900 else "LIVE",
                       "captured_at": latest["captured_at"].isoformat() if latest["captured_at"] else None,
                       "age_seconds": age_seconds, "mid": latest.get("mid"),
                       "spread_bps": latest.get("spread_bps"),
                       "market_open": latest.get("market_open"), **changes})
    live = sum(row.get("status") == "LIVE" for row in output)
    return {"cadence_minutes": 10, "universe": output,
            "situation": "DATA_HEALTHY" if live == len(output) else "PARTIAL_OR_STALE",
            "interpretation": "Moviment i costos observats; no és una recomanació d'entrada."}


def paper_csv(paper: dict, standalone: list[dict] | None = None) -> bytes:
    fields = ["paper_status", "position_sha256", "wallet_sha256", "pair", "side",
              "entry_time", "exit_time", "entry_price", "exit_price",
              "copy_net_pnl_usdc", "cost_complete"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for status, key in (("OPEN", "open_positions"), ("CLOSED", "closed")):
        for trade in paper.get(key, []):
            writer.writerow({"paper_status": status, **trade})
    for trade in standalone or []:
        writer.writerow({"paper_status": "CLOSED_STANDALONE", **trade})
    return stream.getvalue().encode()


def live_message(events: list[dict], now: datetime) -> dict | None:
    if not events:
        return None
    last = events[-1]
    timestamp = parse_time(last.get("detected_at"))
    age_minutes = None if timestamp is None else (now - timestamp).total_seconds() / 60
    wallet = last.get("wallet_sha256", "unknown")
    related = [row for row in events[-12:] if row.get("wallet_sha256") == wallet]
    opened_longs = [row for row in related if row.get("action") == "Open" and row.get("side") == "B"]
    closed_shorts = [row for row in related if row.get("action") in
                     {"Close", "StopLoss", "TakeProfit"} and row.get("side") == "S"]
    rotation = bool(opened_longs and closed_shorts)
    direction = "llarga" if last.get("side") == "B" else "curta"
    stale = age_minutes is None or age_minutes > 60
    return {
        "level": "WATCH",
        "status": "EXPIRED" if stale else "LIVE",
        "title": f"{last.get('pair', 'Mercat')} · activitat {direction}",
        "body": ("La wallet ha tancat curts i ha obert llargs; possible gir tàctic. "
                 if rotation else "S'ha detectat activitat nova d'una wallet observada. ")
                + ("Ja no és una entrada vigent; queda com a evidència."
                   if stale else "Cal confirmació i preu paper abans d'actuar."),
        "facts": {
            "action": last.get("action"),
            "source_execution_price": last.get("execution_price"),
            "detection_latency_seconds": last.get("detection_latency_seconds"),
            "wallet": wallet[:8],
            "age_minutes": age_minutes,
        },
        "simulated": False,
    }


def tracking_views(events: list[dict], paper: dict) -> tuple[list[dict], list[dict]]:
    """Build asset inventory and source-vs-paper lifecycle without inventing missing opens."""
    closed_paper = {row.get("position_sha256"): row for row in paper.get("closed", [])}
    open_paper = {row.get("position_sha256"): row for row in paper.get("open_positions", [])}
    grouped: dict[str, list[dict]] = {}
    for row in events:
        if row.get("position_sha256"):
            grouped.setdefault(row["position_sha256"], []).append(row)
    tracking = []
    for position, rows in grouped.items():
        rows.sort(key=lambda row: row.get("executed_at", ""))
        opens = [row for row in rows if row.get("action") == "Open"]
        closes = [row for row in rows if row.get("action") in
                  {"Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade"}]
        source_pnl = sum(float(row.get("closed_pnl_usd") or 0) for row in closes)
        if opens and not closes:
            status = "OPEN"
        elif opens and closes:
            opened = sum(float(row.get("notional_usd") or 0) for row in opens)
            closed = sum(float(row.get("notional_usd") or 0) for row in closes)
            status = "CLOSED" if closed >= opened * .999 else "PARTIAL"
        else:
            status = "CLOSED_SEEN"
        paper_trade = closed_paper.get(position)
        paper_position = open_paper.get(position)
        if paper_trade:
            paper_status, paper_pnl = "CLOSED", paper_trade.get("copy_net_pnl_usdc")
        elif paper_position:
            paper_status, paper_pnl = "OPEN", None
        else:
            paper_status, paper_pnl = "NOT_COPIED", None
        tracking.append({"position": position[:8], "wallet": rows[-1].get("wallet_sha256", "")[:8],
                         "asset": rows[-1].get("pair"), "side": rows[-1].get("side"),
                         "source_status": status, "source_pnl_usd": source_pnl if closes else None,
                         "paper_status": paper_status, "paper_net_pnl_usdc": paper_pnl,
                         "opened_at": opens[0].get("executed_at") if opens else None,
                         "last_event_at": rows[-1].get("executed_at"),
                         "last_action": rows[-1].get("action")})
    tracking.sort(key=lambda row: row.get("last_event_at") or "", reverse=True)
    assets: dict[str, dict] = {}
    for row in events:
        asset = row.get("pair")
        if not asset:
            continue
        cell = assets.setdefault(asset, {"asset": asset, "events": 0, "open_source": 0,
                                         "closed_source": 0, "source_realized_pnl_usd": 0.0,
                                         "paper_open": 0, "paper_closed": 0,
                                         "paper_net_pnl_usdc": 0.0})
        cell["events"] += 1
    for row in tracking:
        cell = assets[row["asset"]]
        cell["open_source"] += row["source_status"] in {"OPEN", "PARTIAL"}
        cell["closed_source"] += row["source_status"] in {"CLOSED", "CLOSED_SEEN"}
        cell["source_realized_pnl_usd"] += row["source_pnl_usd"] or 0
        cell["paper_open"] += row["paper_status"] == "OPEN"
        cell["paper_closed"] += row["paper_status"] == "CLOSED"
        cell["paper_net_pnl_usdc"] += row["paper_net_pnl_usdc"] or 0
    return sorted(assets.values(), key=lambda row: row["asset"]), tracking


def roster_view(events: list[dict], paper: dict, pack: dict) -> dict:
    module_path = Path(__file__).with_name("wolfpack.py")
    spec = importlib.util.spec_from_file_location("wolfpack_roster_engine", module_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    closed = paper.get("closed", [])
    roster = engine.portfolio_roster(closed, paper.get("execution_realism_pass", False))
    candidates = {row["wallet_sha256"]: row for row in roster.get("candidates", [])}
    titulars = {row["wallet_sha256"]: row for row in roster.get("titulars", [])}
    profiles = []
    for member in pack.get("members", []):
        wallet = member["id"]
        wallet_events = [row for row in events if row.get("wallet_sha256") == wallet]
        wallet_closed = [row for row in closed if row.get("wallet_sha256") == wallet]
        source_closes = [row for row in wallet_events if row.get("action") in
                         {"Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade"}]
        open_paper = [row for row in paper.get("open_positions", [])
                      if row.get("wallet_sha256") == wallet]
        latencies = [float(row["detection_latency_seconds"]) for row in wallet_events
                     if row.get("detection_latency_seconds") is not None]
        shortfalls = [float(row["implementation_shortfall_bps"]) for row in wallet_closed
                      if row.get("implementation_shortfall_bps") is not None]
        if wallet in titulars:
            status = "TITULAR"
        elif wallet in candidates:
            status = "CANDIDATE"
        elif len(wallet_closed) >= engine.CANDIDATE_MIN_CLOSED:
            status = "DEGRADED"
        else:
            status = "OBSERVED"
        if status == "TITULAR":
            confidence = "VALIDATED"
        elif status == "CANDIDATE":
            confidence = "PRELIMINARY"
        elif wallet_closed:
            confidence = "LOW"
        else:
            confidence = "NO_CLOSED_SAMPLE"
        profiles.append({
            "wallet": wallet[:8], "wallet_sha256": wallet, "status": status,
            "confidence": confidence,
            "confidence_meaning": "evidence maturity, not probability of profit",
            "specialties": member.get("specialties", []), "risk_flags": member.get("risk_flags", []),
            "events": len(wallet_events), "assets": sorted({row.get("pair") for row in wallet_events if row.get("pair")}),
            "source_closed": len(source_closes),
            "source_realized_pnl_usd": sum(float(row.get("closed_pnl_usd") or 0)
                                           for row in source_closes),
            "paper_open": len(open_paper),
            "paper_closed": len(wallet_closed),
            "candidate_progress": f"{min(len(wallet_closed), 10)}/10",
            "titular_progress": f"{min(len(wallet_closed), 30)}/30",
            "copy_net_pnl_usdc": sum(float(row.get("copy_net_pnl_usdc") or 0) for row in wallet_closed),
            "median_latency_seconds": statistics.median(latencies) if latencies else None,
            "median_shortfall_bps": statistics.median(shortfalls) if shortfalls else None,
        })
    status_order = {"TITULAR": 0, "CANDIDATE": 1, "OBSERVED": 2, "DEGRADED": 3}
    profiles.sort(key=lambda row: (status_order[row["status"]], -row["events"]))
    titular_count = sum(row["status"] == "TITULAR" for row in profiles)
    portfolio_ready = (paper.get("execution_realism_pass", False) and titular_count >= 2)
    return {**roster, "profiles": profiles,
            "portfolio_gate": {
                "pass": portfolio_ready,
                "minimum_titulars": 2,
                "current_titulars": titular_count,
                "maximum_total_collateral_usdc": 300,
                "maximum_collateral_per_wallet_usdc": 100,
                "maximum_collateral_per_position_usdc": 50,
                "blockers": ([] if portfolio_ready else [
                    "paper execution realism gate has not passed"
                    if not paper.get("execution_realism_pass", False)
                    else f"only {titular_count}/2 minimum titulars"]),
                "live_trading_authorized": False,
            }}


def build_state(follows: Path, heartbeat: Path, paper_path: Path,
                checkpoint: Path, now: datetime | None = None,
                pack_path: Path | None = None,
                link_watch_path: Path | None = None,
                diary_path: Path | None = None,
                codex_review_path: Path | None = None,
                standalone_result_path: Path | None = None,
                unified_ledger_path: Path | None = None,
                unified_ledger_csv_path: Path | None = None,
                replication_watch_path: Path | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    events = read_jsonl(follows)
    heartbeat_data = read_json(heartbeat)
    paper = read_json(paper_path)
    checkpoint_data = read_json(checkpoint)
    pack = read_json(pack_path or Path(__file__).with_name("pack.json"))
    link_watch = read_json(link_watch_path) if link_watch_path else {}
    diary = read_jsonl(diary_path) if diary_path else []
    codex_review = read_json(codex_review_path) if codex_review_path else {}
    standalone = read_json(standalone_result_path) if standalone_result_path else {}
    standalone_closed = [standalone] if standalone.get("status", "").startswith("CLOSED") else []
    standalone_net = sum(float(row.get("copy_net_pnl_usdc") or 0) for row in standalone_closed)
    unified_ledger = read_json(unified_ledger_path) if unified_ledger_path else {}
    replication_watch = read_json(replication_watch_path) if replication_watch_path else {}
    assets, tracking = tracking_views(events, paper)
    roster = roster_view(events, paper, pack)
    checked = parse_time(heartbeat_data.get("checked_at"))
    heartbeat_age = None if checked is None else (now - checked).total_seconds()
    messages = []
    message = live_message(events, now)
    if message:
        messages.append(message)
    for trade in paper.get("closed", [])[-5:]:
        messages.append({
            "level": "PAPER_RESULT", "status": "CLOSED",
            "title": f"{trade.get('pair')} · paper {trade.get('action')}",
            "body": "Resultat del follower al preu observable, sense cap ordre real.",
            "facts": {"copy_net_pnl_usdc": trade.get("copy_net_pnl_usdc"),
                      "gross_pnl_usdc": trade.get("gross_pnl_usdc"),
                      "cost_complete": trade.get("cost_complete")},
            "simulated": False,
        })
    if heartbeat_age is None or heartbeat_age > 1800:
        messages.insert(0, {"level": "SYSTEM", "status": "STALE",
                            "title": "Follower sense heartbeat recent",
                            "body": "No interpretar absència de senyals com absència d'activitat.",
                            "facts": {"heartbeat_age_seconds": heartbeat_age}, "simulated": False})
    simulations = [
        {"level": "WATCH", "status": "SIMULATION", "title": "BTC/USD · possible gir alcista",
         "body": "Una wallet excepcional gira de curta a llarga. Encara falta confirmar que el preu sigui copiable.",
         "facts": {"risk": "cap", "next": "esperar entrada paper"}, "simulated": True},
        {"level": "PAPER", "status": "SIMULATION", "title": "CL · reversió de basis en prova",
         "body": "Basis persistent i funding negatiu; entrada només simulada amb invalidació i expiració.",
         "facts": {"risk_pct": 0.25, "expiry": "6h", "orders": "none"}, "simulated": True},
        {"level": "CANDIDATE", "status": "SIMULATION", "title": "Wallet individual validada",
         "body": "30 tancaments copiats, PF ≥1,5 i dues meitats positives. Requereix decisió humana.",
         "facts": {"live_authorized": False}, "simulated": True},
    ]
    return {
        "generated_at": now.isoformat(),
        "health": {"follower": "healthy" if heartbeat_age is not None and heartbeat_age <= 1800 else "stale",
                   "heartbeat_age_seconds": heartbeat_age},
        "coverage": {"events": len(events), "paper_open": len(paper.get("open_positions", [])),
                     "paper_closed": len(paper.get("closed", [])) + len(standalone_closed),
                     "standalone_paper_closed": len(standalone_closed),
                     "paper_skipped": len(paper.get("skipped", []))},
        "paper": {"starting_equity_usdc": paper.get("starting_equity_usdc", 500),
                  "ending_equity_usdc": paper.get("ending_equity_usdc", 500) + standalone_net,
                  "wolfpack_ending_equity_usdc": paper.get("ending_equity_usdc", 500),
                  "standalone_net_pnl_usdc": standalone_net,
                  "combined_equity_is_estimate": any(not row.get("cost_complete")
                                                     for row in standalone_closed),
                  "execution_realism_pass": paper.get("execution_realism_pass", False),
                  "execution_realism_blockers": paper.get("execution_realism_blockers", []),
                  "live_trading_authorized": False},
        "messages": messages,
        "assets": assets,
        "tracking": tracking,
        "roster": roster,
        "global_signal": {
            "decision": "NO_SIGNAL",
            "reason": ("fewer than two titulars" if
                       roster["portfolio_gate"]["current_titulars"] < 2
                       else "awaiting three-model council and executable setup"),
            "direction": None, "entry": None, "invalidation": None,
            "target": None, "leverage": None, "expected_net_gain_usdc": None,
            "maximum_loss_usdc": None, "live_trading_authorized": False,
        },
        "link_watch": link_watch,
        "replication_watch": replication_watch,
        "standalone_paper_results": standalone_closed,
        "unified_ledger": unified_ledger,
        "opportunity_monitor": {
            "market": market_overview(diary, now),
            "setups": ([{"instrument": "LINK/USD", "kind": "BREAKOUT_OR_BREAKDOWN",
                         "state": link_watch.get("status", "NOT_STARTED"),
                         "paper_only": True}] if link_watch else []),
            "codex_review": codex_review or {"status": "WAITING_FOR_MATERIAL_CHANGE",
                                               "live_trading_authorized": False},
        },
        "simulations": simulations,
        "checkpoint": checkpoint_data.get("brief", checkpoint_data),
    }


def handler_factory(web_root: Path, paths: dict[str, Path]):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_root), **kwargs)

        def do_GET(self):
            request_path = urlparse(self.path).path
            if request_path == "/api/state":
                payload = json.dumps(build_state(**paths), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if request_path == "/api/paper.csv":
                standalone = read_json(paths["standalone_result_path"])
                payload = paper_csv(read_json(paths["paper_path"]), [standalone] if standalone else [])
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=wolfpack-paper.csv")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if request_path == "/api/ledger.csv":
                try:
                    payload = paths["unified_ledger_csv_path"].read_bytes()
                except FileNotFoundError:
                    payload = b""
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=wolfpack-unified-ledger.csv")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers(); self.wfile.write(payload); return
            super().do_GET()

        def end_headers(self):
            # This is a live local dashboard; stale frontend assets can misstate monitor status.
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def log_message(self, fmt, *args):
            return

    return Handler


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--duration-hours", type=float, default=720)
    parser.add_argument("--follows", type=Path, required=True)
    parser.add_argument("--heartbeat", type=Path, required=True)
    parser.add_argument("--paper", dest="paper_path", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--pack", dest="pack_path", type=Path,
                        default=here / "pack.json")
    parser.add_argument("--link-watch", dest="link_watch_path", type=Path,
                        default=Path("/host-tmp/link-watch-state.json"))
    parser.add_argument("--diary", dest="diary_path", type=Path,
                        default=Path("/host-tmp/cross-venue-diary-forward-20260813.jsonl"))
    parser.add_argument("--codex-review", dest="codex_review_path", type=Path,
                        default=Path("/host-tmp/opportunity-codex-review.json"))
    parser.add_argument("--standalone-result", dest="standalone_result_path", type=Path,
                        default=here.parents[1] / "experiments" / "observations" /
                        "link-breakout-breakdown-paper-v39-result.json")
    parser.add_argument("--unified-ledger", dest="unified_ledger_path", type=Path,
                        default=Path("/host-tmp/wolfpack-unified-ledger.json"))
    parser.add_argument("--unified-ledger-csv", dest="unified_ledger_csv_path", type=Path,
                        default=Path("/host-tmp/wolfpack-unified-ledger.csv"))
    parser.add_argument("--replication-watch", dest="replication_watch_path", type=Path,
                        default=Path("/host-tmp/link-relative-v40-state.json"))
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in
             ("follows", "heartbeat", "paper_path", "checkpoint", "pack_path")}
    paths.update(link_watch_path=args.link_watch_path, diary_path=args.diary_path,
                 codex_review_path=args.codex_review_path,
                 standalone_result_path=args.standalone_result_path,
                 unified_ledger_path=args.unified_ledger_path,
                 replication_watch_path=args.replication_watch_path)
    paths["unified_ledger_csv_path"] = args.unified_ledger_csv_path
    server = ThreadingHTTPServer((args.bind, args.port), handler_factory(here / "web", paths))
    server.timeout = 1
    deadline = time.time() + args.duration_hours * 3600
    while time.time() < deadline:
        server.handle_request()


if __name__ == "__main__":
    main()
