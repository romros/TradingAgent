import json
from pathlib import Path

from lab.sq_bridge.ibkr_sq_discovery_v1 import compile_batch
from lab.sq_bridge.sq_project_contract import verify_genetic_project


def test_compiles_intraday_ibkr_projects_without_starting_sq(tmp_path):
    result = compile_batch(tmp_path)
    assert result["decision"] == "PASS_CFX_BATCH_READY"
    assert result["sqcli_started"] is False
    assert len(result["projects"]) == 3
    for row in result["projects"].values():
        manifest = json.loads(Path(row["project_manifest_path"]).read_text())
        assert manifest["timeframe"] == "M15"
        assert manifest["periods"]["train_to"] == "2019-01-10"
        assert manifest["intraday_execution"] == {
            "exit_at_end_of_day": True,
            "eod_exit_seconds": 75540,
            "signal_time_range_seconds": [48600, 74700],
            "exit_at_end_of_range": True,
            "maximum_trades_per_day": 1,
        }
        assert verify_genetic_project(Path(row["project_cfx_path"]), manifest) == row["sq_genetic_shape"]
