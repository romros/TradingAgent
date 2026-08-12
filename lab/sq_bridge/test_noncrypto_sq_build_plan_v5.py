from pathlib import Path

import pytest

from lab.sq_bridge.noncrypto_sq_build_plan_v5 import (
    DEFAULT_PREREG, compile_plan, verify_plan,
)


def test_sealed_campaign_compiles_to_18_budget_safe_jobs():
    plan = compile_plan(DEFAULT_PREREG)
    verify_plan(plan)
    assert plan["job_count"] == 18
    assert sum(row["evolution"]["nominal_evaluations"] for row in plan["jobs"]) == 76_800
    assert {row["resource"]["chart_timeframe"] for row in plan["jobs"]} == {"M15", "D1"}


def test_exit_branches_do_not_multiply_family_budget():
    plan = compile_plan(DEFAULT_PREREG)
    xau = [row for row in plan["jobs"]
           if row["hypothesis_id"] == "xau-m15-macro-compression-breakout-v5"]
    assert [row["evolution"]["generations"] for row in xau] == [17, 17, 16]
    assert sum(row["evolution"]["nominal_evaluations"] for row in xau) == 16_000


def test_future_periods_remain_embargoed_and_execution_disabled():
    plan = compile_plan(DEFAULT_PREREG)
    assert plan["authorization"]["execute_sqcli"] is False
    assert all(row["future_periods_embargoed"] == ["validation", "oos", "holdout"]
               for row in plan["jobs"])


def test_every_job_has_fixed_stop_target_and_time_exit():
    plan = compile_plan(DEFAULT_PREREG)
    for job in plan["jobs"]:
        assert job["exit_semantics"]["stop"]
        assert job["exit_semantics"]["target"]
        assert job["exit_semantics"]["max_bars"] >= 1


def test_missing_history_fails_closed(tmp_path: Path):
    plan = compile_plan(DEFAULT_PREREG)
    plan["jobs"][0]["resource"]["history_path"] = str(tmp_path / "missing.dat")
    with pytest.raises(ValueError, match="SQ history missing"):
        verify_plan(plan)
