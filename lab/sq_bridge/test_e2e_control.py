import json
from pathlib import Path

from lab.sq_bridge.e2e_control import generate


def test_control_proves_complete_wiring_without_promotion(tmp_path):
    result = generate(Path(__file__).with_name("methodology_v3.json"), tmp_path)
    assert result["valid"]
    assert result["operational_control_complete"]
    assert result["control_only"]
    assert not result["promotable"]
    assert not result["paper_ready"]
    assert not result["live_authorized"]
    artifacts = sorted(tmp_path.glob("[0-9][0-9]_*.json"))
    assert len(artifacts) == 8
    assert all(json.loads(path.read_text())["evidence_class"] == "synthetic_control" for path in artifacts)
