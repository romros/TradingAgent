import json
from pathlib import Path

from lab.sq_bridge.us500_v4_sq_worker import tick, validate_us500_scaffold


ROOT = Path(__file__).parents[2]


def test_us500_worker_waits_without_screen_and_creates_no_state(tmp_path):
    output = tmp_path / "out"
    result = tick(
        screen_dir=tmp_path / "absent", config_path=tmp_path / "absent.json",
        output_dir=output)
    assert result["decision"] == "WAITING_FOR_SCREEN"
    assert result["sqcli_started"] is False
    assert not output.exists()


def test_real_scaffold_contains_every_us500_profile_block():
    config = json.loads((
        ROOT / "lab/sq_bridge/us500_v4_sq_worker_config.json").read_text())
    result = validate_us500_scaffold(
        Path(config["scaffold_path"]), config["scaffold_sha256"],
        config["scaffold_sq_version"])
    assert result["required_block_count"] == 14
    assert result["source_role"] == "xml_format_only_no_strategy_or_performance_reuse"


def test_worker_scripts_are_locked_separate_and_us500_scoped():
    runner = (ROOT / "scripts/run_us500_v4_sq_worker.sh").read_text()
    installer = (ROOT / "scripts/install_us500_v4_sq_worker_cron.sh").read_text()
    assert "us500_v4_sq_worker" in runner
    assert "us500-d1-alquimia-v4" in runner
    assert "tradingagent-us500-v4-sq-worker.lock" in installer
    assert 'LINE="*/10 * * * 1-5 flock -n $LOCK ' in installer
    assert "eurusd-v4-sq-worker.lock" not in installer
