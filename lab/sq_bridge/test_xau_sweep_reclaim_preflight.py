from dataclasses import replace

import pandas as pd

from lab.sq_bridge.xau_sweep_reclaim_preflight import (
    CostScenario, Parameters, build_summary, metrics, simulate, stability_counts,
)


def _frame(bars):
    start = 1_600_000_000 // 14_400 * 14_400
    rows = []
    for i, (o, h, l, c) in enumerate(bars):
        rows.append({"ts": start + i * 14_400, "open": o, "high": h,
                     "low": l, "close": c, "volume": 1})
    f = pd.DataFrame(rows)
    f.index = pd.to_datetime(f.ts, unit="s", utc=True)
    return f


def test_signal_enters_next_bar_and_stop_wins_ambiguous_bar():
    bars = [(100, 101, 99, 100)] * 4
    bars += [(100, 101, 99, 100), (100, 105, 98, 101), (101, 110, 90, 100)]
    p = Parameters("long", 3, 2, 2, 1, 1)
    trades = simulate(_frame(bars), p)
    assert len(trades) == 1
    assert trades[0]["entry"] == 101
    assert trades[0]["reason"] == "stop"
    assert trades[0]["ambiguous_h4"] is True
    assert trades[0]["gross_return"] < 0


def test_cost_and_funding_reduce_metrics():
    trades = [{"entry_ts": 0, "exit_ts": 86_400, "year": 2020,
               "gross_return": .01, "mae": .005} for _ in range(4)]
    cheap = metrics(trades, CostScenario("cheap", 0, 0))
    dear = metrics(trades, CostScenario("dear", 20, 12))
    assert dear["expectancy_bps"] < cheap["expectancy_bps"]
    assert dear["compound_return_pct"] < cheap["compound_return_pct"]


def test_stability_rejects_isolated_point_and_accepts_neighbours():
    base = Parameters("long", 10, 4, 14, 2, 2)
    points = [base, replace(base, lookback=5), replace(base, exit_bars=2)]
    rows = []
    for p in points:
        good = {"trades": 60, "profit_factor": 1.3, "positive_year_ratio": .7,
                "expectancy_bps": 2}
        rows.append({"parameters": p.__dict__, "metrics": {"stress": good}})
    stability_counts(rows)
    assert rows[0]["stable_region_member"] is True
    assert rows[1]["stable_region_member"] is False


def test_summary_hashes_full_artifact(tmp_path):
    full = tmp_path / "full.json"; full.write_text("full\n")
    good = {"trades": 60, "profit_factor": 1.3, "positive_year_ratio": .7,
            "expectancy_bps": 2}
    rows = []
    for direction in ("long", "short", "both"):
        p = Parameters(direction, 20, 6, 14, 2.0, 2.0)
        rows.append({"parameters": p.__dict__, "metrics": {
            "base": good, "conservative": good, "stress": good}})
    result = {"experiment": "x", "decision_scope": "train", "holdout_accessed": False,
              "execution_model": "h4", "coverage": {}, "cost_scenarios": [],
              "grid_points": 3, "stress_gate_passes": 3,
              "stable_region_members": 0, "verdict": "REJECT", "rows": rows}
    summary = build_summary(result, full)
    assert summary["full_artifact_sha256"]
    assert summary["neutral_seed_control"]["parameters"]["lookback"] == 20
