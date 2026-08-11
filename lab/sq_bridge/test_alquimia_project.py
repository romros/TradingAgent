#!/usr/bin/env python3
from datetime import date, timedelta
import json
import pytest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import alquimia_project
from alquimia_project import (
    SEARCH_PROFILES, _nominal_genetic_shape, _split_dates, _sq_discovery_slippage,
    _normalize_v4_search_space,
    _validate_generation_contract, _write_reproducible_cfx,
    _validate_v4_prerequisites,
    _validated_v4_periods,
)
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest

generic = SEARCH_PROFILES["generic_translatable"]
assert {"Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.RSI",
        "Indicators.ROC", "EnterAtMarket", "StopLoss.StopLoss"}.issubset(generic)
assert {"Prices.Open", "Indicators.ADX", "Indicators.ATR", "Indicators.talib_BBANDS",
        "Indicators.talib_STDDEV", "Not", "IsLowerOrEqual", "IsGreaterOrEqual",
        "_ExitRule_"}.isdisjoint(generic)

breakout = SEARCH_PROFILES["xau_h4_channel_breakout_v1"]
assert "Indicators.Highest" in breakout and "Indicators.Lowest" in breakout
assert "Indicators.SMA" not in breakout and "Indicators.EMA" not in breakout
stop_breakout = SEARCH_PROFILES["xau_h4_stop_channel_breakout_v2"]
assert "EnterAtStop" in stop_breakout
assert "Stop/Limit Price Levels.Highest" in stop_breakout
assert "EnterAtMarket" not in stop_breakout
compression = SEARCH_PROFILES["xau_h4_atr_compression_breakout_v3"]
assert {"Indicators.ATR", "IsFalling", "EnterAtStop"}.issubset(compression)
assert "Indicators.ADX" not in compression and "Indicators.ROC" not in compression
sweep = SEARCH_PROFILES["xau_h4_sweep_reclaim_v4"]
assert {"Prices.Close", "Prices.High", "Prices.Low", "Indicators.Highest",
        "Indicators.Lowest", "EnterAtMarket"}.issubset(sweep)
assert "EnterAtStop" not in sweep and "Indicators.SMA" not in sweep
eurusd_breakout = SEARCH_PROFILES["eurusd_d1_breakout_v4"]
assert {"Indicators.Highest", "Indicators.Lowest", "EnterAtMarket"}.issubset(
    eurusd_breakout)
assert "BarDayOfWeekIs" in eurusd_breakout
assert "Indicators.ATR" not in eurusd_breakout and "Indicators.ADX" not in eurusd_breakout
assert {"Indicators.ROC", "Indicators.SMA", "Indicators.EMA"}.issubset(
    SEARCH_PROFILES["eurusd_d1_momentum_v4"])
assert {"Indicators.ROC", "Indicators.RSI"}.issubset(
    SEARCH_PROFILES["eurusd_d1_shock_reversion_v4"])

split = _split_dates(date(2017, 1, 26), date(2026, 3, 13),
    {"train_pct": 50, "validation_pct": 20, "oos_pct": 20, "final_holdout_pct": 10})
assert split["train_to"] == "2021-08-19"
assert split["validation_to"] == "2023-06-17"
assert split["oos_to"] == "2025-04-14"
assert split["holdout_to"] == "2026-03-13"
assert split["train_to"] < split["validation_from"] < split["oos_from"] < split["holdout_from"]
print("PASS: sealed chronological split")


def test_v4_requires_genetic_evolution_and_bounded_attempts():
    methodology = json.loads(Path(__file__).with_name("methodology_v4.json").read_text())
    _validate_generation_contract(methodology, "genetic-evolution", 10_000)
    with pytest.raises(ValueError, match="V4_GENERATION_TYPE"):
        _validate_generation_contract(methodology, "random-generation", 10_000)
    with pytest.raises(ValueError, match="V4_ATTEMPT_BUDGET"):
        _validate_generation_contract(methodology, "genetic-evolution", None)
    with pytest.raises(ValueError, match="V4_ATTEMPT_BUDGET"):
        _validate_generation_contract(methodology, "genetic-evolution", 10_001)


