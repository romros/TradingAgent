#!/usr/bin/env python3
"""Read-only real-time dashboard for the IBKR StrategyQuant research queue."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(__file__).resolve().parent / "web"
DATA = ROOT / "data/ibkr_sq_v2"
UNIVERSE = ROOT / "lab/sq_bridge/ibkr_new_universe_v2.json"


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def docker_usage() -> dict:
    command = ["docker", "stats", "sqcli-docker", "--no-stream", "--format",
               "{{json .}}"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=8, check=False)
        value = json.loads(completed.stdout.strip()) if completed.returncode == 0 else {}
        return {
            "available": bool(value), "cpu": value.get("CPUPerc"),
            "memory": value.get("MemUsage"), "memory_percent": value.get("MemPerc"),
            "pids": value.get("PIDs"),
        }
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"available": False}


def run_rows() -> list[dict]:
    rows = []
    runs = DATA / "runs"
    directories = (sorted(runs.glob("*")) if runs.is_dir() else [])
    for pilot in sorted(DATA.glob("aapl_*")):
        if pilot.is_dir() and pilot not in directories:
            directories.append(pilot)
    for directory in directories:
        status = read_json(directory / "watchdog_status.json") or {}
        receipt = read_json(directory / "supervised_run_receipt.json")
        preflight = read_json(directory / "run_preflight.json") or {}
        if not status and not receipt and not preflight:
            continue
        rows.append({
            "id": directory.name,
            "project": (receipt or preflight).get("project_name") or status.get("project"),
            "hypothesis": (receipt or preflight).get("hypothesis_id") or directory.name,
            "state": status.get("state") or (receipt or {}).get("decision") or "PREPARED",
            "reason": status.get("reason"),
            "generated": status.get("generated", (receipt or {}).get("generated", 0)),
            "accepted": status.get("in_databank", (receipt or {}).get("accepted", 0)),
            "budget": status.get("hard_attempt_budget", (receipt or {}).get("hard_attempt_budget")),
            "strategies_per_hour": status.get("strategies_per_hour"),
            "exceptions": status.get("job_exceptions", 0),
            "observed_at": status.get("observed_at"),
            "complete": receipt is not None,
            "decision": (receipt or {}).get("decision"),
        })
    return sorted(rows, key=lambda row: row.get("observed_at") or "", reverse=True)


def retest_rows() -> list[dict]:
    rows = []
    base = DATA / "retests"
    for receipt_path in sorted(base.glob("**/supervised_retest_receipt.json")) \
            if base.is_dir() else []:
        value = read_json(receipt_path)
        if not value:
            continue
        rows.append({
            "candidate": value.get("candidate_id"), "project": value.get("project_name"),
            "stage": value.get("retest_stage"), "decision": value.get("decision"),
            "passed": value.get("passed"), "failed": value.get("failed"),
            "holdout_accessed": value.get("holdout_accessed"),
            "path": str(receipt_path.relative_to(ROOT)),
        })
    return rows


def candidate_kpis() -> list[dict]:
    portfolio = read_json(DATA / "two_strategy_portfolio/sxr8_cat_v1.json") or {}
    forward = portfolio.get("forward_validation_oos_2022_2024", {}).get("strategies", {})
    sxr8, cat = forward.get("SXR8_TURN_OF_MONTH", {}), forward.get("CAT_0168", {})
    return [
        {"case": "SXR8 canvi de mes", "status": "SHADOW_PAPER_READY",
         "passes": bool(sxr8), "summary": sxr8},
        {"case": "CAT 0.168 −DI/ATR", "status": "RESEARCH_SHADOW",
         "passes": bool(cat), "summary": cat,
         "warning": "21 trades OOS 2024; gate de release=60"},
    ] if sxr8 and cat else []


def portfolio_kpis() -> list[dict]:
    value = read_json(DATA / "two_strategy_portfolio/sxr8_cat_v1.json") or {}
    forward = value.get("forward_validation_oos_2022_2024", {})
    if value.get("decision") != "TWO_EDGE_SHADOW_PORTFOLIO" or not forward:
        return []
    ledgers = {}
    for symbol, path in (("SXR8", ROOT / "data/shadow/sxr8_turn_of_month.json"),
                         ("CAT", ROOT / "data/shadow/cat_0168.json")):
        ledger = read_json(path) or {"intents": []}
        position = sum((1 if row.get("action") == "BUY" else -1) * int(row.get("quantity", 0))
                       for row in ledger.get("intents", []) if row.get("symbol") == symbol)
        ledgers[symbol] = {"intents": len(ledger.get("intents", [])), "position": position}
    pipeline = read_json(ROOT / "data/shadow/cat_0168_pipeline_status.json") or {}
    return [{"cases": ["SXR8", "CAT 0.168"], "status": value["decision"],
             "period": "2022–2024 validation+OOS", "summary": forward.get("portfolio", {}),
             "correlation": forward.get("diversification", {}).get("correlation_zero_when_inactive"),
             "strategies": forward.get("strategies", {}), "shadow_ledgers": ledgers,
             "cat_pipeline": {"status": pipeline.get("status"),
                              "session": (pipeline.get("scan") or {}).get("session"),
                              "action": (pipeline.get("scan") or {}).get("action"),
                              "orders_sent": pipeline.get("orders_sent", 0)},
             "passes_temporal_portfolio_gate": forward.get("both_positive") is True}]


def queue_rows(runs: list[dict]) -> list[dict]:
    universe = read_json(UNIVERSE) or {}
    return [{"hypothesis": row.get("diversification_role"),
             "project": row.get("symbol"), "state": row.get("status", "QUEUED")}
            for row in universe.get("candidates", [])]


def universe_rows() -> list[dict]:
    universe = read_json(UNIVERSE) or {}
    return [{"symbol": row.get("symbol"), "status": row.get("status"),
             "label": f"{row.get('name')} · {row.get('local_history_status')}"}
            for row in universe.get("candidates", [])]


def snapshot() -> dict:
    runs = run_rows()
    active = next((row for row in runs
                   if not row["complete"] and row.get("observed_at")), None)
    retests = retest_rows()
    candidates = candidate_kpis()
    portfolios = portfolio_kpis()
    cat = read_json(DATA / "preflight/cat_2017_mechanical_preflight.json") or {}
    complete_runs = [row for row in runs if row["complete"]]
    return {
        "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
        "objective": "Cartera shadow SXR8 + CAT amb dos edges no cripto",
        "venue": "IBKR preparat; sense compte ni ordres", "instrument": "SXR8 + CAT", "crypto_allowed": False,
        "goal": {"starting_capital_usd": "2 butxaques independents de 1.000",
                 "research_cagr_target_pct": "edge net, no promesa de retorn",
                 "portfolio_strategy_target": "2/2 edges trobats; següent consolidar forward",
                 "style": "D1, determinista i auditable",
                 "commission_per_order_usd": "costos d'estrès inclosos",
                 "maximum_risk_per_trade_pct": "sense leverage; CAT encara research shadow",
                 "status": "TWO_EDGE_SHADOW_PORTFOLIO"},
        "gates": ["Dades i mapping certificats", "Preregistre immutable",
                  "Validation i OOS nets", "Costos base/conservador/estrès",
                  "Monte Carlo i risc de ruïna", "Pertorbació i walk-forward",
                  "Paritat SQ → Python", "Holdout final una sola vegada"],
        "universe": universe_rows(),
        "kpis": {"completed_runs": len(complete_runs),
                 "total_generated": sum(int(row.get("generated") or 0) for row in complete_runs),
                 "total_accepted": sum(int(row.get("accepted") or 0) for row in complete_runs),
                 "retests_completed": len(candidates) or len(retests),
                 "promoted_candidates": sum(bool(row.get("passes")) for row in candidates)},
        "findings": ["SXR8: SHADOW_PAPER_READY; canvi de mes last 1 + first 3.",
                     "CAT 0.168: edge validat i RESEARCH_SHADOW; no paper/live.",
                     "Cartera 2022–2024: +16,72%, PF 1,203, DD tancat 9,76%.",
                     "Correlació mensual SXR8/CAT: 0,321; diversificació observable.",
                     "CAT conserva el bloqueig de 21/60 trades OOS; 2025+ segellat."],
        "active": active, "runs": runs, "queue": queue_rows(runs),
        "retests": retests, "candidates": candidates, "portfolios": portfolios,
        "small_account": {}, "docker": docker_usage(),
        "paper_authorized": False, "live_authorized": False,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/status":
            payload = json.dumps(snapshot(), separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        if self.path != "/api/status":
            super().log_message(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Alquimia dashboard: http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
