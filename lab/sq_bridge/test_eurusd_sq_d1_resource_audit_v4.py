from datetime import date, timedelta

from lab.sq_bridge.eurusd_sq_d1_resource_audit_v4 import evaluate


def fixtures(*, sunday=False, incomplete=False):
    sq, source = {}, {}
    cursor = date(2000, 1, 3)
    for index in range(5000):
        while cursor.weekday() >= 5:
            cursor += timedelta(days=1)
        day = cursor.isoformat()
        sq[day] = [1, 2, .5, 1.5]
        source[day] = {"minutes": 1000 if incomplete and index == 0 else 1440,
                       "ohlc": [1, 2, .5, 1.5]}
        cursor += timedelta(days=1)
    if sunday:
        sq["2023-01-01"] = [1, 2, .5, 1.5]
        source["2023-01-01"] = {"minutes": 400, "ohlc": [1, 2, .5, 1.5]}
    return sq, source


def test_clean_resource_passes():
    sq, source = fixtures()
    result = evaluate(sq, source)
    assert result["decision"] == "PASS_SQ_D1_RESOURCE"


def test_sunday_fragment_and_incomplete_bar_block():
    sq, source = fixtures(sunday=True, incomplete=True)
    result = evaluate(sq, source)
    assert result["decision"] == "BLOCK_SQ_D1_RESOURCE_SESSION"
    assert result["checks"]["no_sunday_fragments"] is False
    assert result["checks"]["complete_daily_bars"] is False
