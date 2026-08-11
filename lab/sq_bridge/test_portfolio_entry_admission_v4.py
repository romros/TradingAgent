import pytest

from lab.sq_bridge.portfolio_entry_admission_v4 import admit


def portfolio():
    return {"stage": "portfolio_construction", "decision": "PASS",
            "candidate_ids": ["a", "b", "c", "d"],
            "holdout_accessed": False, "paper_authorized": False,
            "aggregate_risk_policy": {
                "maximum_concurrent_positions": 2,
                "maximum_concurrent_stop_risk_pct": 3,
                "maximum_concurrent_capital_commitment_pct": 60}}


def sizing(candidate="a", risk=3, commitment=50):
    return {"decision": "PASS_PAPER_ENTRY_SIZING", "order_sent": False,
            "candidate_id": candidate, "equity_usdc": 200,
            "actual_stop_risk_usdc": risk,
            "capital_committed_usdc": commitment}


def active(candidate="b", risk=3, commitment=50):
    return {"allocation_id": "ostium:2:0", "candidate_id": candidate,
            "stop_risk_usdc": risk, "capital_commitment_usdc": commitment}


def test_first_and_second_controlled_entries_pass_without_sending():
    first = admit(portfolio=portfolio(), sizing=sizing(), active_allocations=[])
    assert first["decision"] == "PASS_PORTFOLIO_ENTRY_ADMISSION"
    second = admit(portfolio=portfolio(), sizing=sizing("a"),
                   active_allocations=[active()])
    assert second["decision"] == "PASS_PORTFOLIO_ENTRY_ADMISSION"
    assert second["projected_stop_risk_pct"] == 3
    assert second["projected_capital_commitment_pct"] == 50
    assert second["order_sent"] is False


def test_third_position_and_excess_commitment_block_together():
    rows = [active("b"), {**active("c"), "allocation_id": "ostium:2:1"}]
    result = admit(portfolio=portfolio(), sizing=sizing("a", commitment=30),
                   active_allocations=rows)
    assert result["decision"] == "BLOCK_PORTFOLIO_ENTRY_ADMISSION"
    assert "concurrent_position_limit" in result["blocking_reasons"]
    assert "aggregate_stop_risk_limit" in result["blocking_reasons"]
    assert "aggregate_capital_commitment_limit" in result["blocking_reasons"]


def test_duplicate_candidate_and_foreign_candidate_fail_closed():
    result = admit(portfolio=portfolio(), sizing=sizing("b"),
                   active_allocations=[active("b")])
    assert result["decision"] == "BLOCK_PORTFOLIO_ENTRY_ADMISSION"
    assert "candidate_already_active" in result["blocking_reasons"]
    with pytest.raises(ValueError, match="not authorized"):
        admit(portfolio=portfolio(), sizing=sizing("foreign"), active_allocations=[])
