"""Canonical observation-position split contract shared by Python and SQ v4."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(contract: dict) -> str:
    return hashlib.sha256(json.dumps(
        contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _days(source: Path) -> list[date]:
    values = []
    for line in source.read_text().splitlines():
        try:
            values.append(date.fromisoformat(line.split(",", 1)[0].replace(".", "-")))
        except (IndexError, ValueError) as exc:
            raise ValueError("invalid canonical date in temporal source") from exc
    if not values or values != sorted(set(values)):
        raise ValueError("temporal source dates must be non-empty, unique and ordered")
    return values


def build_contract(source: Path, methodology_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    if methodology.get("schema_version") != 4:
        raise ValueError("temporal split contract requires methodology v4")
    split = methodology["temporal_split"]
    names = ("train", "validation", "oos", "final_holdout")
    percentages = [split[f"{name}_pct"] for name in names]
    if sum(percentages) != 100:
        raise ValueError("temporal split percentages must sum to 100")
    days = _days(source)
    cumulative, cuts = 0, []
    for percentage in percentages[:-1]:
        cumulative += percentage
        cuts.append(math.floor(len(days) * cumulative / 100))
    embargo = split["embargo_bars"]
    raw_ranges = ((0, cuts[0] - 1),
                  (cuts[0] + embargo, cuts[1] - 1),
                  (cuts[1] + embargo, cuts[2] - 1),
                  (cuts[2] + embargo, len(days) - 1))
    segments = {}
    for name, (first, last) in zip(names, raw_ranges):
        if first > last or first < 0 or last >= len(days):
            raise ValueError(f"temporal segment {name} empty after embargo")
        segments[name] = {
            "first_row_index": first, "last_row_index": last,
            "rows": last - first + 1,
            "from": days[first].isoformat(), "to": days[last].isoformat(),
        }
    return {
        "schema_version": 1,
        "contract_type": "observation_position_temporal_split_v4",
        "methodology_id": methodology["methodology_id"],
        "methodology_sha256": sha256(methodology_path),
        "source_path": str(source.resolve()), "source_sha256": sha256(source),
        "source_rows": len(days), "source_first": days[0].isoformat(),
        "source_last": days[-1].isoformat(), "percentages": dict(zip(names, percentages)),
        "rounding": "floor_cumulative_observation_count",
        "embargo_bars_before_each_post_train_segment": embargo,
        "segments": segments,
    }


def sq_periods(contract: dict) -> dict[str, str]:
    segments = contract["segments"]
    return {
        "train_from": segments["train"]["from"],
        "train_to": segments["train"]["to"],
        "validation_from": segments["validation"]["from"],
        "validation_to": segments["validation"]["to"],
        "oos_from": segments["oos"]["from"],
        "oos_to": segments["oos"]["to"],
        "holdout_from": segments["final_holdout"]["from"],
        "holdout_to": segments["final_holdout"]["to"],
    }
