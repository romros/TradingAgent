import json
from pathlib import Path

from lab.sq_bridge import earnings_gap_continuation_screen_v1 as v1


def test_metrics_are_chronological_and_compounded():
    rows = [
        {"asset": "A", "exit": "2020-01-03", "net_return": -0.10},
        {"asset": "A", "exit": "2020-01-02", "net_return": 0.20},
    ]
    result = v1.metrics(rows)
    assert result["trades"] == 2
    assert abs(result["compounded_net_return"] - 0.08) < 1e-12
    assert abs(result["maximum_drawdown"] - 0.10) < 1e-12


def test_expanded_screen_is_frozen_reproducible_and_rejected():
    here = Path(v1.__file__).resolve().parent
    original = (v1.SPEC, v1.LOCK, v1.PREFLIGHT)
    try:
        v1.SPEC = here / "earnings_gap_continuation_preregistration_v2.json"
        v1.LOCK = here / "earnings_gap_continuation_preregistration_v2.lock.json"
        v1.PREFLIGHT = v1.ROOT / "data/ibkr_sq_v2/earnings_gap_continuation_v1/sec_calendar_preflight_v2.json"
        result = v1.screen()
    finally:
        v1.SPEC, v1.LOCK, v1.PREFLIGHT = original
    persisted = json.loads((v1.ROOT / "data/ibkr_sq_v2/earnings_gap_continuation_v1/screen_v2_expanded.json").read_text())
    assert result["decision"] == "REJECT_EXPLORATORY_EDGE_GATE"
    assert result["signals_executed"] == 34
    assert result["combined_validation_oos"] == persisted["combined_validation_oos"]
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
