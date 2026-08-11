import json
from pathlib import Path

from lab.sq_bridge.crypto_h4_signal_semantics_v4 import verify


ROOT = Path(__file__).resolve().parents[2]
SEMANTICS = ROOT / "lab/sq_bridge/crypto_h4_signal_semantics_v4.json"


def test_real_semantics_is_sealed_and_bound_to_design():
    result = verify(SEMANTICS)
    assert result["valid"], result["errors"]
    contract = result["contract"]
    assert contract["economics_contract"]["account_usdc"] == 200
    assert contract["position_contract"]["same_bar_priority"] == ["stop", "time_exit"]
    assert contract["temporal_contract"]["validation_accessed"] is False
    assert contract["data_gap_contract"]["imputation_allowed"] is False
    assert contract["screen_acceptance_contract"]["neighbor_definition"][
        "maximum_normalized_distance"] == .15
    assert contract["performance_accessed"] is False


def test_semantics_rejects_design_or_cost_drift(tmp_path):
    contract = json.loads(SEMANTICS.read_text())
    contract["experiment_design_path"] = str(
        ROOT / "lab/sq_bridge/evidence/crypto_h4_experiment_design_v4.json")
    contract["experiment_design_sha256"] = "0" * 64
    contract["economics_contract"]["screen_notional_usdc"] = 10_000
    path = tmp_path / "semantics.json"
    path.write_text(json.dumps(contract))
    result = verify(path)
    assert result["valid"] is False
    assert "EXPERIMENT_DESIGN_BINDING" in result["errors"]
    assert "SMALL_ACCOUNT_ECONOMICS" in result["errors"]