def test_genetic_shape_embeds_attempt_ceiling_and_preserves_four_islands():
    shape = _nominal_genetic_shape(10_000)
    assert shape == {"islands": 4, "population_per_island": 100,
                     "max_generations": 25, "nominal_evaluations": 10_000}
    for budget in (1, 17, 999, 9_973, 10_000):
        value = _nominal_genetic_shape(budget)
        assert value["nominal_evaluations"] <= budget
        assert value["nominal_evaluations"] == (
            value["islands"] * value["population_per_island"]
            * value["max_generations"])


def test_v4_search_space_removes_scaffold_quantitative_inheritance():
    methodology = json.loads(Path(__file__).with_name("methodology_v4.json").read_text())
    profile = "eurusd_d1_momentum_v4"
    root = ET.fromstring(
        '<Root><WhatToBuild><RulesComplexity><Chart minPeriod="1" maxPeriod="999" '
        'minShift="0" maxShift="99"/></RulesComplexity></WhatToBuild>'
        '<Blocks><BuildingBlocks/></Blocks></Root>')
    parent = root.find(".//BuildingBlocks")
    for key in SEARCH_PROFILES[profile]:
        attributes = {"key": key, "use": "true", "weight": "9",
                      "category": "exitTypes" if key in {
                          "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss"}
                          else "indicators"}
        if key == "Indicators.ROC":
            attributes.update({"indicatorMin": "-0.25", "indicatorMax": "0.26",
                               "indicatorStep": "0.0102"})
        block = ET.SubElement(parent, "Block", attributes)
        generated = ET.SubElement(block, "Generated")
        if key in {"Indicators.SMA", "Indicators.EMA"}:
            ET.SubElement(generated, "Param", {"key": "#ComputedFrom#",
                          "generation": "random", "values": "Close=0,Open=1"})
        if key == "ExitAfterBars.ExitAfterBars":
            value = ET.SubElement(block, "Value")
            nested = ET.SubElement(value, "Generated")
            ET.SubElement(nested, "Param", {"key": "#ExitAfterBars#",
                          "generation": "random", "minValue": "2",
                          "maxValue": "48", "step": "2"})
        predefined = ET.SubElement(block, "Predefined", {"changed": "true"})
        ET.SubElement(predefined, "Params", {"name": "inherited"})
    result = _normalize_v4_search_space(
        root, profile, methodology["sq_generation"])
    chart = root.find(".//RulesComplexity/Chart")
    assert (chart.get("minPeriod"), chart.get("maxPeriod")) == ("40", "150")
    assert result["computed_from"] == "close_only"
    blocks = {row.get("key"): row for row in root.findall(".//BuildingBlocks/Block")}
    assert all(row.get("weight") == "1" for row in blocks.values())
    assert all(not list(predefined) for row in blocks.values()
               for predefined in row.findall(".//Predefined"))
    assert blocks["Indicators.ROC"].get("indicatorMin") == "-10"
    computed = blocks["Indicators.SMA"].find(".//Param[@key='#ComputedFrom#']")
    assert computed.get("generation") == "fixed" and computed.get("defaultValue") == "0"
    exit_param = blocks["ExitAfterBars.ExitAfterBars"].find(
        ".//Param[@key='#ExitAfterBars#']")
    assert (exit_param.get("minValue"), exit_param.get("maxValue"),
            exit_param.get("step")) == ("10", "30", "1")


def test_cfx_writer_is_byte_reproducible_and_uses_canonical_metadata(tmp_path):
    first, second = tmp_path / "first.cfx", tmp_path / "second.cfx"
    members = {"config.xml": b"<Project/>", "Build-Task1.xml": b"<Settings/>"}
    _write_reproducible_cfx(first, members)
    _write_reproducible_cfx(second, members)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == list(members)
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0)
                   for info in archive.infolist())


