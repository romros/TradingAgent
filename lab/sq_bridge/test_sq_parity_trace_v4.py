import json

import pytest

from lab.sq_bridge.parity_artifact_v4 import compare_traces
from lab.sq_bridge.sq_parity_trace_v4 import build


def _sources(tmp_path):
    market = tmp_path / "market.csv"
    market.write_text("\n".join([
        "2024.01.01,00:00,100,101,99,100,1",
        "2024.01.02,00:00,102,103,101,102,1",
        "2024.01.03,00:00,104,105,103,104,1",
    ]) + "\n")
    signals = tmp_path / "signals.csv"
    signals.write_text("Timestamp;Direction\n2024.01.01 00:00:00;Buy\n")
    orders = tmp_path / "orders.csv"
    orders.write_text(
        "Type;Open time;Open price;Close time;Close price;Profit/Loss;Close type\n"
        "Buy;2024.01.01 00:00:00;100;2024.01.03 00:00:00;104;999;ExitAfterBars\n")
    return orders, signals, market


def test_builds_observed_sq_trace_and_recomputes_pnl_from_prices(tmp_path):
    orders, signals, market = _sources(tmp_path)
    trace = build(
        candidate_id="candidate", orders_path=orders, signals_path=signals,
        market_data_path=market, source_timezone="UTC", notional_usdc=200,
        output_path=tmp_path / "sq.json")
    assert trace["trades"][0]["pnl"] == pytest.approx(8)
    assert trace["trades"][0]["pnl"] != 999
    assert trace["orders_sha256"] and trace["signals_sha256"]
    clone = json.loads(json.dumps(trace))
    clone["source"] = "python"
    metrics = compare_traces(trace, clone)
    assert metrics["trade_match_rate"] == 1
    assert metrics["signal_match_rate"] == 1


def test_fails_closed_without_independent_signal_rows(tmp_path):
    orders, signals, market = _sources(tmp_path)
    signals.write_text("Timestamp;Direction\n")
    with pytest.raises(ValueError, match="CSV sense files"):
        build(candidate_id="candidate", orders_path=orders, signals_path=signals,
              market_data_path=market, source_timezone="UTC", notional_usdc=200,
              output_path=tmp_path / "sq.json")


def test_fails_closed_when_sq_time_does_not_match_common_candle(tmp_path):
    orders, signals, market = _sources(tmp_path)
    signals.write_text("Timestamp;Direction\n2024.01.01 00:00:01;Buy\n")
    with pytest.raises(ValueError, match="fora de les candles comunes"):
        build(candidate_id="candidate", orders_path=orders, signals_path=signals,
              market_data_path=market, source_timezone="UTC", notional_usdc=200,
              output_path=tmp_path / "sq.json")


def test_requires_explicit_valid_timezone(tmp_path):
    orders, signals, market = _sources(tmp_path)
    with pytest.raises(ValueError, match="Timestamp SQ invalid"):
        build(candidate_id="candidate", orders_path=orders, signals_path=signals,
              market_data_path=market, source_timezone="Not/AZone", notional_usdc=200,
              output_path=tmp_path / "sq.json")
