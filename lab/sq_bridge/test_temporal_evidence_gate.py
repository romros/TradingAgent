import json
from pathlib import Path

from lab.sq_bridge.temporal_evidence_gate import evaluate, overlaps


LEDGER = json.loads(Path(__file__).with_name("temporal_evidence_ledger.json").read_text())


def proposal(claim, start, end, **extra):
    return {"family_id": "v19", "assets": ["BTCUSD", "ETHUSD", "SOLUSD"], "claim": claim, "from": start, "to": end, **extra}


def test_inclusive_overlap_treats_shared_boundary_as_collision():
    assert overlaps("2025-01-01", "2025-06-30", "2025-06-30", "2025-12-31")


def test_reused_2025h1_cannot_be_called_independent():
    result = evaluate(LEDGER, proposal("independent_validation", "2025-01-01", "2025-06-30"))
    assert result["decision"] == "BLOCK_REUSED_PERFORMANCE_PERIOD"
    assert result["independent"] is False


def test_internal_walk_forward_is_allowed_but_cannot_promote():
    result = evaluate(LEDGER, proposal("internal_walk_forward", "2021-01-01", "2025-06-30"))
    assert result["decision"] == "PASS_INTERNAL_NON_INDEPENDENT"
    assert result["performance_promotion_authorized"] is False


def test_holdout_requires_one_time_cohort_release():
    result = evaluate(LEDGER, proposal("global_holdout", "2025-07-01", "2026-06-30", cohort_id="x"))
    assert result["decision"] == "BLOCK_GLOBAL_HOLDOUT_RELEASE_REQUIRED"


def test_parity_only_does_not_consume_performance_period():
    result = evaluate(LEDGER, proposal("parity_only", "2026-08-01", "2026-10-31", performance_metrics_accessed=False))
    assert result["decision"] == "PASS_DATA_QUALITY_ONLY"


def test_parity_scope_blocks_signal_metrics():
    result = evaluate(LEDGER, proposal("parity_only", "2026-08-01", "2026-10-31", performance_metrics_accessed=True))
    assert result["decision"] == "BLOCK_PARITY_SCOPE_VIOLATION"
