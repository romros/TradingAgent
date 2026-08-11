#!/usr/bin/env python3
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from lab.sq_bridge.alquimia_retest import (
    PERIOD_KEYS, _condition, _graft_resource_symbol, _require_resource_symbol,
    _select_all_input_strategies, generate,
    verify_retest_project,
)
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY

assert set(PERIOD_KEYS) == {"train", "validation", "oos", "pre_holdout", "holdout"}
node = _condition("ProfitFactor", "Decimal2", ">=", 1.15)
assert node.find("./Left-Side/Column-Value").get("column") == "ProfitFactor"
assert node.find("Comparator").get("value") == ">="
assert node.find("./Right-Side/Numeric-Value").get("value") == "1.15"
dd_node = _condition("DrawdownPct", "Decimal2Pct", "<=", 20)
assert dd_node.find("./Left-Side/Column-Value").get("column") == "DrawdownPct"
assert dd_node.find("Comparator").get("value") == "<="
assert dd_node.find("./Right-Side/Numeric-Value").get("value") == "20"
resources = ET.fromstring("<Settings><Resources><Symbols><Symbol/></Symbols></Resources></Settings>")
resources.find("./Resources/Symbols/Symbol").set("name", "XAU")
_require_resource_symbol(resources, "XAU")
try:
    _require_resource_symbol(resources, "TSLA")
except ValueError as exc:
    assert "RESOURCE_SYMBOL_MISMATCH" in str(exc)
else:
    raise AssertionError("cal rebutjar un chart sense recurs exacte")
target = ET.fromstring("<Settings><Resources><Symbols><Symbol name='EUR'/></Symbols></Resources></Settings>")
source = ET.fromstring("<Settings><Resources><Symbols><Symbol name='XAU'><InstrumentInfo instrument='XAUUSD'/></Symbol></Symbols></Resources></Settings>")
_graft_resource_symbol(target, source, "XAU")
assert [node.get("name") for node in target.findall("./Resources/Symbols/Symbol")] == ["XAU"]
assert target.find("./Resources/Symbols/Symbol/InstrumentInfo").get("instrument") == "XAUUSD"
print("PASS: temporal retest gates")


def test_generator_source_forces_full_input_databank_not_stale_selection():
    source = ET.fromstring("""<Settings>
      <Databanks retestSelected='true'><Databank name='Input'/><Databank name='Output'/></Databanks>
      <SelectedStrategies><Strategy>STALE</Strategy></SelectedStrategies>
    </Settings>""")
    _select_all_input_strategies(source)
    databanks = source.find('./Databanks')
    assert databanks.get('retestSelected') == 'false'
    assert not source.findall('./SelectedStrategies/Strategy')


def _fixture(tmp_path: Path, candidate_id: str = "T"):
    task = b'''<Settings>
      <Resources><Symbols><Symbol name="NVDA"/></Symbols></Resources>
      <Data><Setups><Setup dateFrom="2000.01.01" dateTo="2001.01.01" testPrecision="1" slippage="7">
        <Chart symbol="OLD" timeframe="H1" spread="9"/>
        <Chart symbol="EXTRA" timeframe="M1" spread="9"/>
        <Commissions><Method type="None" use="false"><Params/></Method></Commissions>
      </Setup></Setups><OutOfSample/></Data>
      <RiskMoneyManagement>
        <MoneyManagement><InitialCapital>1000</InitialCapital>
          <Method type="RiskFixedPctOfAccount" use="false">
            <Parameter key="Risk">2</Parameter><Parameter key="Decimals">2</Parameter>
            <Parameter key="LotsIfNoMM">1</Parameter><Parameter key="MaxLots">1</Parameter>
          </Method>
          <Method type="FixedSize" use="true"><Params><Param key="Size">1</Param></Params></Method>
        </MoneyManagement><RiskManagement maxDrawdown="99"/>
      </RiskMoneyManagement>
      <CrossChecks use="true"/>
      <Rankings type="always"><Conditions><Condition use="true"/></Conditions>
        <DeleteFailedStrategies>true</DeleteFailedStrategies><MaxStrategies>5</MaxStrategies>
        <StopCondition type="time" passedStrategies="5"/>
      </Rankings>
      <Databanks retestSelected="true"><Databank name="Input" value="Old"/>
        <Databank name="Output" value="Old"/></Databanks>
      <SelectedStrategies><Strategy>STALE</Strategy></SelectedStrategies>
    </Settings>'''
    source = tmp_path / "template.cfx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Retest-Task1.xml", task)
    sqx = tmp_path / "candidate.sqx"
    with zipfile.ZipFile(sqx, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr(
            "settings.xml",
            SETTINGS.replace(b'>T</StrategyName>',
                             f'>{candidate_id}</StrategyName>'.encode()))
        archive.writestr("version.txt", "3")
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({
        "periods": {
            "train_from": "2017-01-01", "train_to": "2021-12-31",
            "validation_from": "2022-01-01", "validation_to": "2023-12-31",
            "oos_from": "2024-01-01", "oos_to": "2025-07-31",
            "holdout_from": "2025-08-01", "holdout_to": "2026-07-31",
        },
        "holdout_release_authorized": False,
    }))
    return source, sqx, discovery


