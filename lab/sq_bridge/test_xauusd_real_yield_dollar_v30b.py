import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from lab.sq_bridge.xauusd_real_yield_dollar_v30b import (
    assert_macro_only, decision_time, episodes, evaluate, parameter_grid,
)

CONFIG = json.loads(Path(__file__).with_name("family_xauusd_real_yield_dollar_v30b.json").read_text())


def test_grid_and_seals_are_frozen():
    assert len(parameter_grid(CONFIG)) == 27
    assert_macro_only(CONFIG)
    broken = dict(CONFIG, holdout_accessed=True)
    with pytest.raises(ValueError, match="remain sealed"):
        assert_macro_only(broken)


def test_decision_is_delayed_until_wednesday():
    assert decision_time(date(2014, 1, 3)).isoformat() == "2014-01-08T00:00:00"


def test_episodes_persist_and_flip_without_double_counting():
    start = date(2014, 1, 3)
    rows = [{"friday": start + timedelta(days=7 * index), "state": state}
            for index, state in enumerate([0, 1, 1, 0, -1, -1, 1])]
    result = episodes(rows)
    assert [(row["side"], row["weeks"]) for row in result] == [(1, 2), (-1, 2), (1, 1)]
    assert result[0]["decision_time_utc"].endswith("Z")


def test_synthetic_macro_preflight_is_fail_closed(tmp_path):
    config = json.loads(json.dumps(CONFIG))
    config["splits"]["train"] = ["2007-01-01", "2014-12-31"]
    # Constant signals cannot produce balanced long/short episodes.
    start = date(2007, 1, 1)
    real, dollar = {}, {}
    for index in range(8 * 366):
        stamp = start + timedelta(days=index)
        if stamp.weekday() < 5:
            real[stamp] = 1.0
            dollar[stamp] = 100.0
    source = tmp_path / "source.csv"
    source.write_text("test")
    result = evaluate(config, real, dollar, [source])
    assert result["decision"] == "REJECT_MACRO_FREQUENCY"
    assert result["attempted"] == 27
    assert result["xau_performance_accessed"] is False
    assert result["holdout_accessed"] is False
