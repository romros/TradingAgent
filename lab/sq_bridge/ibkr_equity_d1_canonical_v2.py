#!/usr/bin/env python3
"""Convert an audited US-equity RTH D1 file to SQ's seven-column format."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source: Path, output: Path, receipt: Path, symbol: str,
          corporate_actions_url: str) -> dict:
    if not source.is_file() or not corporate_actions_url.startswith("https://"):
        raise ValueError("audited source and HTTPS corporate-actions source required")
    rows: list[tuple[str, list[float]]] = []
    envelope_repairs: list[dict] = []
    with source.open(newline="", encoding="utf-8-sig") as stream:
        for raw in csv.DictReader(stream):
            values = [float(raw[key]) for key in ("open", "high", "low", "close", "volume")]
            if values[2] <= 0 or int(raw["minutes"]) != 390:
                raise ValueError(f"invalid complete RTH candle on {raw['date']}")
            repaired_high = max(values[0], values[1], values[3])
            repaired_low = min(values[0], values[2], values[3])
            if repaired_high != values[1] or repaired_low != values[2]:
                envelope_repairs.append({
                    "date": raw["date"],
                    "high_delta": round(repaired_high - values[1], 9),
                    "low_delta": round(values[2] - repaired_low, 9)})
                values[1], values[2] = repaired_high, repaired_low
            rows.append((raw["date"], values))
    if not rows or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("dates must be non-empty, unique and increasing")
    jumps = [{"date": b[0], "close_return": round(b[1][3] / a[1][3] - 1, 9)}
             for a, b in zip(rows, rows[1:]) if abs(b[1][3] / a[1][3] - 1) >= .20]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        for day, values in rows:
            writer.writerow([day.replace("-", "."), "00:00",
                             *(f"{value:.6f}" for value in values)])
    temporary.replace(output)
    result = {
        "schema_version": 1, "decision": "PASS_CANONICAL_SOURCE_ONLY",
        "symbol": symbol, "timeframe": "D1", "rows": len(rows),
        "first": rows[0][0], "last": rows[-1][0],
        "source_path": str(source.resolve()), "source_sha256": _sha(source),
        "output_path": str(output.resolve()), "output_sha256": _sha(output),
        "corporate_actions_source": corporate_actions_url,
        "splits_in_research_window": [],
        "absolute_close_jumps_at_least_20pct": jumps,
        "ohlc_envelope_repair": {
            "rule": "high=max(source_high,open,close); low=min(source_low,open,close)",
            "rows_repaired": len(envelope_repairs),
            "max_high_delta": max((row["high_delta"] for row in envelope_repairs), default=0),
            "max_low_delta": max((row["low_delta"] for row in envelope_repairs), default=0)},
        "volume_rules_allowed": False, "performance_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "paper_authorized": False, "live_authorized": False
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--corporate-actions-url", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.receipt, args.symbol,
                           args.corporate_actions_url), indent=2))


if __name__ == "__main__":
    main()
