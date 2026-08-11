#!/usr/bin/env python3
"""Normalize a custom-signal SQ proposal onto the preregistered H4 grid."""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from lab.sq_bridge.sqx_extract import extract


MECHANISMS = {
    "AlquimiaH4MomentumAbove": ("time_series_momentum", "long"),
    "AlquimiaH4MomentumBelow": ("time_series_momentum", "short"),
    "AlquimiaH4ChannelAbove": ("channel_breakout", "long"),
    "AlquimiaH4ChannelBelow": ("channel_breakout", "short"),
    "AlquimiaH4CompressionChannelAbove": (
        "volatility_compression_breakout", "long"),
    "AlquimiaH4CompressionChannelBelow": (
        "volatility_compression_breakout", "short"),
}


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def _nearest(value: float, minimum: float, maximum: float, step: float) -> float:
    value, minimum, maximum, step = map(Decimal, map(str, (value, minimum, maximum, step)))
    if step <= 0 or minimum > maximum or value < minimum - step or value > maximum + step:
        raise ValueError("SQ proposal outside normalizable grid envelope")
    points = []
    current = minimum
    while current <= maximum:
        points.append(current); current += step
    # Decimal distance and ascending point order make exact ties choose lower.
    return float(min(points, key=lambda point: (abs(point - value), point)))


def normalize(*, sqx: Path, manifest_path: Path, preregistration_path: Path) -> dict[str, Any]:
    sqx, manifest_path, preregistration_path = (path.resolve() for path in
                                                (sqx, manifest_path, preregistration_path))
    contract = extract(sqx); manifest = json.loads(manifest_path.read_text())
    prereg = json.loads(preregistration_path.read_text())
    active = [(side, row) for side, row in contract["entries"].items() if row is not None]
    if contract.get("translation_status") != "SUPPORTED_SUBSET" or len(active) != 1:
        raise ValueError("SQ proposal is not a single supported direction")
    side, entry = active[0]; signal = entry["signal"]; op = signal.get("op")
    if op not in MECHANISMS or MECHANISMS[op][1] != side:
        raise ValueError("SQ custom signal direction mismatch")
    mechanism = MECHANISMS[op][0]
    profile_name = f"crypto_h4_{mechanism}_v4"
    profile = prereg["profile_parameter_ranges"].get(profile_name)
    if not isinstance(profile, dict): raise ValueError("preregistered profile absent")
    action = entry["action"]["params"]
    stop = action["#StopLoss.StopLoss#"]
    raw = {"indicator_period": signal["params"]["#Period#"],
           "shift": signal["params"]["#Shift#"],
           "exit_after_bars": action["#ExitAfterBars.ExitAfterBars#"],
           "atr_stop_multiple": stop["params"]["#Value#"]}
    if mechanism == "time_series_momentum":
        raw["roc_threshold_pct"] = signal["params"]["#Level#"]
    elif mechanism == "volatility_compression_breakout":
        raw["compression_lookback"] = signal["params"]["#CompressionLookback#"]
        raw["compression_percentile"] = signal["params"]["#CompressionPercentile#"]
    axes = {"indicator_period": ("indicator_period_min", "indicator_period_max", 1),
            "shift": ("shift_min", "shift_max", 1),
            "exit_after_bars": ("exit_after_bars_min", "exit_after_bars_max",
                                profile["exit_after_bars_step"]),
            "atr_stop_multiple": ("atr_stop_multiple_min", "atr_stop_multiple_max",
                                  profile["atr_stop_multiple_step"])}
    if mechanism == "time_series_momentum":
        axes["roc_threshold_pct"] = ("roc_threshold_min", "roc_threshold_max",
                                     profile["roc_threshold_step"])
    elif mechanism == "volatility_compression_breakout":
        axes["compression_lookback"] = (
            "compression_lookback_min", "compression_lookback_max", 1)
        axes["compression_percentile"] = (
            "compression_percentile_min", "compression_percentile_max",
            profile["compression_percentile_step"])
    normalized = {key: _nearest(raw[key], profile[lo], profile[hi], step)
                  for key, (lo, hi, step) in axes.items()}
    for key in ("indicator_period", "shift", "exit_after_bars", "compression_lookback"):
        if key not in normalized:
            continue
        normalized[key] = int(normalized[key])
    local = manifest.get("parameter_search_space") or {}
    for key, value in normalized.items():
        bounds = local.get(key)
        if isinstance(bounds, dict) and not (bounds["minimum"] <= value <= bounds["maximum"]):
            raise ValueError(f"normalized {key} escaped SQ proposal region")
    return {"schema_version": 1, "decision": "PASS_NORMALIZED_SQ_PROPOSAL_NOT_CANDIDATE",
            "sqx_path": str(sqx), "sqx_sha256": _sha(sqx),
            "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
            "preregistration_path": str(preregistration_path),
            "preregistration_sha256": _sha(preregistration_path),
            "strategy_name": contract["strategy_name"], "market": manifest["market"],
            "mechanism": mechanism, "direction": side,
            "raw_parameters": raw, "normalized_parameters": normalized,
            "changed_parameters": sorted(key for key in raw if float(raw[key]) != float(normalized[key])),
            "normalization_rule": "nearest_preregistered_grid_point_exact_ties_lower",
            "performance_accessed": False, "strategy_promotion_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = normalize(sqx=args.sqx, manifest_path=args.manifest,
                       preregistration_path=args.preregistration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
