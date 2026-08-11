import json
from pathlib import Path

import pytest

from lab.sq_bridge.test_eurusd_d1_hypothesis_trace_v4 import _costs
from lab.sq_bridge.test_us500_d1_hypothesis_trace_v4 import _source
from lab.sq_bridge.test_us500_v4_screen_bootstrap import _preflight
from lab.sq_bridge.us500_v4_screen_trigger import trigger


ROOT = Path(__file__).parent


def test_trigger_waits_without_writing_when_cost_preflight_is_blocked(tmp_path):
    preflight = tmp_path / "blocked.json"
    preflight.write_text(json.dumps({
        "campaign_id": "us500-d1-alquimia-v4", "decision": "BLOCK",
        "blocking_reasons": ["EXECUTION_COSTS_NOT_FROZEN"]}) + "\n")
    result = trigger(
        preflight_path=preflight, source_path=preflight,
        methodology_path=ROOT / "methodology_v4.json",
        output_dir=tmp_path / "out")
    assert result["decision"] == "WAITING_FOR_MARKET_PREFLIGHT"
    assert result["sqcli_started"] is False
    assert not (tmp_path / "out").exists()


def test_trigger_freezes_inputs_is_idempotent_and_never_starts_sqcli(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, source, costs)
    output = tmp_path / "trigger"
    first = trigger(
        preflight_path=preflight, source_path=source,
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    second = trigger(
        preflight_path=preflight, source_path=source,
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert first == second
    assert first["decision"] in {"PASS_SCREEN_TRIGGER", "REJECT_SCREEN_TRIGGER"}
    assert first["sqcli_started"] is False
    assert (output / "frozen/canonical_data.csv").read_bytes() == source.read_bytes()
    frozen_receipt = json.loads(
        (output / "frozen/canonical_source.json").read_text())
    assert frozen_receipt["canonical_path"] == str(
        (output / "frozen/canonical_data.csv").resolve())
    assert json.loads((output / "screen_trigger_journal.json").read_text())[
        "phase"] == "COMPLETED"


def test_completed_trigger_detects_bootstrap_tampering(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, source, costs)
    output = tmp_path / "trigger"
    result = trigger(
        preflight_path=preflight, source_path=source,
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    Path(result["bootstrap_path"]).write_text("{}\n")
    with pytest.raises(ValueError, match="bootstrap changed"):
        trigger(
            preflight_path=preflight, source_path=source,
            methodology_path=ROOT / "methodology_v4.json", output_dir=output)
