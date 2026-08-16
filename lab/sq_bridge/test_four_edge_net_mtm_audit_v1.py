from pathlib import Path

import pytest

from lab.sq_bridge.four_edge_net_mtm_audit_v1 import audit


ROOT = Path(__file__).resolve().parents[2]
SQX = ROOT / "data/ibkr_sq_v2/four_edge_portfolio_composer_v1/Portfolio-1786795330285.sqx"
FX = ROOT / "data/ibkr_sq_v2/four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv"


def test_frozen_four_edge_net_mtm_gate_passes_without_promoting_gold_standalone():
    result = audit(SQX, FX)
    assert result["decision"] == "PASS_ADMIT_SGLN_AS_CAPPED_PORTFOLIO_COMPONENT"
    assert result["sgln_maximum_weight_pct"] == 25
    assert result["sgln_whole_shares"] == 13
    assert result["scenarios"]["stress"]["net_return_pct"] == pytest.approx(20.112051)
    assert result["scenarios"]["stress"]["daily_mtm_max_drawdown_pct"] == pytest.approx(8.151593)
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False


def test_frozen_hash_rejects_a_different_input(tmp_path):
    changed = tmp_path / "changed.csv"
    changed.write_bytes(FX.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="frozen input hash mismatch"):
        audit(SQX, changed)
