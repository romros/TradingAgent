import csv
import json
import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.xauusd_cftc_flow_preflight_v32 import audit

CONFIG = json.loads(Path(__file__).with_name("family_xauusd_cftc_flow_preflight_v32.json").read_text())


def archive(tmp_path, *, code="088691", date_field="Report_Date_as_YYYY-MM-DD"):
    path = tmp_path / "sample.zip"
    fields = ["Market_and_Exchange_Names", date_field, "CFTC_Contract_Market_Code",
              "CFTC_Commodity_Code", *CONFIG["required_position_fields"]]
    text_path = tmp_path / "f_year.txt"
    with text_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
                         date_field: "2018-12-31", "CFTC_Contract_Market_Code": code,
                         "CFTC_Commodity_Code": "088",
                         **{field: "10" for field in CONFIG["required_position_fields"]}})
    with zipfile.ZipFile(path, "w") as zipped:
        zipped.write(text_path, "f_year.txt")
    return path


def synthetic_config(path):
    config = json.loads(json.dumps(CONFIG))
    import hashlib
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    config["sample_archives"] = [{"year": 2018, "path": str(path), "url": "official",
                                   "sha256": digest, "minimum_gold_rows": 1}] * 3
    return config


def test_valid_data_still_blocks_without_release_ledger(tmp_path):
    result = audit(synthetic_config(archive(tmp_path)))
    assert result["data_gate"]["status"] == "PASS"
    assert result["decision"] == "BLOCK_RELEASE_LEDGER"
    assert result["strategy_rule_defined"] is False
    assert result["xau_performance_accessed"] is False


def test_wrong_gold_identity_blocks_data(tmp_path):
    result = audit(synthetic_config(archive(tmp_path, code="OTHER")))
    assert result["decision"] == "BLOCK_DATA"


def test_preflight_rejects_strategy_or_future_access(tmp_path):
    config = synthetic_config(archive(tmp_path))
    config["strategy_rule_defined"] = True
    with pytest.raises(ValueError, match="no strategy"):
        audit(config)
