#!/usr/bin/env python3
"""Compile the sealed, performance-blind crypto H4 experiment design."""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


PROFILE_BY_MECHANISM = {
    "channel_breakout": "crypto_h4_channel_breakout_v4",
    "time_series_momentum": "crypto_h4_time_series_momentum_v4",
    "volatility_compression_breakout":
        "crypto_h4_volatility_compression_breakout_v4",
}
ATTEMPTS = 5_000


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("preregistration must be a JSON object")
    return value


def _integers(low: Any, high: Any, step: Any = 1) -> list[int]:
    low_i, high_i, step_i = int(low), int(high), int(step)
    if low_i != low or high_i != high or step_i != step or step_i <= 0:
        raise ValueError("invalid integer parameter range")
    return list(range(low_i, high_i + 1, step_i))


def _decimals(low: Any, high: Any, step: Any) -> list[float]:
    low_d, high_d, step_d = Decimal(str(low)), Decimal(str(high)), Decimal(str(step))
    if step_d <= 0 or high_d < low_d or (high_d - low_d) % step_d:
        raise ValueError("invalid decimal parameter range")
    count = int((high_d - low_d) / step_d) + 1
    return [float(low_d + index * step_d) for index in range(count)]


def parameter_axes(profile_name: str, ranges: dict[str, Any]) -> dict[str, list[Any]]:
    axes: dict[str, list[Any]] = {
        "indicator_period": _integers(ranges["indicator_period_min"],
                                      ranges["indicator_period_max"]),
        "shift": _integers(ranges["shift_min"], ranges["shift_max"]),
        "exit_after_bars": _integers(ranges["exit_after_bars_min"],
                                     ranges["exit_after_bars_max"],
                                     ranges["exit_after_bars_step"]),
        "atr_stop_multiple": _decimals(ranges["atr_stop_multiple_min"],
                                       ranges["atr_stop_multiple_max"],
                                       ranges["atr_stop_multiple_step"]),
    }
    if profile_name == "crypto_h4_time_series_momentum_v4":
        axes["roc_threshold_pct"] = _decimals(
            ranges["roc_threshold_min"], ranges["roc_threshold_max"],
            ranges["roc_threshold_step"])
    elif profile_name == "crypto_h4_volatility_compression_breakout_v4":
        axes["compression_lookback"] = _integers(
            ranges["compression_lookback_min"], ranges["compression_lookback_max"])
        axes["compression_percentile"] = _integers(
            ranges["compression_percentile_min"],
            ranges["compression_percentile_max"],
            ranges["compression_percentile_step"])
    elif profile_name != "crypto_h4_channel_breakout_v4":
        raise ValueError(f"unsupported profile: {profile_name}")
    return axes


def _point(seed: str, counter: int, axes: dict[str, list[Any]]) -> dict[str, Any]:
    result = {}
    for index, (name, values) in enumerate(axes.items()):
        digest = hashlib.sha256(f"{seed}|{counter}|{index}|{name}".encode()).digest()
        result[name] = values[int.from_bytes(digest[:8], "big") % len(values)]
    return result


def iter_unique_points(seed: str, axes: dict[str, list[Any]],
                       count: int = ATTEMPTS) -> Iterator[dict[str, Any]]:
    cardinality = 1
    for values in axes.values():
        cardinality *= len(values)
    if count > cardinality:
        raise ValueError("requested experiment exceeds parameter-grid cardinality")
    seen: set[bytes] = set()
    counter = 0
    # Hash sampling is deterministic and avoids ordering bias from a rectangular
    # prefix. Rejection only removes duplicate joint points.
    while len(seen) < count:
        if counter >= count * 50:
            raise RuntimeError("unable to compile enough unique experiment points")
        point = _point(seed, counter, axes)
        encoded = _canonical(point)
        counter += 1
        if encoded in seen:
            continue
        seen.add(encoded)
        yield point


