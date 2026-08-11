#!/usr/bin/env python3
"""Build a source-bound SQ-candle versus Dukascopy parity contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from lab.sq_bridge.candle_data_v4 import load_candles


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, sq_candles_path: Path, sq_timezone: str,
          dukascopy_candles_path: Path, dukascopy_timezone: str,
          symbol: str, timeframe: str, minimum_coverage_pct: float = 95.0,
          maximum_ohlc_delta: float = 1e-5) -> dict:
    if (not symbol or not timeframe or not 0 < minimum_coverage_pct <= 100
            or not math.isfinite(maximum_ohlc_delta) or maximum_ohlc_delta < 0):
        raise ValueError("parametres del contracte de candles invalids")
    sq = load_candles(sq_candles_path, sq_timezone)
    duka = load_candles(dukascopy_candles_path, dukascopy_timezone)
    common = sq.index.intersection(duka.index)
    coverage = len(common) / len(sq) * 100
    if len(common):
        deltas = (sq.loc[common, ["open", "high", "low", "close"]]
                  - duka.loc[common, ["open", "high", "low", "close"]]).abs()
        row_delta = deltas.max(axis=1)
        matched = int((row_delta <= maximum_ohlc_delta).sum())
        match_pct = matched / len(common) * 100
        observed_max = float(row_delta.max())
    else:
        matched, match_pct, observed_max = 0, 0.0, None
    checks = {
        "sq_coverage_pct": coverage >= minimum_coverage_pct,
        "ohlc_match_pct": match_pct >= minimum_coverage_pct,
    }
    return {
        "schema_version": 1,
        "contract_type": "sq_dukascopy_candle_parity_v4",
        "decision": "PASS_CANDLE_PARITY" if all(checks.values())
                    else "BLOCK_CANDLE_PARITY",
        "performance_accessed": False,
        "symbol": symbol,
        "timeframe": timeframe,
        "sq_candles_path": str(sq_candles_path.resolve()),
        "sq_candles_sha256": _sha(sq_candles_path),
        "sq_timezone": sq_timezone,
        "dukascopy_candles_path": str(dukascopy_candles_path.resolve()),
        "dukascopy_candles_sha256": _sha(dukascopy_candles_path),
        "dukascopy_timezone": dukascopy_timezone,
        "sq_rows": len(sq), "dukascopy_rows": len(duka),
        "common_rows": len(common), "matched_rows": matched,
        "sq_coverage_pct": coverage, "ohlc_match_pct": match_pct,
        "maximum_observed_ohlc_delta": observed_max,
        "maximum_allowed_ohlc_delta": maximum_ohlc_delta,
        "minimum_required_pct": minimum_coverage_pct,
        "first_common_timestamp_utc": common[0].isoformat() if len(common) else None,
        "last_common_timestamp_utc": common[-1].isoformat() if len(common) else None,
        "checks": checks,
        "semantics": "SQ sizing candles independently compared with Dukascopy OHLC",
    }


def verify(contract: dict) -> dict:
    for key in ("sq_candles_path", "dukascopy_candles_path"):
        path = Path(contract.get(key, ""))
        if not path.is_file() or _sha(path) != contract.get(f"{key[:-5]}_sha256"):
            raise ValueError("font del contracte de candles manipulada")
    rebuilt = build(
        sq_candles_path=Path(contract["sq_candles_path"]),
        sq_timezone=contract.get("sq_timezone", ""),
        dukascopy_candles_path=Path(contract["dukascopy_candles_path"]),
        dukascopy_timezone=contract.get("dukascopy_timezone", ""),
        symbol=contract.get("symbol", ""), timeframe=contract.get("timeframe", ""),
        minimum_coverage_pct=contract.get("minimum_required_pct"),
        maximum_ohlc_delta=contract.get("maximum_allowed_ohlc_delta"))
    return rebuilt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sq-candles", required=True, type=Path)
    parser.add_argument("--sq-timezone", required=True)
    parser.add_argument("--dukascopy-candles", required=True, type=Path)
    parser.add_argument("--dukascopy-timezone", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--minimum-coverage-pct", type=float, default=95.0)
    parser.add_argument("--maximum-ohlc-delta", type=float, default=1e-5)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(
        sq_candles_path=args.sq_candles, sq_timezone=args.sq_timezone,
        dukascopy_candles_path=args.dukascopy_candles,
        dukascopy_timezone=args.dukascopy_timezone,
        symbol=args.symbol, timeframe=args.timeframe,
        minimum_coverage_pct=args.minimum_coverage_pct,
        maximum_ohlc_delta=args.maximum_ohlc_delta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "coverage_pct": result["sq_coverage_pct"],
                      "match_pct": result["ohlc_match_pct"]}, indent=2))


if __name__ == "__main__":
    main()
