import json

from lab.sq_bridge.market_universe_gate import build


def report(tmp_path, **changes):
    value = {
        "symbol": "XAUUSD", "source_a": "ostium_realtime", "source_b": "dukascopy",
        "aligned_count": 6000, "overlap": {"overlap_minutes": 9000},
        "returns_market_open": {"corr": .97, "dir_agree_filtered_pct": 96.5},
        "verdict": "PASS_BACKTEST",
    }
    value.update(changes)
    path = tmp_path / "compat.json"
    path.write_text(json.dumps(value))
    return path


def test_xau_research_pass_does_not_authorize_live_and_btc_blocks(tmp_path):
    result = build(report(tmp_path), [tmp_path / "missing-btc"])
    assert result["selected_for_discovery"] == ["XAUUSD"]
    assert result["paper_or_live_authorized"] is False
    assert result["markets"][0]["live_eligible"] is False
    assert result["markets"][1]["decision"] == "BLOCK"


def test_xau_blocks_when_recent_parity_is_weak(tmp_path):
    result = build(report(tmp_path, returns_market_open={"corr": .80, "dir_agree_filtered_pct": 99}), [])
    assert result["selected_for_discovery"] == []
    assert "RETURN_CORRELATION_BELOW_0_95" in result["markets"][0]["reasons"]


def test_btc_requires_an_existing_native_path(tmp_path):
    native = tmp_path / "btc-native"
    native.mkdir()
    result = build(report(tmp_path), [native])
    assert result["markets"][1]["decision"] == "WARMING"


def test_btc_requires_maturity_and_explicit_proxy_parity(tmp_path):
    native = tmp_path / "btc-native"; native.mkdir()
    coverage = tmp_path / "coverage.json"; coverage.write_text(json.dumps({"decision": "READY_FOR_PARITY"}))
    parity = tmp_path / "parity.json"; parity.write_text(json.dumps({"decision": "PASS_RESEARCH_OHLC"}))
    result = build(report(tmp_path), [native], coverage, parity)
    assert result["markets"][1]["decision"] == "PASS_RESEARCH"
