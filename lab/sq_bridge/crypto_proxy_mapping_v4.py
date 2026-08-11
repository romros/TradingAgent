#!/usr/bin/env python3
"""Build synchronized Binance/Ostium observations and gate proxy mapping."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_canonical_source_v4 import write_json_atomic


MIN_OBSERVATIONS = 240
MIN_DAYS = 60
MIN_HOURS = 12
MAX_BRACKET_SECONDS = 45
MAX_MEDIAN_ABS_BASIS_BPS = 10
MAX_P95_ABS_BASIS_BPS = 25
MIN_RETURN_CORRELATION = .999
MAX_P95_RETURN_ERROR_BPS = 10


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing capture timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_observation(before_path: Path, ostium_path: Path, after_path: Path,
                     output_path: Path) -> dict[str, Any]:
    before, ostium, after = (_load(path.resolve()) for path in
                             (before_path, ostium_path, after_path))
    before_at, ostium_at, after_at = (_stamp(before.get("captured_at")),
                                      _stamp(ostium.get("captured_at")),
                                      _stamp(after.get("captured_at")))
    before_symbol = ((before.get("source") or {}).get("symbol"))
    after_symbol = ((after.get("source") or {}).get("symbol"))
    instrument = ostium.get("instrument") or {}
    expected = f"{instrument.get('pair_from')}USDT"
    if (before_symbol != expected or after_symbol != expected
            or instrument.get("pair_to") != "USD"
            or not before_at <= ostium_at <= after_at):
        raise ValueError("quotes do not form a synchronized USD/USDT bracket")
    before_mid = float((before.get("quote") or {}).get("mid", 0))
    after_mid = float((after.get("quote") or {}).get("mid", 0))
    ostium_mid = float((ostium.get("quote") or {}).get("mid", 0))
    if min(before_mid, after_mid, ostium_mid) <= 0:
        raise ValueError("invalid synchronized quote")
    bracket_seconds = (after_at - before_at).total_seconds()
    if bracket_seconds <= 0:
        raise ValueError("invalid Binance quote bracket")
    interpolation_weight = (ostium_at - before_at).total_seconds() / bracket_seconds
    binance_mid = before_mid + interpolation_weight * (after_mid - before_mid)
    result = {
        "schema_version": 1, "observation_id": ostium_at.isoformat(),
        "captured_at": ostium_at.isoformat(), "ostium_symbol": expected[:-1],
        "binance_symbol": expected, "ostium_mid": ostium_mid,
        "binance_bracket_mid": binance_mid,
        "binance_interpolation_weight": interpolation_weight,
        "basis_bps": (ostium_mid / binance_mid - 1) * 10_000,
        "bracket_seconds": bracket_seconds,
        "inputs": {
            "binance_before": {"path": str(before_path.resolve()),
                                "sha256": _sha(before_path.resolve())},
            "ostium": {"path": str(ostium_path.resolve()),
                       "sha256": _sha(ostium_path.resolve())},
            "binance_after": {"path": str(after_path.resolve()),
                               "sha256": _sha(after_path.resolve())},
        },
        "performance_accessed": False, "research_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_json_atomic(output_path.resolve(), result)
    return result


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(.95 * len(ordered)) - 1]


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or statistics.pstdev(left) == 0 or statistics.pstdev(right) == 0:
        return None
    return statistics.correlation(left, right)


def evaluate(observation_paths: list[Path], native_path: Path,
             canonical_path: Path) -> dict[str, Any]:
    native, canonical = _load(native_path.resolve()), _load(canonical_path.resolve())
    observations = []
    seen = set()
    expected_symbol = canonical.get("research_symbol")
    for path in sorted(path.resolve() for path in observation_paths):
        row = _load(path)
        stamp = _stamp(row.get("captured_at"))
        if (row.get("ostium_symbol") != expected_symbol
                or row.get("binance_symbol") != canonical.get("source_symbol")
                or row.get("performance_accessed") is not False
                or stamp in seen):
            raise ValueError(f"invalid or duplicate proxy observation: {path}")
        seen.add(stamp)
        observations.append((stamp, row, path))
    observations.sort(key=lambda item: item[0])
    abs_basis = [abs(float(row["basis_bps"])) for _, row, _ in observations]
    brackets = [float(row["bracket_seconds"]) for _, row, _ in observations]
    ostium_returns, binance_returns = [], []
    for (_, previous, _), (_, current, _) in zip(observations, observations[1:]):
        ostium_returns.append(float(current["ostium_mid"]) /
                              float(previous["ostium_mid"]) - 1)
        binance_returns.append(float(current["binance_bracket_mid"]) /
                               float(previous["binance_bracket_mid"]) - 1)
    correlation = _correlation(ostium_returns, binance_returns)
    return_errors = [abs(left - right) * 10_000 for left, right in
                     zip(ostium_returns, binance_returns)]
    dates = {stamp.date() for stamp, _, _ in observations}
    hours = {stamp.hour for stamp, _, _ in observations}
    span_days = ((observations[-1][0] - observations[0][0]).total_seconds() / 86400
                 if len(observations) > 1 else 0)
    reasons = []
    if canonical.get("decision") != "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED":
        reasons.append("CANONICAL_H4_PROXY_SOURCE_INVALID")
    if native.get("decision") != "READY_FOR_PARITY":
        reasons.append("OSTIUM_NATIVE_60D_COVERAGE_MISSING")
    if len(observations) < MIN_OBSERVATIONS: reasons.append("PAIRED_OBSERVATIONS_LT_240")
    if len(dates) < MIN_DAYS or span_days < MIN_DAYS: reasons.append("PAIRED_SPAN_LT_60_DAYS")
    if len(hours) < MIN_HOURS: reasons.append("PAIRED_UTC_HOURS_LT_12")
    if not brackets or max(brackets) > MAX_BRACKET_SECONDS:
        reasons.append("QUOTE_BRACKET_TOO_WIDE")
    median_basis = statistics.median(abs_basis) if abs_basis else None
    p95_basis = _p95(abs_basis) if abs_basis else None
    p95_return_error = _p95(return_errors) if return_errors else None
    if median_basis is None or median_basis > MAX_MEDIAN_ABS_BASIS_BPS:
        reasons.append("MEDIAN_ABS_BASIS_GT_10_BPS")
    if p95_basis is None or p95_basis > MAX_P95_ABS_BASIS_BPS:
        reasons.append("P95_ABS_BASIS_GT_25_BPS")
    if correlation is None or correlation < MIN_RETURN_CORRELATION:
        reasons.append("SYNCHRONIZED_RETURN_CORRELATION_LT_0_999")
    if p95_return_error is None or p95_return_error > MAX_P95_RETURN_ERROR_BPS:
        reasons.append("P95_SYNCHRONIZED_RETURN_ERROR_GT_10_BPS")
    passed = not reasons
    return {
        "schema_version": 1, "gate_id": "crypto-binance-ostium-proxy-mapping-v4",
        "decision": "PASS_CRYPTO_PROXY_MAPPING" if passed else "WARMING",
        "symbol": expected_symbol, "observations": len(observations),
        "distinct_utc_dates": len(dates), "distinct_utc_hours": len(hours),
        "observed_span_days": span_days, "maximum_bracket_seconds": max(brackets, default=None),
        "median_absolute_basis_bps": median_basis,
        "p95_absolute_basis_bps": p95_basis,
        "synchronized_return_correlation": correlation,
        "p95_synchronized_return_error_bps": p95_return_error,
        "thresholds": {"minimum_observations": MIN_OBSERVATIONS,
                       "minimum_days": MIN_DAYS, "minimum_utc_hours": MIN_HOURS,
                       "maximum_bracket_seconds": MAX_BRACKET_SECONDS,
                       "maximum_median_absolute_basis_bps": MAX_MEDIAN_ABS_BASIS_BPS,
                       "maximum_p95_absolute_basis_bps": MAX_P95_ABS_BASIS_BPS,
                       "minimum_return_correlation": MIN_RETURN_CORRELATION,
                       "maximum_p95_return_error_bps": MAX_P95_RETURN_ERROR_BPS},
        "blocking_reasons": reasons,
        "canonical": {"path": str(canonical_path.resolve()), "sha256": _sha(canonical_path.resolve())},
        "native_coverage": {"path": str(native_path.resolve()), "sha256": _sha(native_path.resolve())},
        "observation_files": [{"path": str(path), "sha256": _sha(path)}
                              for _, _, path in observations],
        "selection_basis": "synchronized_price_mapping_only_no_strategy_returns",
        "performance_accessed": False, "holdout_accessed": False,
        "research_authorized": passed, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe")
    for name in ("before", "ostium", "after", "output"):
        observe.add_argument(f"--{name}", required=True, type=Path)
    gate = sub.add_parser("gate")
    gate.add_argument("--observations", required=True)
    gate.add_argument("--native", required=True, type=Path)
    gate.add_argument("--canonical", required=True, type=Path)
    gate.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "observe":
        result = make_observation(args.before, args.ostium, args.after, args.output)
    else:
        result = evaluate([Path(path) for path in glob.glob(args.observations)],
                          args.native, args.canonical)
        write_json_atomic(args.output.resolve(), result)
    print(json.dumps({key: result.get(key) for key in
                      ("decision", "observations", "blocking_reasons")}, indent=2))


if __name__ == "__main__":
    main()
