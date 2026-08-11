import hashlib
import json
from pathlib import Path

from lab.sq_bridge.eurusd_v4_real_scaffold_smoke import verify_translation_surface
from lab.sq_bridge.us500_v4_hypotheses import US500_PROFILE_BLOCKS


ROOT = Path(__file__).parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_us500_profiles_have_the_exact_runtime_translation_surface():
    result = verify_translation_surface(US500_PROFILE_BLOCKS)
    assert result["profile_count"] == 3
    assert result["extractor_runtime_signal_surfaces_equal"] is True
    assert result["unknown_action_parameters_rejected"] is True


def test_recorded_real_scaffold_smoke_binds_current_frozen_inputs():
    evidence = json.loads(
        (ROOT / "evidence/us500_v4_real_scaffold_smoke.json").read_text())
    assert evidence["decision"] == "PASS_REAL_SCAFFOLD_STRUCTURAL_SMOKE"
    assert evidence["performance_accessed"] is False
    assert evidence["sqcli_started"] is False
    assert evidence["verified_branch_count"] == 9
    assert evidence["registry_sha256"] == _sha(ROOT / "ostium_markets.json")
    assert evidence["methodology_sha256"] == _sha(ROOT / "methodology_v4.json")
    assert evidence["source_sha256"] == _sha(
        ROOT / "evidence/us500_d1_canonical_v4.csv")
    assert evidence["worker_config_sha256"] == _sha(
        ROOT / "us500_v4_sq_worker_config.json")
    assert {(row["profile"], row["market_side"]) for row in evidence["branches"]} == {
        (profile, side) for profile in US500_PROFILE_BLOCKS
        for side in ("both", "long", "short")}
    assert all(row["nominal_evaluations"] == 10_000
               for row in evidence["branches"])
