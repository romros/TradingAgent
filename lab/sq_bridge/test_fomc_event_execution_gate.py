from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from lab.sq_bridge.fomc_event_execution_gate import evaluate, phase_for

NY = ZoneInfo("America/New_York")


def snapshot(local_time: str, *, opened=True, pair_id="5"):
    stamp = datetime.fromisoformat(f"2026-09-16T{local_time}:00").replace(tzinfo=NY)
    points = [{"notional_usd": value, "slippage_bps": value / 200}
              for value in (200, 400, 500, 600)]
    return {
        "captured_at": stamp.isoformat(),
        "source": {"raw_sha256": local_time.replace(":", "")},
        "instrument": {"pair_id": pair_id, "pair_from": "XAU", "pair_to": "USD"},
        "market_state": {"is_market_open": opened},
        "fees": {"open_fee_bps": 2, "close_fee_bps": 0},
        "quote": {"spread_bps": 1},
        "simulated_slippage": {"long": points, "short": points},
    }


def test_phase_boundaries_are_explicit():
    assert phase_for(datetime(2026, 9, 16, 13, 45, tzinfo=NY)) == "pre"
    assert phase_for(datetime(2026, 9, 16, 14, 0, tzinfo=NY)) == "reaction"
    assert phase_for(datetime(2026, 9, 16, 14, 30, 59, tzinfo=NY)) == "reaction"
    assert phase_for(datetime(2026, 9, 16, 14, 31, tzinfo=NY)) == "post"
    assert phase_for(datetime(2026, 9, 16, 16, 46, tzinfo=NY)) is None


def test_rejects_wrong_pair_date_and_duplicate_minute():
    with pytest.raises(ValueError, match="expected"):
        evaluate([snapshot("14:00", pair_id="10")], event_date=date(2026, 9, 16))
    with pytest.raises(ValueError, match="does not match"):
        evaluate([snapshot("14:00")], event_date=date(2026, 9, 17))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate([snapshot("14:00"), snapshot("14:00")], event_date=date(2026, 9, 16))


def test_gate_is_fail_closed_and_cost_formula_is_a_proxy():
    rows = ([snapshot(f"13:{minute:02d}") for minute in range(45, 55)]
            + [snapshot(f"14:{minute:02d}") for minute in range(20)]
            + [snapshot(f"15:{minute:02d}") for minute in range(60)])
    result = evaluate(rows, event_date=date(2026, 9, 16))
    assert result["gate"]["status"] == "EVENT_EXECUTION_EVIDENCE_READY"
    assert result["phases"]["pre"]["estimated_cost_by_notional"]["200"][
        "direction_neutral_roundtrip_proxy_bps"]["p50"] == 5
    assert result["cost_model"]["limitation"].endswith("not observed fills.")
    assert result["live_authorized"] is False
    rows.pop()
    result = evaluate(rows, event_date=date(2026, 9, 16))
    assert result["gate"]["status"] == "INSUFFICIENT_EVENT_EXECUTION_EVIDENCE"


def test_closed_samples_do_not_count():
    result = evaluate([snapshot("13:45", opened=False)], event_date=date(2026, 9, 16))
    assert result["closed_market_snapshots_in_window"] == 1
    assert result["gate"]["checks"]["pre"]["actual_open_distinct_minutes"] == 0
