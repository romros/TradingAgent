#!/usr/bin/env python3
"""Atomic daily CAT forward fetch -> receipt verification -> shadow scan."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False,
                                     prefix="." + path.name) as stream:
        temp = Path(stream.name); json.dump(value, stream, indent=2); stream.write("\n")
        stream.flush(); os.fsync(stream.fileno())
    temp.replace(path)


def verify_forward(candles: Path, receipt_path: Path, as_of: dt.date) -> dict:
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("classification") != "FORWARD_ONLY_NOT_RESEARCH":
        raise ValueError("unsafe forward classification")
    actual = hashlib.sha256(candles.read_bytes()).hexdigest()
    if actual != receipt.get("csv_sha256"):
        raise ValueError("forward CSV hash does not match receipt")
    if receipt.get("performance_calculated") is not False:
        raise ValueError("forward feed contaminated by performance calculation")
    last = dt.date.fromisoformat(receipt["last_session"])
    if last > as_of:
        raise ValueError("future-dated session")
    age = (as_of - last).days
    if age > 5:
        raise ValueError(f"stale forward feed: {age} calendar days")
    if int(receipt.get("sessions", 0)) < 45:
        raise ValueError("insufficient indicator warm-up")
    return receipt


def run(command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                               timeout=120, check=False)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip()[-1000:])
    return json.loads(completed.stdout)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--candles", type=Path, default=ROOT / "data/forward/CAT_CANONICAL_D1.csv")
    ap.add_argument("--receipt", type=Path, default=ROOT / "data/forward/CAT_CANONICAL_D1.receipt.json")
    ap.add_argument("--ledger", type=Path, default=ROOT / "data/shadow/cat_0168.json")
    ap.add_argument("--status", type=Path, default=ROOT / "data/shadow/cat_0168_pipeline_status.json")
    ap.add_argument("--lock", type=Path, default=ROOT / "data/shadow/cat_0168_pipeline.lock")
    ap.add_argument("--skip-fetch", action="store_true", help="verify and scan an existing forward receipt")
    args = ap.parse_args()
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    with args.lock.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("CAT shadow pipeline already running")
        result = {"schema_version": 1, "pipeline": "cat_0168_forward_shadow",
                  "as_of": args.as_of.isoformat(), "mode": "shadow", "orders_sent": 0,
                  "paper_authorized": False, "live_authorized": False}
        try:
            if not args.skip_fetch:
                result["fetch"] = run([sys.executable, str(ROOT / "apps/cat_forward_fetch.py"),
                                      "--as-of", args.as_of.isoformat(), "--output", str(args.candles),
                                      "--receipt", str(args.receipt)])
            receipt = verify_forward(args.candles, args.receipt, args.as_of)
            result["receipt_verified"] = True
            result["scan"] = run([sys.executable, str(ROOT / "apps/cat_0168_shadow_daily.py"),
                                  "--candles", str(args.candles), "--ledger", str(args.ledger),
                                  "--session", receipt["last_session"], "--capital", str(args.capital)])
            result["status"] = "PASS"
        except Exception as exc:
            result.update(status="FAIL_CLOSED", error=f"{type(exc).__name__}: {exc}")
        atomic_json(args.status, result)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
