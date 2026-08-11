#!/usr/bin/env python3
"""Fail-closed, chunked and resumable crypto H4 train-screen worker."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_experiment_design_v4 import (
    iter_unique_points, parameter_axes,
)
from lab.sq_bridge.crypto_h4_signal_semantics_v4 import verify as verify_semantics
from lab.sq_bridge.crypto_h4_train_engine_v4 import evaluate_point, load_train
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


DEFAULT_CHUNK_SIZE = 25


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verified_receipt(preflight: dict[str, Any], label: str) -> tuple[Path, dict[str, Any]]:
    receipt = ((preflight.get("input_receipts") or {}).get(label) or {})
    path = Path(str(receipt.get("path", "")))
    if not path.is_file() or receipt.get("sha256") != _sha(path):
        raise ValueError(f"preflight {label} receipt changed")
    return path, _load(path)


def _date(value: str, *, end: bool = False) -> datetime:
    stamp = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return stamp.replace(hour=20) if end else stamp


def _compact(attempt: int, parameters: dict[str, Any], result: dict[str, Any]) -> dict:
    scenarios = result["scenarios"]
    return {
        "attempt": attempt, "parameters": parameters,
        "decision": result["decision"], "closed_trades": result["closed_trades"],
        "scenarios": {name: {key: scenarios[name][key] for key in (
            "net_pnl_usdc", "expectancy_usdc_per_trade", "profit_factor",
            "max_drawdown_usdc", "positive_calendar_years_ratio")}
            for name in ("base", "conservative", "stress")},
    }


def _expected_points(branch: dict[str, Any], prereg: dict[str, Any],
                     stop: int) -> list[dict[str, Any]]:
    ranges = prereg["profile_parameter_ranges"][branch["profile"]]
    axes = parameter_axes(branch["profile"], ranges)
    return list(itertools.islice(
        iter_unique_points(branch["seed"], axes, branch["attempts"]), stop))


def load_branch_rows(branch_dir: Path, branch: dict[str, Any],
                     prereg: dict[str, Any], bindings: dict[str, str]) -> list[dict[str, Any]]:
    files = sorted(branch_dir.glob("chunk_*.json")) if branch_dir.is_dir() else []
    completed = 0
    all_rows: list[dict[str, Any]] = []
    expected = _expected_points(branch, prereg, branch["attempts"]) if files else []
    for path in files:
        artifact = _load(path)
        rows = artifact.get("rows")
        start, end = artifact.get("start_attempt"), artifact.get("end_attempt")
        if (artifact.get("schema_version") != 1
                or artifact.get("hypothesis_id") != branch["hypothesis_id"]
                or artifact.get("bindings") != bindings
                or not isinstance(rows, list) or not rows
                or start != completed + 1 or end != completed + len(rows)
                or path.name != f"chunk_{start:06d}_{end:06d}.json"):
            raise ValueError(f"invalid or non-contiguous screen chunk: {path}")
        for offset, row in enumerate(rows, completed):
            if (row.get("attempt") != offset + 1
                    or row.get("parameters") != expected[offset]):
                raise ValueError(f"screen chunk does not replay design: {path}")
        all_rows.extend(rows)
        completed = end
    if completed > branch["attempts"]:
        raise ValueError("screen branch exceeds sealed attempt budget")
    return all_rows


def _resume_count(branch_dir: Path, branch: dict[str, Any], prereg: dict[str, Any],
                  bindings: dict[str, str]) -> int:
    return len(load_branch_rows(branch_dir, branch, prereg, bindings))


def run(*, preflight_path: Path, design_path: Path, semantics_path: Path,
        output_dir: Path, max_chunks: int = 1,
        chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict[str, Any]:
    preflight_path = preflight_path.resolve()
    preflight = _load(preflight_path)
    # Critical ordering: BLOCK never touches design, semantics, source, costs or output.
    if (preflight.get("decision") != "PASS"
            or preflight.get("research_authorized") is not True
            or preflight.get("next_stage_authorized") != "hypothesis_screen"):
        return {"schema_version": 1, "decision": "WAITING_FOR_MARKET_PREFLIGHT",
                "campaign_id": preflight.get("campaign_id"),
                "blocking_reasons": preflight.get("blocking_reasons", []),
                "market_data_accessed": False, "performance_accessed": False,
                "sqcli_started": False, "state_created": False,
                "paper_authorized": False, "live_authorized": False}
    if max_chunks <= 0 or chunk_size <= 0 or chunk_size > 250:
        raise ValueError("invalid bounded worker budget")

    design_path, semantics_path = design_path.resolve(), semantics_path.resolve()
    design, semantics = _load(design_path), verify_semantics(semantics_path)
    if (not semantics["valid"]
            or semantics["contract"].get("experiment_design_sha256") != _sha(design_path)
            or design.get("stage") != "experiment_design"
            or design.get("performance_accessed") is not False):
        raise ValueError("sealed experiment design/semantics invalid")
    prereg_path = Path(design["preregistration"]["path"])
    if (not prereg_path.is_file()
            or design["preregistration"]["sha256"] != _sha(prereg_path)):
        raise ValueError("experiment preregistration changed")
    prereg = _load(prereg_path)
    campaign_id, market = preflight.get("campaign_id"), preflight.get("market")
    market_plan = (prereg.get("markets") or {}).get(market) or {}
    if (market_plan.get("campaign_id") != campaign_id
            or preflight.get("account_usdc") != 200
            or preflight.get("timeframe") != "H4"):
        raise ValueError("preflight campaign does not match experiment")

    canonical_path, canonical = _verified_receipt(preflight, "canonical_source")
    costs_path, costs = _verified_receipt(preflight, "costs")
    source = Path(str(canonical.get("canonical_path", "")))
    if (canonical.get("research_symbol") != market or not source.is_file()
            or canonical.get("canonical_sha256") != _sha(source)):
        raise ValueError("canonical train source changed")
    if (costs.get("decision") != "PASS_COSTS_FROZEN"
            or costs.get("costs_frozen") is not True
            or not (costs.get("by_notional") or {}).get("200")):
        raise ValueError("Ostium 200 USDC costs are not frozen")
    split = market_plan["temporal_split_utc"]["train"]
    bars = load_train(source, _date(split[0]), _date(split[1], end=True))

    bindings = {"preflight_sha256": _sha(preflight_path),
                "design_sha256": _sha(design_path),
                "semantics_sha256": _sha(semantics_path),
                "canonical_receipt_sha256": _sha(canonical_path),
                "source_sha256": _sha(source), "costs_sha256": _sha(costs_path)}
    branches = [row for row in design["branches"] if row["market"] == market]
    chunks_written = 0
    progress = {}
    output_dir = output_dir.resolve()
    for branch in branches:
        branch_dir = output_dir / branch["hypothesis_id"]
        completed = _resume_count(branch_dir, branch, prereg, bindings)
        while completed < branch["attempts"] and chunks_written < max_chunks:
            end = min(branch["attempts"], completed + chunk_size)
            points = _expected_points(branch, prereg, end)[completed:end]
            rows = []
            for attempt, parameters in enumerate(points, completed + 1):
                result = evaluate_point(bars, branch["mechanism"],
                                        branch["direction"], parameters, costs)
                rows.append(_compact(attempt, parameters, result))
            artifact = {"schema_version": 1,
                        "campaign_id": campaign_id,
                        "hypothesis_id": branch["hypothesis_id"],
                        "start_attempt": completed + 1, "end_attempt": end,
                        "rows": rows, "bindings": bindings,
                        "performance_scope": "train_only",
                        "validation_accessed": False, "oos_accessed": False,
                        "holdout_accessed": False, "sqcli_started": False,
                        "paper_authorized": False, "live_authorized": False}
            branch_dir.mkdir(parents=True, exist_ok=True)
            write_atomic(branch_dir / f"chunk_{completed + 1:06d}_{end:06d}.json",
                         artifact)
            completed = end; chunks_written += 1
        progress[branch["hypothesis_id"]] = {
            "completed": completed, "required": branch["attempts"]}
        if chunks_written >= max_chunks:
            break
    total_done = sum(row["completed"] for row in progress.values())
    all_complete = len(progress) == len(branches) and all(
        row["completed"] == row["required"] for row in progress.values())
    result = {"schema_version": 1,
              "decision": "SCREEN_POINTS_COMPLETE" if all_complete else "SCREEN_RUNNING",
              "campaign_id": campaign_id, "market": market,
              "chunks_written": chunks_written, "progress": progress,
              "completed_points_seen": total_done,
              "market_data_accessed": True, "performance_accessed": True,
              "performance_scope": "train_only", "validation_accessed": False,
              "oos_accessed": False, "holdout_accessed": False,
              "sqcli_started": False, "paper_authorized": False,
              "live_authorized": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(output_dir / "worker_status.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--semantics", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-chunks", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    args = parser.parse_args()
    result = run(preflight_path=args.preflight, design_path=args.design,
                 semantics_path=args.semantics, output_dir=args.output_dir,
                 max_chunks=args.max_chunks, chunk_size=args.chunk_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
