import json
from pathlib import Path

from lab.sq_bridge.crypto_intraday_compression_v18 import leverage_plan, parameter_grid, trade_diagnostics


FAMILY = Path(__file__).with_name("family_crypto_intraday_compression_v18.json")


def test_v18_grid_size_and_sealed_periods():
    config = json.loads(FAMILY.read_text())
    grid = config["grid"]
    points = 1
    for key, values in grid.items():
        if key != "points":
            points *= len(values)
    assert points == grid["points"] == 2304
    assert config["periods"]["validation_from"] == "2025-01-01"
    assert config["periods"]["holdout_from"] == "2025-07-01"
    assert config["holdout_release_authorized"] is False


def test_v18_small_account_rule_caps_liquidation_before_venue_max():
    config = json.loads(FAMILY.read_text())
    account = config["small_account"]
    stop_distance = 0.02
    safe_leverage = int(1 / (stop_distance * account["liquidation_buffer_over_stop"]))
    assert safe_leverage == 40
    assert safe_leverage < account["venue_max_leverage"]["SOLUSD"]
    assert config["cost_model"]["oracle_fee_usdc_per_trade"] == 0.10


def test_v18_parameter_generator_matches_preregistered_points():
    config = json.loads(FAMILY.read_text())
    assert len(list(parameter_grid(config))) == 2304


def test_v18_leverage_uses_highest_stop_safe_integer_and_margin_is_small():
    account = json.loads(FAMILY.read_text())["small_account"]
    plan = leverage_plan(0.02, "SOLUSD", account)
    assert plan["leverage"] == 40
    assert plan["liquidation_distance"] == 0.025
    assert plan["exposure"] == 0.5
    assert plan["margin_fraction"] == 0.0125


def test_v18_leverage_respects_venue_cap_for_tight_stop():
    account = json.loads(FAMILY.read_text())["small_account"]
    assert leverage_plan(0.001, "SOLUSD", account)["leverage"] == 150


def test_v18_trade_diagnostics_reports_holding_and_collateral():
    rows = [{"entry": "2024-01-01T01:00:00+00:00", "exit": "2024-01-01T06:00:00+00:00",
             "reason": "time", "leverage": 40, "exposure_to_capital": .5,
             "margin_fraction": .0125, "liquidation": False}]
    result = trade_diagnostics(rows)
    assert result["median_duration_hours"] == 5
    assert result["median_margin_pct"] == 1.25
    assert result["liquidations"] == 0
