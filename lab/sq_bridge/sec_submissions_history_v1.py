#!/usr/bin/env python3
"""Download SEC-declared supplemental submission histories, resumably and politely."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://data.sec.gov/submissions/"
USER_AGENT = "TradingAgent academic research contact roman@example.invalid"


def download(current_paths: list[Path], output: Path, minimum_date: str = "2017-01-01") -> dict:
    output.mkdir(parents=True, exist_ok=True)
    required = []
    for current_path in current_paths:
        current = json.loads(current_path.read_text())
        for item in current["filings"].get("files", []):
            if item["filingTo"] >= minimum_date:
                required.append(item["name"])
    required = sorted(set(required))
    written = skipped = 0
    for name in required:
        target = output / name
        if target.is_file():
            json.loads(target.read_text())
            skipped += 1
            continue
        request = urllib.request.Request(BASE + name, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
        json.loads(payload)
        temporary = target.with_suffix(".tmp.json")
        temporary.write_bytes(payload)
        temporary.replace(target)
        written += 1
        time.sleep(0.12)
    return {"schema_version": 1, "required": len(required), "written": written, "skipped": skipped, "minimum_date": minimum_date}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("current", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(download(args.current, args.output), indent=2))


if __name__ == "__main__":
    main()
