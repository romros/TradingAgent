import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from lab.sq_bridge.portfolio_construction_v4 import (
    _source_hypothesis, pair_metrics, portfolio_exposure, select,
)


GATE = {
    "minimum_strategies": 4,
    "maximum_strategies": 8,
    "maximum_candidate_pool": 12,
    "maximum_absolute_daily_stress_pnl_correlation": .7,
    "maximum_exit_date_jaccard": .8,
    "minimum_union_exit_dates": 30,
    "maximum_concurrent_positions": 2,
    "maximum_concurrent_stop_risk_pct": 3,
    "maximum_concurrent_capital_commitment_pct": 60,
}


def candidate(index: int, *, duplicate_of: int | None = None):
    offset = (index if duplicate_of is None else duplicate_of) * 10
    start = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset)
    series = {(start + timedelta(days=day)).isoformat(): 1.0 if day % 2 else -1.0
              for day in range(30)}
    interval_start = datetime(2100, 1, 1, tzinfo=timezone.utc) + timedelta(days=index * 10)
    return {"candidate_id": f"candidate-{index}",
            "hypothesis_id": f"family_{index}_long",
            "net_expectancy_usdc": 1 + index / 10,
            "net_profit_factor": 1.2 + index / 100,
            "stress_series": series,
            "commitment_intervals": [{
                "entry_timestamp": interval_start.isoformat(),
                "exit_timestamp": (interval_start + timedelta(days=1)).isoformat(),
                "stop_risk_usdc": 3, "capital_commitment_usdc": 50}]}


def test_pair_metrics_aligns_missing_exit_dates_as_zero():
    metrics = pair_metrics(candidate(0)["stress_series"], candidate(1)["stress_series"])
    assert metrics["union_exit_dates"] == 40
    assert metrics["exit_date_jaccard"] == .5
    assert metrics["absolute_daily_stress_pnl_correlation"] <= .7


def test_selects_maximum_diversified_cardinality_deterministically():
    result = select([candidate(index) for index in range(5)], GATE)
    assert result["selected_candidate_ids"] == [
        "candidate-0", "candidate-1", "candidate-2", "candidate-3", "candidate-4"]
    assert result["reason"] is None


def test_duplicate_stress_profile_is_excluded_not_counted_as_diversification():
    values = [candidate(index) for index in range(4)]
    values.append(candidate(4, duplicate_of=0))
    result = select(values, GATE)
    assert len(result["selected_candidate_ids"]) == 4
    assert not {"candidate-0", "candidate-4"} <= set(result["selected_candidate_ids"])


def test_fewer_than_four_candidates_rejects_cleanly():
    result = select([candidate(index) for index in range(3)], GATE)
    assert result["selected_candidate_ids"] == []
    assert result["reason"] == "CANDIDATE_COUNT_OUTSIDE_PORTFOLIO_CONTRACT"


def test_joint_concurrency_blocks_individually_safe_strategies():
    values = [candidate(index) for index in range(4)]
    shared = values[0]["commitment_intervals"]
    for value in values:
        value["commitment_intervals"] = shared
    exposure = portfolio_exposure(values)
    assert exposure["maximum_concurrent_positions"] == 4
    assert exposure["maximum_concurrent_stop_risk_pct"] == 6
    assert exposure["maximum_concurrent_capital_commitment_pct"] == 100
    result = select(values, GATE)
    assert result["selected_candidate_ids"] == []
    assert result["reason"] == "NO_DIVERSIFIED_SUBSET_OF_FOUR"


def test_hypothesis_identity_is_derived_from_hashed_generation_lineage(tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value, sort_keys=True) + "\n")
        return path

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    generation = write("generation.json", {
        "artifact_role": "global_multi_branch_candidate_universe",
        "candidate_source_hypothesis_ids": {"candidate": "d1_breakout_long"}})
    temporal = write("temporal.json", {
        "sq_generation_artifact_path": str(generation),
        "sq_generation_artifact_sha256": sha(generation)})
    robustness = write("robustness.json", {
        "temporal_validation_artifact_path": str(temporal),
        "temporal_validation_artifact_sha256": sha(temporal)})
    small_path = write("small.json", {})
    small = {"robustness_artifact_path": str(robustness),
             "robustness_artifact_sha256": sha(robustness)}
    assert _source_hypothesis(small, small_path, "candidate") == "d1_breakout_long"
    generation.write_text("{}\n")
    with pytest.raises(ValueError, match="generation lineage"):
        _source_hypothesis(small, small_path, "candidate")
