import json

import pytest

from lab.sq_bridge.xle_monthly_tsmom_oos_v1 import evaluate
from lab.sq_bridge.xle_monthly_tsmom_screen_v1 import SPEC, sha


def test_rejects_oos_without_validation_release(tmp_path):
    source = tmp_path / "XLE_2024.csv"
    source.write_text("date,open,high,low,close,volume,minutes\n")
    prior = tmp_path / "validation.json"
    prior.write_text(json.dumps({"decision": "REJECT_VALIDATION",
                                 "preregistration_sha256": sha(SPEC),
                                 "source_sha256": sha(source),
                                 "oos_2024_performance_accessed": False}))
    with pytest.raises(ValueError, match="OOS_RELEASE_NOT_AUTHORIZED"):
        evaluate(source, prior, tmp_path / "out.json")
