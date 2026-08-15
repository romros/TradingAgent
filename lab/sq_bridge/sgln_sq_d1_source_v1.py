#!/usr/bin/env python3
"""Convert adjusted SGLN.L Yahoo D1 from GBp to canonical SQ GBP MT4 CSV."""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def convert(source: Path, output: Path, receipt: Path) -> dict:
    rows = []; repaired = 0
    with source.open(newline="", encoding="utf-8-sig") as stream:
        for raw in csv.reader(stream):
            if not raw or raw[0].lower() == "date": continue
            day = raw[0].replace(".", "-")
            if day < "2012-01-03": continue
            if day >= "2025-01-01": raise ValueError("through-2024 source required")
            offset = 2 if len(raw) > 1 and ":" in raw[1] else 1
            open_, high, low, close = [float(raw[offset + index]) / 100.0 for index in range(4)]
            fixed_high, fixed_low = max(high, open_, close), min(low, open_, close)
            repaired += int(fixed_high != high or fixed_low != low)
            volume = raw[offset + 4] if len(raw) > offset + 4 else "0"
            rows.append([day.replace("-", "."), "00:00",
                         *[f"{value:.8f}" for value in (open_, fixed_high, fixed_low, close)], volume])
    if not rows or len({row[0] for row in rows}) != len(rows): raise ValueError("empty or duplicate D1 source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream: csv.writer(stream, lineterminator="\n").writerows(rows)
    result = {"schema_version": 1, "decision": "PASS_SGLN_SQ_D1_IMPORT_SOURCE",
              "symbol": "SGLN_GBP_ALQ_D1", "instrument": "SGLN_GBP_ALQ",
              "unit_conversion": "Yahoo GBp divided by 100 to GBP", "scale": 0.01,
              "envelope_rows_repaired": repaired,
              "rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
              "source_sha256": sha(source), "output_sha256": sha(output),
              "performance_accessed": False, "paper_authorized": False, "live_authorized": False}
    receipt.parent.mkdir(parents=True, exist_ok=True); receipt.write_text(json.dumps(result, indent=2) + "\n")
    return result
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--receipt",type=Path,required=True)
    args=parser.parse_args(); print(json.dumps(convert(args.source,args.output,args.receipt),indent=2))
if __name__ == "__main__": main()
