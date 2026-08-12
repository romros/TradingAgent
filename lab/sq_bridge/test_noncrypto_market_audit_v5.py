import json
from pathlib import Path

import pytest

from lab.sq_bridge.noncrypto_market_audit_v5 import audit


ROOT = Path(__file__).resolve().parents[2]


def test_historical_audit_is_performance_blind_and_reports_frozen_cost_inputs():
    result = audit()
    assert result["decision"] == "PARTIAL_RESEARCH_UNIVERSE_WITH_PAPER_BLOCKS"
    assert result["market_count"] == 5
    assert result["research_ready_count"] == 4
    # This is an archived Ostium input audit, not authorization under the
    # current IBKR objective. Three technically-ready cost inputs are factual.
    assert result["paper_ready_count"] == 3
    assert result["performance_accessed"] is False
    assert result["holdout_accessed"] is False
    assert result["legacy_candidates_reused"] is False
    assert {item["category"] for item in result["markets"]}.isdisjoint({"crypto"})
    gbp = next(item for item in result["markets"] if item["symbol"] == "GBPUSD")
    assert gbp["known_research_blockers"] == ["HISTORICAL_SOURCE_GAP_2024_2025"]


def _fixture(tmp_path: Path, *, category="forex", performance=False, frozen=False):
    evidence = tmp_path / "technical.json"
    evidence.write_text(json.dumps({"decision": "PASS", "performance_accessed": performance}))
    costs = tmp_path / "costs.json"
    costs.write_text(json.dumps({"decision": "PASS", "costs_frozen": frozen}))
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "audit_id": "fixture",
        "allowed_categories": ["forex", "commodity", "index", "stock"],
        "performance_accessed": False,
        "holdout_accessed": False,
        "legacy_candidates_reused": False,
        "markets": [{
            "symbol": "TEST",
            "category": category,
            "ostium_pair": "TEST/USD",
            "timeframe": "M15",
            "technical_evidence": [{
                "role": "mapping", "path": "technical.json", "decision_allowlist": ["PASS"]
            }],
            "cost_evidence": "costs.json",
        }],
    }))
    return spec


def test_rejects_crypto_before_research(tmp_path):
    with pytest.raises(ValueError, match="forbidden category"):
        audit(_fixture(tmp_path, category="crypto"), root=tmp_path)


def test_rejects_performance_tainted_technical_evidence(tmp_path):
    with pytest.raises(ValueError, match="performance_accessed=true"):
        audit(_fixture(tmp_path, performance=True), root=tmp_path)


def test_frozen_costs_can_authorize_paper_inputs(tmp_path):
    result = audit(_fixture(tmp_path, frozen=True), root=tmp_path)
    assert result["decision"] == "PASS_RESEARCH_AND_PAPER_UNIVERSE"
    assert result["paper_ready_count"] == 1
