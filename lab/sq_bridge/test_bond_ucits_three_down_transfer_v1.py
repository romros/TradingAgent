import json
from pathlib import Path

from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "lab/sq_bridge/bond_ucits_three_down_transfer_v1.json"


def test_bond_transfer_decision_replays():
    receipt = ROOT / "data/ibkr_sq_v2/bond_ucits_three_down_transfer_v1/development.json"
    expected = json.loads(receipt.read_text())
    result = evaluate(SPEC)
    assert result["decision"] == expected["decision"]
    assert result["evaluated_variants"] == 1
    assert result["oos_accessed"] is False
