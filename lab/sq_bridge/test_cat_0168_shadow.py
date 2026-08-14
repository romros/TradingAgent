import json
from pathlib import Path

from packages.execution.shadow import (ShadowIntent, append_once,
    hypothetical_open_intent, hypothetical_position, sync_csv)
from packages.strategy.cat_adx_d1 import bracket_exit, entry_for_index


def test_bracket_is_pessimistic_when_both_touch():
    assert bracket_exit({"open": 100, "high": 120, "low": 80}, 90, 110) == ("SL", 90)


def test_gap_uses_actual_open():
    assert bracket_exit({"open": 85, "high": 100, "low": 80}, 90, 110) == ("SL_GAP", 85)


def test_shadow_metadata_and_position_are_idempotent(tmp_path: Path):
    ledger = tmp_path / "ledger.json"
    buy = ShadowIntent("k", "cat_0168", "CAT", "BUY", "2026-01-02", 100, 2, 200, 1,
                       metadata={"stop": 90, "target": 110})
    assert append_once(ledger, buy) is True
    assert append_once(ledger, buy) is False
    value = json.loads(ledger.read_text())
    assert hypothetical_position(value, "CAT") == 2
    assert hypothetical_open_intent(value, "CAT")["metadata"]["stop"] == 90
    csv_text = sync_csv(ledger).read_text()
    assert "metadata_json" in csv_text
    assert '""stop"":90' in csv_text


def test_entry_never_uses_current_bar_for_signal_or_atr():
    rows = [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
            for _ in range(50)]
    before = entry_for_index(rows, 49)
    rows[49] = {"open": 100.0, "high": 1000.0, "low": 1.0, "close": 900.0}
    after = entry_for_index(rows, 49)
    assert before == after
