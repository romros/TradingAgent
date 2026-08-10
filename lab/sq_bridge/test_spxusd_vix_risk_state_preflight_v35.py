import csv
import hashlib
from pathlib import Path

from lab.sq_bridge.spxusd_vix_risk_state_preflight_v35 import audit


def _config(path: Path):
    return {"campaign_id": "test", "source": {"path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "expected_columns": ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]},
            "timing_policy": {"same_session_use_allowed": False, "rule": "prior",
                              "observation": "close", "earliest_use": "next", "intraday_reconstruction_allowed": False},
            "gate": {"minimum_first_date": "2020-01-02", "minimum_last_date": "2020-01-02",
                     "minimum_rows": 1, "require_unique_dates": True,
                     "require_weekdays": True, "require_valid_close": True,
                     "quarantine_inconsistent_non_close_ohlc": True},
            "strategy_rule_defined": False, "spx_performance_accessed": False,
            "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False,
            "sqcli_authorized": False, "paper_authorized": False, "live_authorized": False}


def test_valid_source_passes(tmp_path: Path):
    path = tmp_path / "vix.csv"
    path.write_text("DATE,OPEN,HIGH,LOW,CLOSE\n01/02/2020,14,16,13,15\n")
    assert audit(_config(path))["decision"] == "PASS_VIX_DATA_TIMING"


def test_same_session_policy_fails(tmp_path: Path):
    path = tmp_path / "vix.csv"
    path.write_text("DATE,OPEN,HIGH,LOW,CLOSE\n01/02/2020,14,16,13,15\n")
    config = _config(path)
    config["timing_policy"]["same_session_use_allowed"] = True
    assert audit(config)["decision"] == "BLOCK_VIX_DATA"
