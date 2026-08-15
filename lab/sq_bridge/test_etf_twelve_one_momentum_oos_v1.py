import json

import pytest

from lab.sq_bridge.etf_twelve_one_momentum_oos_v1 import evaluate


def test_oos_refuses_failed_validation(tmp_path):
    report = tmp_path / "validation.json"
    report.write_text(json.dumps({"decision": "REJECT_VALIDATION"}))
    with pytest.raises(ValueError, match="VALIDATION_GATE_NOT_PASSED"):
        evaluate({}, report, tmp_path / "oos.json")
