import json
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_cfx_v4 import compile_cfx, verify_cfx


SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_REPRO_SMOKE/project.cfx")


def _plan(tmp_path, mechanism="channel_breakout"):
    plan = {"decision": "PASS_SQ_PLAN_READY", "mechanism": mechanism,
        "market": "BTCUSD", "symbol": "BTCUSD_ALQ_H4", "instrument": "BTC_ALQ",
        "project_name": "ALQ4_BTCUSD_TEST", "direction": "long",
        "attempt_budget": 10000, "attempt_stop_guard": 64,
        "wall_time_budget_minutes": 240, "accepted_limit": 1,
        "sq_genetic_shape": {"islands": 4, "population_per_island": 100,
            "max_generations": 25, "nominal_evaluations": 10000},
        "genetic_parameters": {"crossover_probability_pct": 80,
            "mutation_probability_pct": 20, "migration_every_generations": 5,
            "migration_rate_pct": 10, "initial_population_mode": 2},
        "initial_capital_usdc": 200, "discovery_leverage": 1,
        "money_management": {"method": "CryptoSizeByPrice",
            "use_account_balance": False, "maximum_size": 100, "decimals": 4,
            "fallback_to_size_one_allowed": False},
        "periods": {"train_from": "2018-03-01", "train_to": "2022-04-30"},
        "parameter_search_space": {
            "indicator_period": {"minimum": 49, "maximum": 51},
            "shift": {"minimum": 1, "maximum": 2},
            "exit_after_bars": {"minimum": 9, "maximum": 11},
            "atr_stop_multiple": {"minimum": 1.75, "maximum": 2.25}}}
    if mechanism == "time_series_momentum":
        plan["parameter_search_space"]["roc_threshold_pct"] = {
            "minimum": 2.0, "maximum": 3.0}
    elif mechanism == "volatility_compression_breakout":
        plan["parameter_search_space"]["compression_lookback"] = {
            "minimum": 12, "maximum": 24}
        plan["parameter_search_space"]["compression_percentile"] = {
            "minimum": 10, "maximum": 40}
    path = tmp_path / "plan.json"; path.write_text(json.dumps(plan)); return path


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_compiles_real_sq_scaffold_with_crypto_sizing(tmp_path):
    output = tmp_path / "project.cfx"
    manifest = compile_cfx(_plan(tmp_path), SCAFFOLD, output)
    verification = verify_cfx(output, manifest)
    assert verification["shape"] == (4, 100, 25)
    assert verification["money_management"] == {
        "UseAccountBalance": "false", "MaxSize": "100", "Decimals": "4"}
    assert manifest["sqcli_authorized"] is False
    assert manifest["python_parity_required"] is True
    assert manifest["strategy_promotion_authorized"] is False
    normalized = output.with_name("normalized.cfx")
    normalized.write_bytes(output.read_bytes())
    assert verify_cfx(normalized, manifest, require_archive_hash=False)["valid"] is True


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_compiles_all_source_verified_signal_families(tmp_path):
    output = tmp_path / "momentum.cfx"
    manifest = compile_cfx(_plan(tmp_path, "time_series_momentum"), SCAFFOLD, output)
    verified = verify_cfx(output, manifest)
    assert "AlquimiaH4MomentumAbove" in verified["enabled_blocks"]
    assert "Indicators.Highest" not in verified["enabled_blocks"]
    short_plan = _plan(tmp_path, "time_series_momentum")
    short_value = json.loads(short_plan.read_text())
    short_value["direction"] = "short"
    short_value["project_name"] = "ALQ4_BTCUSD_SHORT_TEST"
    short_plan.write_text(json.dumps(short_value))
    short_output = tmp_path / "momentum-short.cfx"
    short_manifest = compile_cfx(short_plan, SCAFFOLD, short_output)
    assert "AlquimiaH4MomentumBelow" in verify_cfx(
        short_output, short_manifest)["enabled_blocks"]
    compression_output = tmp_path / "compression.cfx"
    compression = compile_cfx(
        _plan(tmp_path, "volatility_compression_breakout"), SCAFFOLD,
        compression_output)
    assert "AlquimiaH4CompressionChannelAbove" in verify_cfx(
        compression_output, compression)["enabled_blocks"]
