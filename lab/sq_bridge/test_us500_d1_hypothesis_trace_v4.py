import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from lab.sq_bridge.hypothesis_screen_artifact_v4 import verify_source_trade_replay
from lab.sq_bridge.us500_d1_hypothesis_trace_v4 import build


ROOT = Path(__file__).parent


def _source(tmp_path: Path) -> Path:
    path, rows, day = tmp_path / "us500.csv", [], date(2010, 1, 4)
    index = 0
    while len(rows) < 1200:
        if day.weekday() < 5:
            base = 2500 + index * .7 + math.sin(index / 12) * 80
            shock = 85 if index % 40 == 0 else (-90 if index % 40 == 20 else 0)
            close = base + shock
            open_ = base - math.sin(index / 4) * 8
            rows.append(f"{day:%Y.%m.%d},00:00,{open_:.4f},"
                        f"{max(open_, close)+12:.4f},{min(open_, close)-12:.4f},"
                        f"{close:.4f},1000")
            index += 1
        day += timedelta(days=1)
    path.write_text("\n".join(rows) + "\n")
    return path


def _costs(tmp_path: Path, frozen=True) -> Path:
    path = tmp_path / "costs.json"
    path.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN" if frozen else "BLOCK",
        "costs_frozen": frozen}) + "\n")
    return path


def test_us500_grid_is_preregistered_deterministic_and_train_only(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    first = build(source, costs, ROOT / "methodology_v4.json")
    assert first == build(source, costs, ROOT / "methodology_v4.json")
    assert first["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first["source_rows"] == 1200
    assert first["train_rows"] == 600
    assert first["attempted_variants"] == 27
    assert [row["hypothesis_id"] for row in first["hypotheses"]] == [
        f"{family}_{side}" for family in (
            "d1_shock_reversion", "d1_time_series_momentum",
            "d1_volatility_regime_trend")
        for side in ("both", "long", "short")]
    assert all(trade["exit_timestamp"] <= first["train_end_utc"]
               for hypothesis in first["hypotheses"]
               for variant in hypothesis["variants"]
               for trade in variant["trades"])
    assert verify_source_trade_replay(first) is True


def test_us500_replay_rejects_forged_trade(tmp_path):
    trace = build(_source(tmp_path), _costs(tmp_path), ROOT / "methodology_v4.json")
    trade = next(trade for hypothesis in trace["hypotheses"]
                 for variant in hypothesis["variants"]
                 for trade in variant["trades"])
    trade["gross_return_pct"] += 1
    assert verify_source_trade_replay(trace) is False


def test_us500_producer_refuses_to_read_performance_before_costs(tmp_path):
    with pytest.raises(ValueError, match="must be frozen"):
        build(_source(tmp_path), _costs(tmp_path, frozen=False),
              ROOT / "methodology_v4.json")
