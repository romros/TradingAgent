from lab.sq_bridge.ostium_native_coverage_gate import inventory


def write(root, rows):
    path = root / "2026" / "08.csv"; path.parent.mkdir(parents=True)
    path.write_text("".join(f"{ts},{price},{price+1},{price-1},{price},0\n" for ts, price in rows))


def test_fresh_short_recorder_is_warming_not_research_ready(tmp_path):
    write(tmp_path, [(1_800_000_000, 100), (1_800_000_060, 101)])
    result = inventory(tmp_path, 1_800_000_120)
    assert result["decision"] == "WARMING"
    assert result["research_authorized"] is False
    assert "SPAN_LT_60_DAYS" in result["reasons"]


def test_complete_mature_recorder_becomes_ready_for_parity(tmp_path):
    start = 1_800_000_000
    rows = [(start + minute * 60, 100 + minute / 1_000_000) for minute in range(60 * 24 * 61)]
    write(tmp_path, rows)
    result = inventory(tmp_path, rows[-1][0] + 60)
    assert result["decision"] == "READY_FOR_PARITY"
    assert result["paper_or_live_authorized"] is False


def test_stale_or_invalid_recorder_blocks(tmp_path):
    write(tmp_path, [(1_800_000_000, 100)])
    path = tmp_path / "2026" / "08.csv"
    with path.open("a") as handle: handle.write("1800000061,100,99,101,100,0\n")
    result = inventory(tmp_path, 1_800_001_000, minimum_days=0)
    assert result["decision"] == "BLOCK"
    assert "INVALID_CANDLES_PRESENT" in result["reasons"]
    assert "RECORDER_STALE" in result["reasons"]
