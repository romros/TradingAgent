#!/usr/bin/env python3
"""Frozen, cheap GBPUSD M15 mechanism screen before any SQ Builder search."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import duckdb
import pandas as pd

from lab.sq_bridge.eurusd_intraday_v2 import candidates, features, metrics, trades

SPLITS = {
    "train": ("2007-01-01", "2013-12-31"),
    "validation": ("2014-01-01", "2018-12-31"),
    "oos": ("2019-01-01", "2023-12-31"),
}


def load_m15(path: Path) -> pd.DataFrame:
    query = """
        SELECT time_bucket(INTERVAL '15 minutes', to_timestamp(ts)) AS t,
               arg_min(open, ts) AS o, max(high) AS h, min(low) AS l,
               arg_max(close, ts) AS c, count(*) AS n
        FROM read_parquet(?) GROUP BY t ORDER BY t
    """
    frame = duckdb.connect(":memory:").execute(query, [str(path)]).df()
    frame.index = pd.to_datetime(frame.pop("t"), utc=True)
    return frame[(frame.n >= 10) & (frame.c > 0) & (frame.h > frame.l)]


def segment(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    start, end = SPLITS[name]
    return frame[(frame.date >= start) & (frame.date <= end)]


def run(path: Path) -> dict:
    data = features(load_m15(path))
    rows = []
    for family in ("asian_range_breakout", "vol_expansion_continuation", "vol_expansion_reversal"):
        variants = []
        for candidate_family, params in candidates():
            if candidate_family != family:
                continue
            candidate_trades = trades(data, family, params)
            train = metrics(segment(candidate_trades, "train"), 15)
            score = train["pf"] * math.sqrt(train["n"]) if train["n"] >= 100 and train["ev_usdc"] > 0 else -1
            variants.append((score, params, candidate_trades, train))
        _, params, selected, train = max(variants, key=lambda item: item[0])
        periods = {
            split: {
                scenario: metrics(segment(selected, split), bps)
                for scenario, bps in (("base", 8), ("conservative", 15), ("stress", 30))
            }
            for split in SPLITS
        }
        validation, oos = periods["validation"], periods["oos"]
        passed = (
            validation["base"]["n"] >= 100 and oos["base"]["n"] >= 100
            and validation["base"]["pf"] >= 1.2 and oos["base"]["pf"] >= 1.2
            and validation["stress"]["pf"] >= 1.05 and oos["stress"]["pf"] >= 1.05
            and validation["stress"]["ev_usdc"] >= .1 and oos["stress"]["ev_usdc"] >= .1
            and validation["base"]["positive_years"] >= .6 and oos["base"]["positive_years"] >= .6
        )
        rows.append({"family": family, "params": params, "train": train,
                     "periods": periods, "passes_pre_holdout": passed})
    eligible = [row["family"] for row in rows if row["passes_pre_holdout"]]
    return {
        "methodology": "methodology_gbpusd_m15_v1.json",
        "source": str(path),
        "coverage": {"first": str(data.index.min()), "last": str(data.index.max()), "bars": len(data)},
        "holdout_evaluated": False,
        "families": rows,
        "eligible": eligible,
        "decision": "PASS_TO_SQCLI" if eligible else "REJECT_NO_SQCLI",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
