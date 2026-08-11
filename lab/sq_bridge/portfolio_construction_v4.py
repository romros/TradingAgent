#!/usr/bin/env python3
"""Select a preregistered 4-8 strategy portfolio before final holdout access."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from pathlib import Path
from typing import Any

from lab.sq_bridge.methodology import validate as validate_methodology
from lab.sq_bridge.small_account_trace_v4 import rebuild_from_trace


HYPOTHESIS_ID = re.compile(r"^[a-z0-9][a-z0-9_]{2,79}$")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: object, label: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(f"{label} invalid")
    return float(value)


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _series(rows: object, candidate_id: str) -> dict[str, float]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"stress PnL series missing: {candidate_id}")
    result: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"stress PnL row invalid: {candidate_id}")
        timestamp = row.get("exit_timestamp")
        if (not isinstance(timestamp, str) or not timestamp.endswith("+00:00")
                or timestamp in result):
            raise ValueError(f"stress PnL timestamp invalid: {candidate_id}")
        result[timestamp] = _number(row.get("pnl_usdc"), "stress PnL")
    if list(result) != sorted(result):
        raise ValueError(f"stress PnL series not ordered: {candidate_id}")
    return result


def _intervals(rows: object, candidate_id: str) -> list[dict[str, float | str]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"commitment intervals missing: {candidate_id}")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"commitment interval invalid: {candidate_id}")
        entry, exit_ = row.get("entry_timestamp"), row.get("exit_timestamp")
        if (not isinstance(entry, str) or not isinstance(exit_, str)
                or not entry.endswith("+00:00") or not exit_.endswith("+00:00")
                or exit_ <= entry):
            raise ValueError(f"commitment timestamps invalid: {candidate_id}")
        risk = _number(row.get("stop_risk_usdc"), "stop risk")
        commitment = _number(row.get("capital_commitment_usdc"), "capital commitment")
        if risk <= 0 or commitment <= 0:
            raise ValueError(f"commitment amount invalid: {candidate_id}")
        result.append({"entry_timestamp": entry, "exit_timestamp": exit_,
                       "stop_risk_usdc": risk,
                       "capital_commitment_usdc": commitment})
    if result != sorted(result, key=lambda row: (row["entry_timestamp"], row["exit_timestamp"])):
        raise ValueError(f"commitment intervals not ordered: {candidate_id}")
    return result


def _source_hypothesis(artifact: dict[str, Any], artifact_path: Path,
                       candidate_id: str) -> str:
    robustness_path = _resolve(
        artifact_path.parent, artifact.get("robustness_artifact_path"),
        artifact.get("robustness_artifact_sha256"), "portfolio robustness lineage")
    robustness = json.loads(robustness_path.read_text())
    temporal_path = _resolve(
        robustness_path.parent, robustness.get("temporal_validation_artifact_path"),
        robustness.get("temporal_validation_artifact_sha256"),
        "portfolio temporal lineage")
    temporal = json.loads(temporal_path.read_text())
    generation_path = _resolve(
        temporal_path.parent, temporal.get("sq_generation_artifact_path"),
        temporal.get("sq_generation_artifact_sha256"),
        "portfolio generation lineage")
    generation = json.loads(generation_path.read_text())
    hypotheses = generation.get("candidate_source_hypothesis_ids")
    hypothesis = hypotheses.get(candidate_id) if isinstance(hypotheses, dict) else None
    if (generation.get("artifact_role") != "global_multi_branch_candidate_universe"
            or not isinstance(hypothesis, str) or not HYPOTHESIS_ID.fullmatch(hypothesis)):
        raise ValueError(f"directed hypothesis lineage missing: {candidate_id}")
    return hypothesis


def pair_metrics(left: dict[str, float], right: dict[str, float]) -> dict[str, float | int]:
    dates = sorted(set(left) | set(right))
    x = [left.get(day, 0.0) for day in dates]
    y = [right.get(day, 0.0) for day in dates]
    mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
    var_x = sum((value - mean_x) ** 2 for value in x)
    var_y = sum((value - mean_y) ** 2 for value in y)
    if var_x <= 0 or var_y <= 0:
        correlation = 1.0
    else:
        correlation = sum((a - mean_x) * (b - mean_y)
                          for a, b in zip(x, y, strict=True)) / math.sqrt(var_x * var_y)
    active_left, active_right = set(left), set(right)
    jaccard = len(active_left & active_right) / len(active_left | active_right)
    return {"union_exit_dates": len(dates), "daily_stress_pnl_correlation": correlation,
            "absolute_daily_stress_pnl_correlation": abs(correlation),
            "exit_date_jaccard": jaccard}


def portfolio_exposure(candidates: list[dict[str, Any]], capital_usdc: float = 200) -> dict:
    events: dict[str, list[float]] = {}
    for candidate in candidates:
        for row in candidate["commitment_intervals"]:
            entry = events.setdefault(str(row["entry_timestamp"]), [0, 0.0, 0.0])
            exit_ = events.setdefault(str(row["exit_timestamp"]), [0, 0.0, 0.0])
            entry[0] += 1
            entry[1] += float(row["stop_risk_usdc"])
            entry[2] += float(row["capital_commitment_usdc"])
            exit_[0] -= 1
            exit_[1] -= float(row["stop_risk_usdc"])
            exit_[2] -= float(row["capital_commitment_usdc"])
    concurrent, risk, commitment = 0, 0.0, 0.0
    maximum_concurrent, maximum_risk, maximum_commitment = 0, 0.0, 0.0
    for timestamp in sorted(events):
        count_delta, risk_delta, commitment_delta = events[timestamp]
        concurrent += int(count_delta)
        risk += risk_delta
        commitment += commitment_delta
        if concurrent < 0 or risk < -1e-8 or commitment < -1e-8:
            raise ValueError("portfolio exposure event sequence invalid")
        maximum_concurrent = max(maximum_concurrent, concurrent)
        maximum_risk = max(maximum_risk, risk)
        maximum_commitment = max(maximum_commitment, commitment)
    if concurrent != 0 or abs(risk) > 1e-8 or abs(commitment) > 1e-8:
        raise ValueError("portfolio exposure does not close")
    return {"maximum_concurrent_positions": maximum_concurrent,
            "maximum_concurrent_stop_risk_usdc": maximum_risk,
            "maximum_concurrent_stop_risk_pct": maximum_risk / capital_usdc * 100,
            "maximum_concurrent_capital_commitment_usdc": maximum_commitment,
            "maximum_concurrent_capital_commitment_pct":
                maximum_commitment / capital_usdc * 100}


def select(candidates: list[dict[str, Any]], gate: dict[str, Any]) -> dict[str, Any]:
    minimum, maximum = gate["minimum_strategies"], gate["maximum_strategies"]
    if (not isinstance(candidates, list) or len(candidates) > gate["maximum_candidate_pool"]
            or len(candidates) < minimum):
        return {"selected_candidate_ids": [], "pair_metrics": {},
                "reason": "CANDIDATE_COUNT_OUTSIDE_PORTFOLIO_CONTRACT"}
    ids = [row.get("candidate_id") for row in candidates]
    hypotheses = [row.get("hypothesis_id") for row in candidates]
    if (any(not isinstance(value, str) or not value for value in ids)
            or len(ids) != len(set(ids)) or ids != sorted(ids)
            or any(not isinstance(value, str) or not HYPOTHESIS_ID.fullmatch(value)
                   for value in hypotheses)
            or len(hypotheses) != len(set(hypotheses))):
        raise ValueError("candidate or directed hypothesis identity invalid")
    by_id = {row["candidate_id"]: row for row in candidates}
    pairs: dict[str, dict[str, float | int]] = {}
    compatible: dict[tuple[str, str], bool] = {}
    for left, right in itertools.combinations(ids, 2):
        metrics = pair_metrics(by_id[left]["stress_series"], by_id[right]["stress_series"])
        key = f"{left}|{right}"
        pair_passes = (
            metrics["union_exit_dates"] >= gate["minimum_union_exit_dates"]
            and metrics["absolute_daily_stress_pnl_correlation"]
                <= gate["maximum_absolute_daily_stress_pnl_correlation"]
            and metrics["exit_date_jaccard"] <= gate["maximum_exit_date_jaccard"])
        pairs[key] = {**metrics, "passes_diversification": pair_passes}
        compatible[(left, right)] = pair_passes
    best: tuple[str, ...] | None = None
    best_quality: tuple[float, float] | None = None
    best_exposure: dict | None = None
    for size in range(min(maximum, len(ids)), minimum - 1, -1):
        for combination in itertools.combinations(ids, size):
            if not all(compatible[tuple(sorted(pair))]
                       for pair in itertools.combinations(combination, 2)):
                continue
            exposure = portfolio_exposure([by_id[value] for value in combination])
            if (exposure["maximum_concurrent_positions"]
                    > gate["maximum_concurrent_positions"]
                    or exposure["maximum_concurrent_stop_risk_pct"]
                    > gate["maximum_concurrent_stop_risk_pct"] + 1e-9
                    or exposure["maximum_concurrent_capital_commitment_pct"]
                    > gate["maximum_concurrent_capital_commitment_pct"] + 1e-9):
                continue
            quality = (sum(by_id[value]["net_expectancy_usdc"] for value in combination),
                       sum(by_id[value]["net_profit_factor"] for value in combination))
            if best_quality is None or quality > best_quality:
                best, best_quality, best_exposure = combination, quality, exposure
        if best is not None:
            break
    if best is None:
        return {"selected_candidate_ids": [], "pair_metrics": pairs,
                "reason": "NO_DIVERSIFIED_SUBSET_OF_FOUR"}
    return {"selected_candidate_ids": list(best), "pair_metrics": pairs,
            "portfolio_exposure": best_exposure,
            "reason": None}


def build(*, manifest_path: Path, methodology_path: Path, output_path: Path) -> dict:
    manifest_path, methodology_path = manifest_path.resolve(), methodology_path.resolve()
    manifest = json.loads(manifest_path.read_text())
    methodology = json.loads(methodology_path.read_text())
    gate = methodology.get("portfolio_construction") or {}
    errors = validate_methodology(methodology)
    if errors:
        raise ValueError(f"methodology v4 invalid: {errors}")
    if (manifest.get("schema_version") != 1 or not isinstance(manifest.get("portfolio_id"), str)
            or manifest.get("holdout_accessed") is not False
            or gate.get("holdout_accessed") is not False):
        raise ValueError("portfolio manifest or methodology invalid")
    sources = manifest.get("small_account_branches")
    if not isinstance(sources, list):
        raise ValueError("small-account branch inventory missing")
    candidates, source_receipts, cost_hashes = [], {}, {}
    for source in sources:
        hypothesis = source.get("hypothesis_id") if isinstance(source, dict) else None
        source_campaign = source.get("campaign_id") if isinstance(source, dict) else None
        if not isinstance(hypothesis, str) or not HYPOTHESIS_ID.fullmatch(hypothesis):
            raise ValueError("directed hypothesis identity invalid")
        if not isinstance(source_campaign, str) or not source_campaign:
            raise ValueError("source campaign identity invalid")
        artifact_path = _resolve(
            manifest_path.parent, source.get("artifact_path"), source.get("artifact_sha256"),
            f"small-account artifact {hypothesis}")
        artifact = json.loads(artifact_path.read_text())
        ids = artifact.get("candidate_ids")
        if (artifact.get("stage") != "small_account_economics"
                or artifact.get("decision") != "PASS"
                or artifact.get("campaign_id") != source_campaign
                or artifact.get("holdout_accessed") is not False
                or not isinstance(ids, list) or len(ids) != 1):
            raise ValueError(f"small-account branch not promotable: {hypothesis}")
        candidate_id = ids[0]
        metrics = (artifact.get("evaluated_candidate_small_account_metrics") or {}).get(
            candidate_id)
        trace_path = _resolve(
            artifact_path.parent,
            (artifact.get("small_account_trace_paths") or {}).get(candidate_id),
            (artifact.get("small_account_trace_sha256") or {}).get(candidate_id),
            f"small-account trace {candidate_id}")
        trace = json.loads(trace_path.read_text())
        if (trace.get("schema_version") != 2 or rebuild_from_trace(trace) != trace
                or not isinstance(metrics, dict)):
            raise ValueError(f"small-account source not reproducible: {candidate_id}")
        if _source_hypothesis(artifact, artifact_path, candidate_id) != hypothesis:
            raise ValueError(f"manifest hypothesis does not match lineage: {candidate_id}")
        current_cost_hash = artifact.get("cost_model_sha256")
        if not isinstance(current_cost_hash, str) or not current_cost_hash:
            raise ValueError(f"frozen cost identity missing: {candidate_id}")
        cost_hashes[candidate_id] = current_cost_hash
        candidates.append({
            "candidate_id": candidate_id, "hypothesis_id": hypothesis,
            "net_expectancy_usdc": _number(artifact.get("net_expectancy_usdc"), "expectancy"),
            "net_profit_factor": _number(artifact.get("net_profit_factor"), "profit factor"),
            "stress_series": _series(metrics.get("stress_pnl_by_exit_utc"), candidate_id),
            "commitment_intervals": _intervals(
                metrics.get("portfolio_commitment_intervals"), candidate_id),
        })
        source_receipts[candidate_id] = {
            "hypothesis_id": hypothesis, "campaign_id": source_campaign,
            "artifact_path": str(artifact_path),
            "artifact_sha256": _sha(artifact_path), "trace_path": str(trace_path),
            "trace_sha256": _sha(trace_path)}
    candidates.sort(key=lambda row: row["candidate_id"])
    result = select(candidates, gate)
    selected = result["selected_candidate_ids"]
    artifact = {
        "schema_version": 1, "stage": "portfolio_construction",
        "campaign_id": manifest["portfolio_id"], "portfolio_id": manifest["portfolio_id"],
        "decision": "PASS" if selected else "REJECT", "candidate_ids": selected,
        "holdout_accessed": False, "paper_authorized": False, "live_authorized": False,
        "selection_policy": gate["selection_policy"],
        "evaluated_candidate_ids": [row["candidate_id"] for row in candidates],
        "selected_hypothesis_ids": [next(row["hypothesis_id"] for row in candidates
                                         if row["candidate_id"] == candidate)
                                    for candidate in selected],
        "pair_metrics": result["pair_metrics"], "rejection_reason": result["reason"],
        "portfolio_exposure": result.get("portfolio_exposure"),
        "cost_model_sha256_by_candidate": cost_hashes,
        "source_receipts": source_receipts,
        "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
        "methodology_path": str(methodology_path),
        "methodology_sha256": _sha(methodology_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(manifest_path=args.manifest, methodology_path=args.methodology,
                   output_path=args.output)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
