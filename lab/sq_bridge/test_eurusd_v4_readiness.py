import json
from pathlib import Path

from lab.sq_bridge.eurusd_v4_readiness import build
from lab.sq_bridge.ostium_small_account_cost_gate_v4 import (
    REQUIRED_NOTIONALS_USDC, derive,
)


ROOT = Path(__file__).parents[2]


def write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value))
    return path


def incomplete_summary() -> dict:
    distribution = {"n": 3, "p50": 4.0, "p95": 6.0}
    return {
        "schema_version": 1,
        "instrument": {"pair_id": "2", "pair_from": "EUR", "pair_to": "USD"},
        "gate": {"execution_economics": "INSUFFICIENT_OPEN_MARKET_EVIDENCE",
                 "checks": {"open_samples": {"actual": 6},
                            "distinct_utc_days": {"actual": 1},
                            "distinct_utc_hours": {"actual": 4}}},
        "roundtrip_proxy_bps_by_notional": {
            str(value): {"direction_neutral": dict(distribution)}
            for value in REQUIRED_NOTIONALS_USDC},
    }


def setup_contract(tmp_path: Path, summary_value=None) -> tuple[Path, Path, Path]:
    summary = write(tmp_path / "summary.json", summary_value or incomplete_summary())
    raw = summary.read_bytes()
    costs = derive(json.loads(raw), expected_pair_id="2", expected_pair=("EUR", "USD"))
    import hashlib
    costs["source_sha256"] = hashlib.sha256(raw).hexdigest()
    costs_path = write(tmp_path / "costs.json", costs)
    config = write(tmp_path / "config.json", {
        "schema_version": 1, "preflight_composer": "eurusd_d1_v4",
        "campaign_id": "eurusd-d1-alquimia-v4", "ostium_pair_id": "EUR/USD",
        "coverage": str(ROOT / "lab/sq_bridge/evidence/eurusd_d1_historical_coverage_v4.json"),
        "mapping": str(ROOT / "lab/sq_bridge/evidence/eurusd_d1_bridge_mapping_v4.json"),
        "sq_resource": str(ROOT / "lab/sq_bridge/evidence/eurusd_alq_ny17_d1_resource_audit_v4.json"),
        "costs": str(costs_path),
    })
    return summary, costs_path, config


def test_reports_real_slowest_bucket_without_authorizing_sqcli(tmp_path):
    summary, costs, config = setup_contract(tmp_path)
    result = build(summary, costs, config)
    assert result["status"] == "COLLECTING_COSTS"
    assert result["remaining_complete_captures_lower_bound"] == 27
    assert result["notional_observations"]["14000"] == 3
    assert result["next_stage_authorized"] is None
    assert result["sqcli_authorized"] is False


def test_rejects_a_stale_or_edited_cost_artifact(tmp_path):
    summary, costs, config = setup_contract(tmp_path)
    value = json.loads(costs.read_text())
    value["remaining_complete_captures_lower_bound"] = 0
    write(costs, value)
    result = build(summary, costs, config)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "COST_ARTIFACT_STALE_OR_TAMPERED" in result["errors"]


def test_mature_evidence_authorizes_only_the_hypothesis_screen(tmp_path):
    value = incomplete_summary()
    value["gate"] = {
        "execution_economics": "PASS",
        "checks": {"open_samples": {"actual": 30},
                   "distinct_utc_days": {"actual": 3},
                   "distinct_utc_hours": {"actual": 6}},
    }
    distribution = {"n": 30, "p50": 4.0, "p95": 6.0}
    value["roundtrip_proxy_bps_by_notional"] = {
        str(notional): {route: dict(distribution)
                        for route in ("direction_neutral", "long", "short")}
        for notional in REQUIRED_NOTIONALS_USDC}
    value["fees"] = {
        "rollover_long_pct_per_8h": {"p50": -0.001},
        "rollover_short_pct_per_8h": {"p50": -0.001},
    }
    value["limits"] = {"max_leverage": {"p50": 200}}
    summary, costs, config = setup_contract(tmp_path, value)
    result = build(summary, costs, config)
    assert result["status"] == "READY_HYPOTHESIS_SCREEN"
    assert result["next_stage_authorized"] == "hypothesis_screen"
    assert result["sqcli_authorized"] is False
