import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from lab.sq_bridge.eurusd_d1_hypothesis_trace_v4 import build
from lab.sq_bridge.hypothesis_screen_artifact_v4 import build_artifact


ROOT = Path(__file__).parent


def _source(tmp_path: Path) -> Path:
    path, rows, day = tmp_path / "eurusd.csv", [], date(2000, 1, 3)
    index = 0
    while len(rows) < 600:
        if day.weekday() < 5:
            shock = .025 if index % 20 == 0 else (-.025 if index % 20 == 10 else 0)
            close = 1.0 + index * .0001 + math.sin(index / 5) * .03 + shock
            open_ = close - math.sin(index / 3) * .002
            rows.append(
                f"{day:%Y.%m.%d},00:00,{open_:.5f},{max(open_, close)+.001:.5f},"
                f"{min(open_, close)-.001:.5f},{close:.5f},100")
            index += 1
        day += timedelta(days=1)
    path.write_text("\n".join(rows) + "\n")
    return path


def _costs(tmp_path: Path, *, frozen: bool = True) -> Path:
    path = tmp_path / "costs.json"
    carry = {f"{scenario}_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    path.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN" if frozen else "BLOCK",
        "costs_frozen": frozen,
        "by_notional": {"200": {"base_roundtrip_bps": 1,
                                    "conservative_roundtrip_bps": 2,
                                    "stress_roundtrip_bps": 4}},
        "carry": {"long": carry, "short": carry},
    }, sort_keys=True) + "\n")
    return path


def test_producer_is_deterministic_preregistered_and_train_only(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    first = build(source, costs, ROOT / "methodology_v4.json")
    second = build(source, costs, ROOT / "methodology_v4.json")
    assert first == second
    assert first["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first["source_rows"] == 600
    assert first["train_rows"] == 300
    assert first["attempted_variants"] == 9
    assert [row["hypothesis_id"] for row in first["hypotheses"]] == [
        "d1_breakout", "d1_momentum", "d1_shock_reversion"]
    train_end = first["train_end_utc"]
    for hypothesis in first["hypotheses"]:
        assert len(hypothesis["variants"]) == 3
        central = hypothesis["variants"][0]
        assert central["variant_id"] == hypothesis["central_variant_id"]
        assert central["neighbor_of"] is None
        for neighbor in hypothesis["variants"][1:]:
            assert neighbor["neighbor_of"] == central["variant_id"]
            differences = {key for key in central["parameters"]
                           if central["parameters"][key] != neighbor["parameters"][key]}
            assert len(differences) == 1
        assert all(trade["exit_timestamp"] <= train_end
                   for variant in hypothesis["variants"]
                   for trade in variant["trades"])


def test_produced_trace_satisfies_real_screen_contract(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    trace = build(source, costs, ROOT / "methodology_v4.json")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace_path, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "artifact.json")
    assert artifact["attempted"] == 9
    assert set(artifact["evaluated_hypothesis_metrics"]) == {
        "d1_breakout", "d1_momentum", "d1_shock_reversion"}


def test_producer_refuses_performance_before_costs_are_frozen(tmp_path):
    with pytest.raises(ValueError, match="must be frozen"):
        build(_source(tmp_path), _costs(tmp_path, frozen=False),
              ROOT / "methodology_v4.json")
