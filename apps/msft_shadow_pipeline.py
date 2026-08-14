#!/usr/bin/env python3
"""Atomic MSFT forward fetch, receipt verification and shadow scan."""
from __future__ import annotations
import argparse, datetime as dt, fcntl, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, prefix="." + path.name) as f:
        temp = Path(f.name); json.dump(value, f, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    temp.replace(path)

def run(command: list[str]) -> dict:
    done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    if done.returncode: raise RuntimeError((done.stderr or done.stdout).strip()[-1000:])
    return json.loads(done.stdout)

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--candles", type=Path, default=ROOT / "data/forward/MSFT_CANONICAL_D1.csv")
    ap.add_argument("--receipt", type=Path, default=ROOT / "data/forward/MSFT_CANONICAL_D1.receipt.json")
    ap.add_argument("--ledger", type=Path, default=ROOT / "data/shadow/msft_capitulation.json")
    ap.add_argument("--status", type=Path, default=ROOT / "data/shadow/msft_capitulation_pipeline_status.json")
    ap.add_argument("--lock", type=Path, default=ROOT / "data/shadow/msft_capitulation_pipeline.lock")
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args(); args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open("a+") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit("MSFT shadow pipeline already running")
        result = {"schema_version": 1, "pipeline": "msft_capitulation_forward_shadow",
                  "as_of": args.as_of.isoformat(), "mode": "shadow", "orders_sent": 0,
                  "paper_authorized": False, "live_authorized": False}
        try:
            if not args.skip_fetch:
                result["fetch"] = run([sys.executable, str(ROOT / "apps/cat_forward_fetch.py"),
                    "--ticker", "MSFT", "--as-of", args.as_of.isoformat(), "--output", str(args.candles),
                    "--receipt", str(args.receipt)])
            receipt = json.loads(args.receipt.read_text())
            if receipt.get("classification") != "FORWARD_ONLY_NOT_RESEARCH" or receipt.get("ticker") != "MSFT":
                raise ValueError("unsafe MSFT forward receipt")
            if hashlib.sha256(args.candles.read_bytes()).hexdigest() != receipt.get("csv_sha256"):
                raise ValueError("MSFT forward CSV hash mismatch")
            last = dt.date.fromisoformat(receipt["last_session"])
            if last > args.as_of or (args.as_of-last).days > 5 or int(receipt.get("sessions", 0)) < 45:
                raise ValueError("MSFT forward feed is stale, future-dated, or too short")
            result["receipt_verified"] = True
            result["scan"] = run([sys.executable, str(ROOT / "apps/msft_capitulation_shadow_daily.py"),
                "--candles", str(args.candles), "--ledger", str(args.ledger),
                "--session", receipt["last_session"], "--capital", str(args.capital)])
            result["status"] = "PASS"
        except Exception as exc: result.update(status="FAIL_CLOSED", error=f"{type(exc).__name__}: {exc}")
        atomic_json(args.status, result); print(json.dumps(result, indent=2))
        raise SystemExit(result["status"] != "PASS")

if __name__ == "__main__": main()
