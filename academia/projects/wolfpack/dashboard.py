#!/usr/bin/env python3
"""Local, read-only Wolfpack dashboard backed by ephemeral JSON/JSONL feeds."""

from __future__ import annotations

import argparse
import json
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


def build_state(follows: Path, heartbeat: Path, paper_path: Path,
                checkpoint: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    events = read_jsonl(follows)
    heartbeat_data = read_json(heartbeat)
    paper = read_json(paper_path)
    checkpoint_data = read_json(checkpoint)
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
                     "paper_closed": len(paper.get("closed", [])),
                     "paper_skipped": len(paper.get("skipped", []))},
        "paper": {"starting_equity_usdc": paper.get("starting_equity_usdc", 500),
                  "ending_equity_usdc": paper.get("ending_equity_usdc", 500),
                  "live_trading_authorized": False},
        "messages": messages,
        "simulations": simulations,
        "checkpoint": checkpoint_data.get("brief", checkpoint_data),
    }


def handler_factory(web_root: Path, paths: dict[str, Path]):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_root), **kwargs)

        def do_GET(self):
            if urlparse(self.path).path == "/api/state":
                payload = json.dumps(build_state(**paths), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

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
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in ("follows", "heartbeat", "paper_path", "checkpoint")}
    server = ThreadingHTTPServer((args.bind, args.port), handler_factory(here / "web", paths))
    server.timeout = 1
    deadline = time.time() + args.duration_hours * 3600
    while time.time() < deadline:
        server.handle_request()


if __name__ == "__main__":
    main()
