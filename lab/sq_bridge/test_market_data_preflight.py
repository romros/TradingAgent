import json
from pathlib import Path

from lab.sq_bridge.market_data_preflight import evaluate_market


def _write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def test_newest_registry_wins_and_conflict_fails_closed(tmp_path):
    bs = tmp_path / "bs"
    _write(bs / "datafiles/historical_parquet/_coverage/XAUUSD_tf1m.json",
           {"last_updated": "now", "months": {"2020-01": {"status": "done", "rows": 10}}})
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    _write(old, {"XAUUSD": {"asof_ts": 1, "status": "PASS", "allowed_for_backtest": True}})
    _write(new, {"XAUUSD": {"asof_ts": 2, "status": "PARTIAL", "allowed_for_backtest": False}})
    result = evaluate_market("XAUUSD", bs, [new, old])
    assert result["decision"] == "BLOCK_CURRENT_PARITY"
    assert result["current_compatibility"]["asof_ts"] == 2
    assert result["registry_conflict"] is True


def test_missing_historical_source_blocks_even_with_ostium_data(tmp_path):
    bs = tmp_path / "bs"
    parquet = bs / "datafiles/historical_parquet_ostium_v1/MSFT/tf=1m/year=2026/month=03/data.parquet"
    parquet.parent.mkdir(parents=True); parquet.write_bytes(b"fixture")
    registry = tmp_path / "registry.json"
    _write(registry, {"MSFT": {"asof_ts": 3, "status": "PASS", "allowed_for_backtest": True}})
    result = evaluate_market("MSFT", bs, [registry])
    assert result["decision"] == "BLOCK_HISTORICAL_SOURCE"
    assert result["ostium_native_storage"]["available"] is True


def test_complete_source_and_current_pass_only_authorize_research(tmp_path):
    bs = tmp_path / "bs"
    _write(bs / "datafiles/historical_parquet/_coverage/EURUSD_tf1m.json",
           {"last_updated": "now", "months": {"2020-01": {"status": "done", "rows": 10}}})
    registry = tmp_path / "registry.json"
    _write(registry, {"EURUSD": {"asof_ts": 3, "status": "PASS_BACKTEST", "allowed_for_backtest": True}})
    result = evaluate_market("EURUSD", bs, [registry])
    assert result["decision"] == "PASS_RESEARCH_PROXY_ONLY"
    assert result["paper_or_live_authorized"] is False