def compile_design(preregistration_path: Path,
                   output_dir: Path | None = None) -> dict[str, Any]:
    preregistration_path = preregistration_path.resolve()
    prereg = _load(preregistration_path)
    hypotheses = prereg.get("directed_hypotheses") or {}
    budgets = prereg.get("budgets") or {}
    if (prereg.get("schema_version") != 1
            or prereg.get("preregistration_id") != "crypto-h4-alquimia-v4"
            or prereg.get("registration_closed") is not True
            or prereg.get("performance_accessed") is not False
            or prereg.get("legacy_candidates_reused") is not False
            or prereg.get("capital_usdc") != 200
            or hypotheses.get("mechanisms") != list(PROFILE_BY_MECHANISM)
            or hypotheses.get("directions") != ["both", "long", "short"]
            or hypotheses.get("count_total") != 18
            or budgets.get("hypothesis_screen_attempts_per_directed_hypothesis") != ATTEMPTS
            or budgets.get("accepted_candidates_global_budget_shared_with_all_v4_campaigns") != 60):
        raise ValueError("crypto H4 preregistration contract changed")

    branches = []
    combined = hashlib.sha256()
    for market, market_plan in (prereg.get("markets") or {}).items():
        if market not in ("BTCUSD", "ETHUSD"):
            raise ValueError("unexpected crypto H4 market")
        for mechanism in hypotheses["mechanisms"]:
            profile = PROFILE_BY_MECHANISM[mechanism]
            ranges = (prereg.get("profile_parameter_ranges") or {}).get(profile)
            if not isinstance(ranges, dict):
                raise ValueError(f"missing profile ranges: {profile}")
            axes = parameter_axes(profile, ranges)
            cardinality = 1
            for values in axes.values():
                cardinality *= len(values)
            for direction in hypotheses["directions"]:
                hypothesis_id = f"{market.lower()}_{mechanism}_{direction}_v4"
                seed = f"{prereg['preregistration_id']}|{hypothesis_id}"
                digest = hashlib.sha256()
                rows = [] if output_dir is not None else None
                for attempt, parameters in enumerate(iter_unique_points(seed, axes), 1):
                    row = {"attempt": attempt, "parameters": parameters}
                    encoded = _canonical(row)
                    digest.update(encoded)
                    combined.update(hypothesis_id.encode() + b"\0" + encoded)
                    if rows is not None:
                        rows.append(row)
                branch = {
                    "hypothesis_id": hypothesis_id,
                    "campaign_id": market_plan["campaign_id"], "market": market,
                    "timeframe": "H4", "mechanism": mechanism,
                    "direction": direction, "profile": profile,
                    "attempts": ATTEMPTS, "grid_cardinality": cardinality,
                    "seed": seed, "points_sha256": digest.hexdigest(),
                    "parameter_axes": {name: {"count": len(values),
                                               "minimum": values[0],
                                               "maximum": values[-1]}
                                       for name, values in axes.items()},
                }
                if rows is not None:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    points_path = output_dir / f"{hypothesis_id}.jsonl"
                    points_path.write_bytes(b"".join(_canonical(row) for row in rows))
                    branch["points_path"] = str(points_path.resolve())
                    branch["points_file_sha256"] = _sha(points_path)
                branches.append(branch)
    if len(branches) != 18 or sum(row["attempts"] for row in branches) != 90_000:
        raise ValueError("compiled experiment does not contain the sealed 18x5000 design")
    return {
        "schema_version": 1, "stage": "experiment_design",
        "preregistration": {"path": str(preregistration_path),
                            "sha256": _sha(preregistration_path)},
        "capital_usdc": 200, "directed_hypotheses": 18,
        "attempts_per_directed_hypothesis": ATTEMPTS,
        "total_screen_points": 90_000,
        "accepted_candidates_global_budget": 60,
        "sampling_method": "sha256_seeded_unique_joint_grid_v1",
        "branches": branches, "combined_points_sha256": combined.hexdigest(),
        "selection_basis": "sealed_parameter_design_only_no_market_data",
        "market_data_accessed": False, "performance_accessed": False,
        "holdout_accessed": False, "research_authorized": False,
        "sqcli_authorized": False, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--points-dir", type=Path)
    args = parser.parse_args()
    result = compile_design(args.preregistration, args.points_dir)
    write_atomic(args.output.resolve(), result)
    print(json.dumps({key: result[key] for key in (
        "directed_hypotheses", "total_screen_points",
        "accepted_candidates_global_budget", "combined_points_sha256",
        "performance_accessed")}, indent=2))


if __name__ == "__main__":
    main()
