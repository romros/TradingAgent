from lab.sq_bridge.nflx_04681_m1_execution_audit_v1 import first_touch, verify_lock


def bar(open_, high, low, ts=1):
    return {"open": open_, "high": high, "low": low, "close": open_, "ts": ts, "time": "t"}


def test_gap_open_fills_up_stop_even_with_bad_raw_envelope():
    assert first_touch([bar(316.838, 316.837, 316.0)], 316.838, "up") is not None


def test_gap_open_fills_down_stop_even_with_bad_raw_envelope():
    assert first_touch([bar(99.0, 100.0, 99.1)], 99.0, "down") is not None


def test_start_timestamp_is_respected():
    bars = [bar(101, 102, 100, 1), bar(101, 102, 100, 2)]
    assert first_touch(bars, 101, "up", start_ts=2)["ts"] == 2


def test_preregistration_remains_locked():
    assert verify_lock()["candidate"] == "Strategy 0.4681"