def test_v3_keeps_legacy_generation_compatibility():
    methodology = json.loads(Path(__file__).with_name("methodology_v3.json").read_text())
    _validate_generation_contract(methodology, "random-generation", None)


def test_v4_sq_discovery_is_gross_and_cannot_double_charge_slippage():
    assert _sq_discovery_slippage(
        {"discovery_slippage": 400}, {"schema_version": 4}) == 0
    assert _sq_discovery_slippage(
        {"discovery_slippage": 400}, {"schema_version": 3}) == 400


def _ready_chain(tmp_path, selected=("hypothesis",)):
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({"selected_hypothesis_ids": list(selected)}))
    chain = tmp_path / "chain.json"
    chain.write_text(json.dumps({
        "campaign_id": "campaign", "hypothesis_id": "hypothesis", "market": "EURUSD",
        "receipts": [
            {"stage": "market_preflight", "decision": "PASS",
             "receipt_sha256": "a" * 64},
            {"stage": "hypothesis_screen", "decision": "PASS",
             "receipt_sha256": "b" * 64, "artifact": str(screen)},
        ]}))
    return chain


def test_v4_project_requires_verified_chain_at_sq_generation(tmp_path, monkeypatch):
    methodology_path = Path(__file__).with_name("methodology_v4.json")
    methodology = json.loads(methodology_path.read_text())
    with pytest.raises(ValueError, match="PREREQUISITES_REQUIRED"):
        _validate_v4_prerequisites(
            methodology, methodology_path, None, None, None, "EURUSD")
    monkeypatch.setattr(alquimia_project, "verify_chain", lambda *_: {
        "valid": True, "terminal": False, "next_stage": "sq_generation",
        "promotable": True, "errors": []})
    chain = _ready_chain(tmp_path)
    result = _validate_v4_prerequisites(
        methodology, methodology_path, chain, "campaign", "hypothesis", "EURUSD")
    assert result["source_hypothesis_id"] == "hypothesis"
    assert result["evidence_chain_sha256"]


def test_v4_project_rejects_unscreened_hypothesis_or_wrong_identity(tmp_path, monkeypatch):
    methodology_path = Path(__file__).with_name("methodology_v4.json")
    methodology = json.loads(methodology_path.read_text())
    monkeypatch.setattr(alquimia_project, "verify_chain", lambda *_: {
        "valid": True, "terminal": False, "next_stage": "sq_generation",
        "promotable": True, "errors": []})
    chain = _ready_chain(tmp_path, selected=("other",))
    with pytest.raises(ValueError, match="HYPOTHESIS_NOT_SCREENED"):
        _validate_v4_prerequisites(
            methodology, methodology_path, chain, "campaign", "hypothesis", "EURUSD")
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        _validate_v4_prerequisites(
            methodology, methodology_path, chain, "wrong", "hypothesis", "EURUSD")


def test_v4_sq_periods_use_exact_observation_contract_not_calendar_approximation(tmp_path):
    source = tmp_path / "source.csv"
    days = [date(2020, 1, 1) + timedelta(days=index) for index in range(200)]
    source.write_text("\n".join(
        f"{day:%Y.%m.%d},00:00,1,1,1,1,1" for day in days) + "\n")
    methodology = Path(__file__).with_name("methodology_v4.json")
    contract = build_contract(source, methodology)
    contract_path = tmp_path / "periods.json"
    contract_path.write_text(json.dumps(contract))
    periods, evidence = _validated_v4_periods(
        contract_path, digest(contract), methodology,
        days[0], days[-1])
    assert periods["train_to"] == contract["segments"]["train"]["to"]
    assert evidence["temporal_split_contract_sha256"] == digest(contract)
    with pytest.raises(ValueError, match="MISMATCH"):
        _validated_v4_periods(
            contract_path, "0" * 64, methodology,
            days[0], days[-1])
