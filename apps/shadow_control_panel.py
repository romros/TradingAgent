#!/usr/bin/env python3
"""Simple human-facing shadow portfolio panel with an hourly scheduler."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/shadow_panel_web"
STATE = ROOT / "data/shadow/hourly_scheduler_status.json"
CAT_PIPELINE = ROOT / "data/shadow/cat_0168_pipeline_status.json"
MSFT_PIPELINE = ROOT / "data/shadow/msft_capitulation_pipeline_status.json"
PORTFOLIO = ROOT / "data/ibkr_sq_v2/two_strategy_portfolio/sxr8_cat_v1.json"
SXR8_READY = ROOT / "data/ibkr_sq_v2/turn_of_month/sxr8_shadow_readiness.json"
SXR8_SCHEDULE = ROOT / "data/ibkr_sq_v2/turn_of_month/sxr8_xetra_schedule_2026.json"
ASSET_SELECTION = ROOT / "data/shadow/asset_selection_dashboard.json"


def read(path: Path, default=None):
    try: return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError): return {} if default is None else default


def position(path: Path, symbol: str) -> dict:
    ledger = read(path, {"intents": []}); quantity = 0
    for item in ledger.get("intents", []):
        if item.get("symbol") != symbol: continue
        quantity += (1 if item.get("action") == "BUY" else -1) * int(item.get("quantity", 0))
    return {"quantity": quantity, "intents": len(ledger.get("intents", [])),
            "last_intent": ledger.get("intents", [])[-1] if ledger.get("intents") else None}


def atomic_state(value: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(".tmp"); temp.write_text(json.dumps(value, indent=2) + "\n"); temp.replace(STATE)


def run_cycle(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc); started = now.isoformat()
    result = {"started_at": started, "status": "RUNNING", "orders_sent": 0}
    atomic_state(result)
    commands = {
        "CAT": [sys.executable, str(ROOT / "apps/cat_shadow_pipeline.py"),
                "--as-of", now.date().isoformat(), "--capital", "1000"],
        "SXR8": [sys.executable, str(ROOT / "apps/sxr8_shadow_daily.py"),
                 "--session", now.date().isoformat(), "--capital", "1000"],
        "MSFT": [sys.executable, str(ROOT / "apps/msft_shadow_pipeline.py"),
                 "--as-of", now.date().isoformat(), "--capital", "1000"],
    }
    outputs = {}
    for name, command in commands.items():
        try:
            done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                  timeout=180, check=False)
            outputs[name] = json.loads(done.stdout) if done.stdout.strip() else {
                "status": "ERROR", "error": done.stderr[-500:]}
            outputs[name]["returncode"] = done.returncode
        except Exception as exc:
            outputs[name] = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}",
                             "returncode": 1, "orders_sent": 0}
    ended = dt.datetime.now(dt.timezone.utc)
    result.update(status="PASS" if all(x["returncode"] == 0 for x in outputs.values()) else "FAIL_CLOSED",
                  ended_at=ended.isoformat(), next_run_at=(ended + dt.timedelta(hours=1)).isoformat(),
                  strategies=outputs, orders_sent=sum(int(x.get("orders_sent", 0)) for x in outputs.values()))
    atomic_state(result); return result


def scheduler(stop: threading.Event, interval: int) -> None:
    while not stop.is_set():
        run_cycle()
        stop.wait(interval)


def snapshot() -> dict:
    cycle, cat, msft, portfolio = read(STATE), read(CAT_PIPELINE), read(MSFT_PIPELINE), read(PORTFOLIO)
    forward = portfolio.get("forward_validation_oos_2022_2024", {})
    sxr8_position = position(ROOT / "data/shadow/sxr8_turn_of_month.json", "SXR8")
    cat_position = position(ROOT / "data/shadow/cat_0168.json", "CAT")
    msft_position = position(ROOT / "data/shadow/msft_capitulation.json", "MSFT")
    schedule = read(SXR8_SCHEDULE); today = dt.date.today().isoformat()
    upcoming = next((x for x in schedule.get("actions", []) if x.get("date", "") >= today), None)
    cat_scan = cat.get("scan", {})
    return {"schema_version": 1, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode": "SHADOW_ONLY", "plain_status": (
                "Tot correcte. Esperant una oportunitat; no hi ha cap posició oberta."
                if cycle.get("status") == "PASS" and not sxr8_position["quantity"] and not cat_position["quantity"] and not msft_position["quantity"]
                else "Revisa els avisos o les posicions obertes."),
            "scheduler": cycle,
            "strategies": [
                {"name": "SXR8 · canvi de mes", "state": "SHADOW_PAPER_READY",
                 "explanation": "Compra l'última sessió del mes i ven la quarta del següent.",
                 "last_action": (cycle.get("strategies", {}).get("SXR8") or {}).get("action", "NONE"),
                 "position": sxr8_position, "next_known_action": upcoming},
                {"name": "CAT 0.168 · pressió venedora", "state": "RESEARCH_SHADOW",
                 "explanation": "Entra quan disminueix la pressió venedora; usa stop i objectiu ATR.",
                 "last_action": cat_scan.get("action", "NO_SCAN"), "last_session": cat_scan.get("session"),
                 "position": cat_position, "next_known_action": "Depèn del senyal diari"},
                {"name": "MSFT · capitulació D1", "state": "RESEARCH_SHADOW",
                 "explanation": "Caiguda diària extrema sota Bollinger; entra l'endemà i surt al tancament.",
                 "last_action": (msft.get("scan") or {}).get("action", "NO_SCAN"),
                 "last_session": (msft.get("scan") or {}).get("session"),
                 "position": msft_position, "next_known_action": "Depèn del senyal al tancament anterior"}],
            "portfolio": {"research_period": "2022–2024 validació + OOS",
                          **forward.get("portfolio", {}),
                          "correlation": forward.get("diversification", {}).get("correlation_zero_when_inactive")},
            "asset_selection": read(ASSET_SELECTION, {"assets": []}),
            "safety": {"orders_sent": cycle.get("orders_sent", 0), "broker_connected": False,
                       "paper_authorized": False, "live_authorized": False,
                       "message": "Tot és hipotètic: aquest servei no conté cap client d'ordres."}}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(WEB), **kwargs)
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()
    def do_GET(self):
        if urlparse(self.path).path == "/api/status":
            payload = json.dumps(snapshot()).encode(); self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload); return
        super().do_GET()
    def log_message(self, fmt, *args):
        if self.path != "/api/status": super().log_message(fmt, *args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770); ap.add_argument("--interval", type=int, default=3600)
    ap.add_argument("--no-scheduler", action="store_true"); args = ap.parse_args()
    if args.interval < 60: raise ValueError("interval must be at least 60 seconds")
    stop = threading.Event()
    if not args.no_scheduler:
        threading.Thread(target=scheduler, args=(stop, args.interval), daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Shadow panel: http://{args.host}:{args.port} · interval={args.interval}s", flush=True)
    try: server.serve_forever()
    finally: stop.set(); server.server_close()


if __name__ == "__main__": main()
