import json
from datetime import datetime, timedelta, timezone

import pytest

from lab.sq_bridge.crypto_proxy_mapping_v4 import evaluate, make_observation


def _write(path, value):
    path.write_text(json.dumps(value))
    return path


def test_observation_requires_bracket_and_computes_basis(tmp_path):
    before = _write(tmp_path / "before.json", {
        "captured_at": "2026-01-01T00:00:00+00:00",
        "source": {"symbol": "BTCUSDT"}, "quote": {"mid": 100}})
    ostium = _write(tmp_path / "ostium.json", {
        "captured_at": "2026-01-01T00:00:10+00:00",
        "instrument": {"pair_from": "BTC", "pair_to": "USD"},
        "quote": {"mid": 100.01}})
    after = _write(tmp_path / "after.json", {
        "captured_at": "2026-01-01T00:00:20+00:00",
        "source": {"symbol": "BTCUSDT"}, "quote": {"mid": 100}})
    result = make_observation(before, ostium, after, tmp_path / "observation.json")
    assert result["basis_bps"] == pytest.approx(1)
    assert result["bracket_seconds"] == 20
    assert result["binance_interpolation_weight"] == .5
    assert result["research_authorized"] is False


def _gate_inputs(tmp_path, count=241):
    canonical = _write(tmp_path / "canonical.json", {
        "decision": "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED",
        "research_symbol": "BTCUSD", "source_symbol": "BTCUSDT"})
    native = _write(tmp_path / "native.json", {"decision": "READY_FOR_PARITY"})
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    paths = []
    for index in range(count):
        day, slot = divmod(index, 4)
        stamp = first + timedelta(days=day, hours=(slot * 6 + day) % 24)
        price = 100 + index * .1
        path = tmp_path / f"observation-{index:03}.json"
        paths.append(_write(path, {
            "captured_at": stamp.isoformat(), "ostium_symbol": "BTCUSD",
            "binance_symbol": "BTCUSDT", "ostium_mid": price * 1.0001,
            "binance_bracket_mid": price, "basis_bps": 1,
            "bracket_seconds": 20, "performance_accessed": False}))
    return paths, native, canonical


def test_gate_passes_only_after_diverse_sixty_day_mapping(tmp_path):
    paths, native, canonical = _gate_inputs(tmp_path)
    result = evaluate(paths, native, canonical)
    assert result["decision"] == "PASS_CRYPTO_PROXY_MAPPING"
    assert result["research_authorized"] is True
    assert result["synchronized_return_correlation"] == pytest.approx(1)


def test_gate_explains_immature_mapping(tmp_path):
    paths, native, canonical = _gate_inputs(tmp_path, count=1)
    result = evaluate(paths, native, canonical)
    assert result["decision"] == "WARMING"
    assert result["research_authorized"] is False
    assert "PAIRED_OBSERVATIONS_LT_240" in result["blocking_reasons"]
    assert "SYNCHRONIZED_RETURN_CORRELATION_LT_0_999" in result["blocking_reasons"]