def _generate(tmp_path: Path, output_name: str = "retest.cfx", **overrides):
    fixture_candidate_id = overrides.pop("fixture_candidate_id", "T")
    source, sqx, discovery = _fixture(tmp_path, fixture_candidate_id)
    args = dict(
        source=source, output=tmp_path / output_name,
        project_name="RETEST_T", stage="pre_holdout",
        manifest_path=discovery,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        symbol="NVDA", timeframe="M15", candidate_sqx=sqx,
        candidate_id=fixture_candidate_id,
    )
    args.update(overrides)
    return generate(**args), args["output"]


def test_v4_pre_holdout_is_uncensored_candidate_bound_and_reproducible(tmp_path):
    first, first_path = _generate(tmp_path, "first.cfx")
    second, second_path = _generate(tmp_path, "second.cfx")
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first["cfx_sha256"] == second["cfx_sha256"]
    assert first["candidate_id"] == "T"
    assert first["candidate_sqx_sha256"] == hashlib.sha256(
        (tmp_path / "candidate.sqx").read_bytes()).hexdigest()
    assert first["date_from"] == "2017-01-01"
    assert first["date_to"] == "2025-07-31"
    assert first["performance_filters_applied_in_sq"] is False
    assert first["keep_failed"] is True
    assert first["holdout_accessed"] is False
    with zipfile.ZipFile(first_path) as archive:
        task = ET.fromstring(archive.read("Retest-Task1.xml"))
    assert task.findall("./Rankings/Conditions/Condition") == []
    assert task.findtext("./Rankings/DeleteFailedStrategies") == "false"
    assert task.find("./Databanks").get("retestSelected") == "false"
    assert task.find("./Databanks/Databank[@name='Output']").get("value") == "PreHoldout"
    assert verify_retest_project(first_path, first)["candidate_id"] == "T"


def test_retest_verifier_reopens_cfx_and_candidate_sources(tmp_path):
    manifest, cfx = _generate(tmp_path)
    altered = dict(manifest, performance_filters_applied_in_sq=True)
    with pytest.raises(ValueError, match="RETEST_MANIFEST_INVALID"):
        verify_retest_project(cfx, altered)
    (tmp_path / "candidate.sqx").write_bytes(b"changed")
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        verify_retest_project(cfx, manifest)


def test_v4_retest_rejects_wrong_candidate_identity_and_partial_stage(tmp_path):
    source, sqx, discovery = _fixture(tmp_path)
    common = dict(
        source=source, output=tmp_path / "out.cfx", project_name="R",
        manifest_path=discovery,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        symbol="NVDA", timeframe="M15", candidate_sqx=sqx,
    )
    with pytest.raises(ValueError, match="CANDIDATE_ID_MISMATCH"):
        generate(stage="pre_holdout", candidate_id="NOT_T", **common)
    with pytest.raises(ValueError, match="V4_RETEST_STAGE"):
        generate(stage="validation", candidate_id="T", **common)


def test_holdout_remains_locked_even_with_exact_candidate(tmp_path):
    source, sqx, discovery = _fixture(tmp_path)
    with pytest.raises(ValueError, match="HOLDOUT_LOCKED"):
        generate(
            source=source, output=tmp_path / "holdout.cfx", project_name="H",
            stage="holdout", manifest_path=discovery,
            methodology_path=Path(__file__).with_name("methodology_v4.json"),
            symbol="NVDA", timeframe="M15", candidate_sqx=sqx,
            candidate_id="T")
