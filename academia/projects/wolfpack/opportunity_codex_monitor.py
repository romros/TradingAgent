#!/usr/bin/env python3
"""Finite, event-triggered Codex reviewer for immutable paper-market snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


THRESHOLDS = {"BTC/USD": 0.5, "US500/USD": 0.35, "XAU/USD": 0.4, "EUR/USD": 0.2}


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


def snapshot(diary: Path, link_watch: Path) -> dict:
    rows = read_jsonl(diary)
    link = read_json(link_watch)
    prices: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
        for quote in row.get("sources", {}).get("ostium", []):
            if quote.get("instrument") in THRESHOLDS and quote.get("mid") is not None:
                prices.setdefault(quote["instrument"], []).append((stamp, float(quote["mid"])))
    markets = {}
    for name, values in prices.items():
        latest_time, latest = values[-1]
        prior = min(values, key=lambda value: abs(value[0] - (latest_time - 3600)))[1]
        change = (latest / prior - 1) * 100 if prior else 0
        threshold = THRESHOLDS[name]
        regime = "UP" if change >= threshold else "DOWN" if change <= -threshold else "NEUTRAL"
        markets[name] = {"mid": latest, "change_1h_pct": change, "regime": regime}
    return {"captured_at": datetime.now(timezone.utc).isoformat(), "markets": markets,
            "link": {"status": link.get("status", "NOT_STARTED"),
                     "position": link.get("position", {}), "last_quote": link.get("last_quote", {})},
            "paper_only": True, "live_trading_authorized": False}


def material_signature(payload: dict) -> str:
    facts = {"link_status": payload["link"]["status"],
             "regimes": {key: value["regime"] for key, value in payload["markets"].items()}}
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def invoke_codex(payload: dict, codex: Path, schema: Path, repo: Path) -> dict:
    prompt = ("Actua com a revisor crític d'una observació de mercat PAPER. Analitza només el JSON "
              "immutable adjunt. No executis eines, no modifiquis fitxers, no inventis dades i no "
              "autorizis ordres reals. OPEN_PAPER només és acceptable si el snapshot conté un setup "
              "amb entrada, invalidació i objectiu explícits. Sigues escèptic amb mostres petites.\n\n"
              + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    with tempfile.NamedTemporaryFile(prefix="wolfpack-codex-", suffix=".json", delete=False) as handle:
        result_path = Path(handle.name)
    try:
        command = [str(codex), "exec", "--ephemeral", "--ignore-user-config", "-s", "read-only",
                   "-C", str(repo), "--output-schema", str(schema),
                   "--output-last-message", str(result_path), prompt]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if completed.returncode:
            return {"status": "ERROR", "error": completed.stderr[-1000:],
                    "live_trading_authorized": False}
        reviewed = json.loads(result_path.read_text())
        reviewed.update(status="REVIEWED", reviewed_at=datetime.now(timezone.utc).isoformat(),
                        live_trading_authorized=False)
        return reviewed
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as error:
        return {"status": "ERROR", "error": str(error), "live_trading_authorized": False}
    finally:
        result_path.unlink(missing_ok=True)


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diary", type=Path, required=True)
    parser.add_argument("--link-watch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex", type=Path, default=Path("/home/roman/.local/bin/codex"))
    parser.add_argument("--schema", type=Path, default=here / "codex_review.schema.json")
    parser.add_argument("--repo", type=Path, default=here.parents[2])
    parser.add_argument("--interval-seconds", type=int, default=600)
    parser.add_argument("--duration-hours", type=float, default=720)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not 60 <= args.interval_seconds <= 3600 or not 0 < args.duration_hours <= 720:
        raise SystemExit("invalid finite cadence or duration")
    deadline = time.time() + args.duration_hours * 3600
    previous = read_json(args.output).get("material_signature")
    while time.time() < deadline:
        facts = snapshot(args.diary, args.link_watch)
        signature = material_signature(facts)
        if previous is None:
            result = {"status": "BASELINE_ESTABLISHED", "decision": "Esperant un canvi material",
                      "reviewed_at": None, "live_trading_authorized": False}
        elif signature != previous:
            result = invoke_codex(facts, args.codex, args.schema, args.repo)
        else:
            old = read_json(args.output)
            result = {key: value for key, value in old.items()
                      if key not in {"material_signature", "last_checked_at", "snapshot"}}
            result.setdefault("status", "WAITING_FOR_MATERIAL_CHANGE")
        result.update(material_signature=signature,
                      last_checked_at=datetime.now(timezone.utc).isoformat(), snapshot=facts)
        write_json(args.output, result)
        previous = signature
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
