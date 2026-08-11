import pytest

from lab.sq_bridge.candle_source_contract_v4 import build, verify


def _csv(path, close="1.1"):
    path.write_text(
        "Date,Time,Open,High,Low,Close,Volume\n"
        f"2020.01.01,00:00,1,1.2,0.9,{close},1\n"
        "2020.01.01,00:15,1.1,1.3,1,1.2,1\n")


def test_proves_reproducible_sq_dukascopy_candle_parity(tmp_path):
    sq, duka = tmp_path / "sq.csv", tmp_path / "duka.csv"
    _csv(sq); _csv(duka)
    contract = build(
        sq_candles_path=sq, sq_timezone="UTC",
        dukascopy_candles_path=duka, dukascopy_timezone="UTC",
        symbol="EURUSD", timeframe="M15")
    assert contract["decision"] == "PASS_CANDLE_PARITY"
    assert contract["sq_coverage_pct"] == 100
    assert contract["ohlc_match_pct"] == 100
    assert verify(contract) == contract


def test_blocks_price_mismatch_and_detects_later_source_mutation(tmp_path):
    sq, duka = tmp_path / "sq.csv", tmp_path / "duka.csv"
    _csv(sq); _csv(duka, close="1.15")
    contract = build(
        sq_candles_path=sq, sq_timezone="UTC",
        dukascopy_candles_path=duka, dukascopy_timezone="UTC",
        symbol="EURUSD", timeframe="M15")
    assert contract["decision"] == "BLOCK_CANDLE_PARITY"
    duka.write_text(duka.read_text().replace("1.15", "1.1"))
    with pytest.raises(ValueError, match="manipulada"):
        verify(contract)
