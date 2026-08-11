import json

import lab.sq_bridge.crypto_h4_sq_candidate_normalize_v4 as module
from lab.sq_bridge.crypto_h4_sq_candidate_normalize_v4 import _nearest


def test_nearest_grid_is_decimal_deterministic_and_ties_choose_lower():
    assert _nearest(2.3, 1, 4, .25) == 2.25
    assert _nearest(2.375, 1, 4, .25) == 2.25
    assert _nearest(2.376, 1, 4, .25) == 2.5


def test_normalizes_compression_sq_node_onto_preregistered_grid(tmp_path, monkeypatch):
    sqx = tmp_path / "candidate.sqx"; sqx.write_bytes(b"sqx")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"market": "BTCUSD", "parameter_search_space": {
        "indicator_period": {"minimum": 12, "maximum": 120},
        "shift": {"minimum": 1, "maximum": 2},
        "exit_after_bars": {"minimum": 3, "maximum": 30},
        "atr_stop_multiple": {"minimum": 1, "maximum": 4},
        "compression_lookback": {"minimum": 12, "maximum": 72},
        "compression_percentile": {"minimum": 10, "maximum": 40}}}))
    prereg = tmp_path / "prereg.json"
    prereg.write_text(json.dumps({"profile_parameter_ranges": {
        "crypto_h4_volatility_compression_breakout_v4": {
            "indicator_period_min": 12, "indicator_period_max": 120,
            "shift_min": 1, "shift_max": 2,
            "exit_after_bars_min": 3, "exit_after_bars_max": 30,
            "exit_after_bars_step": 1,
            "atr_stop_multiple_min": 1, "atr_stop_multiple_max": 4,
            "atr_stop_multiple_step": .25,
            "compression_lookback_min": 12, "compression_lookback_max": 72,
            "compression_percentile_min": 10,
            "compression_percentile_max": 40,
            "compression_percentile_step": 5}}}))
    monkeypatch.setattr(module, "extract", lambda _path: {
        "translation_status": "SUPPORTED_SUBSET", "strategy_name": "C",
        "entries": {"short": None, "long": {"signal": {
            "op": "AlquimiaH4CompressionChannelAbove", "params": {
                "#Period#": 49, "#Shift#": 1, "#CompressionLookback#": 23.6,
                "#CompressionPercentile#": 27.6}}, "action": {"params": {
                    "#ExitAfterBars.ExitAfterBars#": 10,
                    "#StopLoss.StopLoss#": {"params": {"#Value#": 2.3}}}}}}})
    result = module.normalize(sqx=sqx, manifest_path=manifest,
                              preregistration_path=prereg)
    assert result["mechanism"] == "volatility_compression_breakout"
    assert result["normalized_parameters"]["compression_lookback"] == 24
    assert result["normalized_parameters"]["compression_percentile"] == 30
    assert result["normalized_parameters"]["atr_stop_multiple"] == 2.25
