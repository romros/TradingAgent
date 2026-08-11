#!/usr/bin/env python3
"""Globally replay and finalize BTC+ETH H4 stable train regions."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_region_selector_v4 import regions_for_branch, select_global
from lab.sq_bridge.crypto_h4_screen_worker_v4 import _compact, load_branch_rows
from lab.sq_bridge.crypto_h4_signal_semantics_v4 import verify as verify_semantics
from lab.sq_bridge.crypto_h4_train_engine_v4 import Bars, evaluate_point, load_train
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


MARKETS = ("BTCUSD", "ETHUSD")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _date(value: str, *, end: bool = False) -> datetime:
    stamp = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return stamp.replace(hour=20) if end else stamp


def replay_regions(regions: list[dict[str, Any]],
                   rows_by_hypothesis: dict[str, list[dict[str, Any]]],
                   bars_by_market: dict[str, Bars],
                   costs_by_market: dict[str, dict[str, Any]]) -> tuple[list[dict], int]:
    cache: dict[tuple[str, int], dict[str, Any]] = {}
    verified = []
    for region in regions:
        hypothesis = region["hypothesis_id"]
        stored = {row["attempt"]: row for row in rows_by_hypothesis[hypothesis]}
        for attempt in region["member_attempts"]:
            key = (hypothesis, attempt)
            if key not in cache:
                row = stored.get(attempt)
                if row is None:
                    raise ValueError("stable region member missing from worker rows")
                replay = evaluate_point(
                    bars_by_market[region["market"]], region["mechanism"],
                    region["direction"], row["parameters"],
                    costs_by_market[region["market"]])
                cache[key] = _compact(attempt, row["parameters"], replay)
                if cache[key] != row:
                    raise ValueError(
                        f"train replay differs for {hypothesis} attempt {attempt}")
            if cache[key]["decision"] != "PASS_POINT":
                raise ValueError("selected stable-region member no longer passes")
        verified.append(region)
    return verified, len(cache)


def _receipt(preflight: dict[str, Any], label: str) -> tuple[Path, dict[str, Any]]:
    item = ((preflight.get("input_receipts") or {}).get(label) or {})
    path = Path(str(item.get("path", "")))
    if not path.is_file() or item.get("sha256") != _sha(path):
        raise ValueError(f"preflight {label} receipt changed")
    return path, _load(path)


def _chunk_receipt(branch_dir: Path) -> dict[str, Any]:
    files = sorted(branch_dir.glob("chunk_*.json"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode() + b"\0" + bytes.fromhex(_sha(path)))
    return {"chunk_count": len(files), "ordered_chunk_chain_sha256": digest.hexdigest()}


def finalize(*, btc_preflight_path: Path, eth_preflight_path: Path,
             design_path: Path, semantics_path: Path, runtime_root: Path,
             output_path: Path) -> dict[str, Any]:
    preflight_paths = {"BTCUSD": btc_preflight_path.resolve(),
                       "ETHUSD": eth_preflight_path.resolve()}
    preflights = {market: _load(path) for market, path in preflight_paths.items()}
    # Stop before design, semantics, sources, costs, chunks or output.
    waiting = {market: value.get("blocking_reasons", [])
               for market, value in preflights.items()
               if (value.get("decision") != "PASS"
                   or value.get("research_authorized") is not True
                   or value.get("next_stage_authorized") != "hypothesis_screen")}
    if waiting:
        return {"schema_version": 1, "decision": "WAITING_FOR_BOTH_MARKET_PREFLIGHTS",
                "waiting": waiting, "market_data_accessed": False,
                "performance_accessed": False, "state_created": False,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}

    design_path, semantics_path = design_path.resolve(), semantics_path.resolve()
    design, semantics = _load(design_path), verify_semantics(semantics_path)
    if (not semantics["valid"]
            or semantics["contract"]["experiment_design_sha256"] != _sha(design_path)
            or design.get("directed_hypotheses") != 18
            or design.get("total_screen_points") != 90_000):
        raise ValueError("global crypto experiment contract invalid")
    prereg_path = Path(design["preregistration"]["path"])
    if not prereg_path.is_file() or design["preregistration"]["sha256"] != _sha(prereg_path):
        raise ValueError("crypto preregistration changed")
    prereg = _load(prereg_path)

    bars_by_market, costs_by_market, bindings_by_market = {}, {}, {}
    source_receipts, cost_receipts = {}, {}
    for market in MARKETS:
        preflight = preflights[market]
        if (preflight.get("market") != market or preflight.get("account_usdc") != 200):
            raise ValueError("market preflight identity invalid")
        canonical_path, canonical = _receipt(preflight, "canonical_source")
        costs_path, costs = _receipt(preflight, "costs")
        source = Path(str(canonical.get("canonical_path", "")))
        if (canonical.get("research_symbol") != market or not source.is_file()
                or canonical.get("canonical_sha256") != _sha(source)
                or costs.get("decision") != "PASS_COSTS_FROZEN"
                or costs.get("costs_frozen") is not True):
            raise ValueError("mature source/cost contract invalid")
        split = prereg["markets"][market]["temporal_split_utc"]["train"]
        bars_by_market[market] = load_train(source, _date(split[0]), _date(split[1], end=True))
        costs_by_market[market] = costs
        source_receipts[market] = {"path": str(source), "sha256": _sha(source)}
        cost_receipts[market] = {"path": str(costs_path), "sha256": _sha(costs_path)}
        bindings_by_market[market] = {
            "preflight_sha256": _sha(preflight_paths[market]),
            "design_sha256": _sha(design_path), "semantics_sha256": _sha(semantics_path),
            "canonical_receipt_sha256": _sha(canonical_path),
            "source_sha256": _sha(source), "costs_sha256": _sha(costs_path)}

    rows_by_hypothesis, chunk_receipts, all_regions = {}, {}, []
    for branch in design["branches"]:
        market = branch["market"]
        branch_dir = runtime_root.resolve() / market.lower() / branch["hypothesis_id"]
        rows = load_branch_rows(branch_dir, branch, prereg, bindings_by_market[market])
        if len(rows) != branch["attempts"]:
            raise ValueError(f"screen branch incomplete: {branch['hypothesis_id']}")
        rows_by_hypothesis[branch["hypothesis_id"]] = rows
        chunk_receipts[branch["hypothesis_id"]] = _chunk_receipt(branch_dir)
        all_regions.extend(regions_for_branch(rows, branch, prereg))
    verified, replayed = replay_regions(
        all_regions, rows_by_hypothesis, bars_by_market, costs_by_market)
    result = select_global(verified)
    result.update({
        "stage": "hypothesis_screen", "replay_verified": True,
        "replay_receipt": {"replayed_unique_points": replayed,
                           "sources": source_receipts, "costs": cost_receipts,
                           "chunks": chunk_receipts,
                           "design_sha256": _sha(design_path),
                           "semantics_sha256": _sha(semantics_path)},
        "market_data_accessed": True, "performance_accessed": True,
        "performance_scope": "train_only", "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False})
    write_atomic(output_path.resolve(), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-preflight", required=True, type=Path)
    parser.add_argument("--eth-preflight", required=True, type=Path)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--semantics", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = finalize(btc_preflight_path=args.btc_preflight,
                      eth_preflight_path=args.eth_preflight,
                      design_path=args.design, semantics_path=args.semantics,
                      runtime_root=args.runtime_root, output_path=args.output)
    print(json.dumps({key: result.get(key) for key in (
        "decision", "selected_candidate_ids", "waiting", "replay_verified",
        "sqcli_started")}, indent=2))


if __name__ == "__main__":
    main()
