import pandas as pd
import pytest

from lab.sq_bridge.sqx_extract import SUPPORTED_SIGNAL_NODES
from lab.sq_bridge.strategy_ir_runtime import (
    RUNTIME_SIGNAL_NODES, SignalRuntime, evaluate_entries, simulate_trade_trace,
    sq_atr, sq_ema, sq_roc, sq_rsi, sq_sma,
)


def _frame():
    index = pd.date_range("2024-01-29", periods=8, freq="B")
    close = pd.Series([10, 11, 12, 11, 13, 14, 13, 15], index=index, dtype=float)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1,
                         "close": close}, index=index)


def test_extractor_and_runtime_support_exactly_the_same_signal_nodes():
    assert RUNTIME_SIGNAL_NODES == SUPPORTED_SIGNAL_NODES


def test_runtime_evaluates_composed_signal_with_sq_warmup_at_dataset_edges():
    runtime = SignalRuntime(_frame())
    node = {"op": "AND", "children": [
        {"op": "IsGreater", "children": [
            {"op": "Close"}, {"op": "SMA", "params": {"#Period#": 3}}]},
        {"op": "IsRising", "params": {"#Bars#": 2},
         "children": [{"op": "ROC", "params": {"#Period#": 1}}]},
    ]}
    result = runtime.evaluate(node)
    assert list(result.astype(bool)) == [False, True, False, False, True, False, False, True]
    first = runtime.evaluate({"op": "IsMonthFirstTradingDay"})
    last = runtime.evaluate({"op": "IsMonthLastTradingDay"})
    assert not bool(first.iloc[0])
    assert not bool(last.iloc[-1])


def test_rising_falling_match_installed_sq_bars_shift_rounding_and_flat_rule():
    frame = _frame().iloc[:6].copy()
    frame.loc[:, "close"] = [10.0000001, 11, 11, 12, 11, 10]
    frame.loc[:, "open"] = frame["close"]
    frame.loc[:, "high"] = frame["close"] + 1
    frame.loc[:, "low"] = frame["close"] - 1
    runtime = SignalRuntime(frame)
    rising = runtime.evaluate({
        "op": "IsRising",
        "params": {"#Bars#": 2, "#NotStrict#": True, "#Shift#": 1},
        "children": [{"op": "Close"}],
    })
    falling = runtime.evaluate({
        "op": "IsFalling",
        "params": {"#Bars#": 3, "#NotStrict#": True},
        "children": [{"op": "Close"}],
    })
    # Shift=1 compares the two prior rounded values; equal-only is never true.
    assert rising.tolist() == [False, False, True, False, True, False]
    # Three sampled values mean two comparisons and at least one strict fall.
    assert falling.tolist() == [False, False, False, False, False, True]


def test_rising_rejects_bars_below_sq_minimum():
    with pytest.raises(ValueError, match="Nombre de barres invalid"):
        SignalRuntime(_frame()).evaluate({
            "op": "IsRising", "params": {"#Bars#": 1},
            "children": [{"op": "Close"}],
        })


def test_ir_entry_api_preserves_inactive_direction():
    ir = {"ir_type": "alquimia_strategy_ir", "entries": {
        "long": {"signal": {"op": "Boolean", "params": {"#Value#": True}}},
        "short": None,
    }}
    result = evaluate_entries(ir, _frame())
    assert result["long"].all()
    assert result["short"] is None


def test_runtime_reproduces_sq_highest_lowest_and_all_price_sources():
    runtime = SignalRuntime(_frame())
    highest = runtime.evaluate({"op": "Highest", "params": {
        "#Period#": 3, "#Shift#": 1, "#ComputedFrom#": 2}})
    lowest = runtime.evaluate({"op": "Lowest", "params": {
        "#Period#": 2, "#ComputedFrom#": 3}})
    assert pd.isna(highest.iloc[0])
    assert highest.iloc[1:3].tolist() == [11, 12]
    assert highest.iloc[3] == 13
    assert lowest.iloc[1] == 9
    weighted = runtime.evaluate({"op": "Highest", "params": {
        "#Period#": 1, "#ComputedFrom#": 6}})
    expected = (_frame().high + _frame().low + 2 * _frame().close) / 4
    pd.testing.assert_series_equal(weighted, expected)


def test_highest_lowest_use_available_prefix_during_sq_warmup():
    runtime = SignalRuntime(_frame())
    highest = runtime.evaluate({"op": "Highest", "params": {
        "#Period#": 3, "#ComputedFrom#": 0}})
    lowest = runtime.evaluate({"op": "Lowest", "params": {
        "#Period#": 3, "#ComputedFrom#": 0}})
    assert highest.iloc[:4].tolist() == [10, 11, 12, 12]
    assert lowest.iloc[:4].tolist() == [10, 10, 10, 11]


def _execution_ir(*, direction="long", stop=None, target=None, exit_after=0):
    inactive = "short" if direction == "long" else "long"
    entry = {"signal": {"op": "Boolean", "params": {"#Value#": True}}}
    plan = {"entry_order": "market_at_signal_bar_open",
            "allow_duplicate_trades": False, "exit_after_bars": exit_after,
            "stop_loss": stop or {"type": "percent", "percent": 50},
            "profit_target": target or {"type": "none"}}
    return {"ir_type": "alquimia_strategy_ir", "strategy_id": "candidate",
            "execution": {"exit_at_end_of_day": False, "exit_on_friday": False,
                          "spread_in_sq": 0, "slippage_in_sq": 0,
                          "commission_enabled": False, "swap_enabled": False},
            "entries": {direction: entry, inactive: None},
            "trade_plans": {direction: plan, inactive: None}}


def _utc_frame(rows):
    index = pd.date_range("2024-01-01", periods=len(rows), freq="D", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)


def test_trade_runtime_applies_adverse_stop_gap_and_gross_notional_pnl():
    frame = _utc_frame([(100, 101, 99, 100), (90, 92, 89, 91),
                        (91, 92, 90, 91)])
    trace = simulate_trade_trace(
        _execution_ir(stop={"type": "percent", "percent": 5}), frame, 200)
    first = trace["trades"][0]
    assert first["exit_reason"] == "stop"
    assert first["entry_price"] == 100
    assert first["exit_price"] == 90
    assert first["gross_return"] == pytest.approx(-.1)
    assert first["pnl"] == pytest.approx(-20)
    assert trace["costs_applied"] is False


def test_trade_runtime_time_exit_can_reenter_only_at_a_bar_open():
    frame = _utc_frame([(100, 101, 99, 100), (102, 103, 101, 102),
                        (104, 105, 103, 104), (106, 107, 105, 106),
                        (108, 109, 107, 108)])
    trace = simulate_trade_trace(_execution_ir(exit_after=2), frame, 200)
    assert [(row["entry_price"], row["exit_price"], row["exit_reason"])
            for row in trace["trades"]] == [
                (100, 104, "time"), (104, 108, "time"),
                (108, 108, "EndTest"),
            ]


def test_trade_runtime_uses_warmup_but_only_trades_evaluation_window():
    frame = _utc_frame([(100, 101, 99, 100), (101, 102, 100, 101),
                        (102, 103, 101, 102), (103, 104, 102, 103)])
    trace = simulate_trade_trace(
        _execution_ir(), frame, 200,
        evaluation_start=frame.index[2], evaluation_end=frame.index[3])
    assert [row["timestamp"] for row in trace["signals"]] == [
        frame.index[2].isoformat().replace("+00:00", "Z"),
        frame.index[3].isoformat().replace("+00:00", "Z"),
    ]
    assert trace["trades"][-1]["exit_reason"] == "EndTest"
    assert trace["trades"][-1]["entry_timestamp"].startswith("2024-01-03")


def test_weekend_filter_blocks_entries_but_keeps_protective_exits_active():
    index = pd.date_range("2024-01-05", periods=4, freq="D", tz="UTC")
    frame = pd.DataFrame([
        (100, 101, 99, 100), (100, 101, 99, 100),
        (100, 101, 94, 95), (96, 97, 95, 96),
    ], columns=["open", "high", "low", "close"], index=index)
    ir = _execution_ir(stop={"type": "percent", "percent": 5})
    ir["execution"].update({
        "dont_trade_on_weekends": True,
        "weekend_friday_close_hhmm": 1700,
        "weekend_sunday_open_hhmm": 1700,
    })
    trace = simulate_trade_trace(ir, frame, 200)
    # Friday entry closes through its protective stop on Sunday; no weekend re-entry.
    assert trace["trades"][0]["exit_timestamp"].startswith("2024-01-07")
    assert trace["trades"][1]["entry_timestamp"].startswith("2024-01-08")


def test_trade_runtime_fails_closed_on_ambiguous_intrabar_order():
    frame = _utc_frame([(100, 110, 90, 100), (100, 101, 99, 100)])
    ir = _execution_ir(stop={"type": "percent", "percent": 5},
                       target={"type": "percent", "percent": 5})
    with pytest.raises(ValueError, match="ordre no demostrable"):
        simulate_trade_trace(ir, frame, 200)


def test_sq_atr_uses_prefix_mean_then_wilder_recursion():
    frame = _utc_frame([(10, 12, 9, 11), (11, 14, 10, 13),
                        (13, 15, 12, 14), (14, 18, 13, 17)])
    result = sq_atr(frame, 3)
    assert result.iloc[0] == 3
    assert result.iloc[1] == pytest.approx((3 + 4) / 2)
    assert result.iloc[2] == pytest.approx((3 + 4 + 3) / 3)
    assert result.iloc[3] == pytest.approx(((3 + 4 + 3) / 3 * 2 + 5) / 3)


def test_atr_stop_uses_previous_bar_and_sq_six_decimal_rounding():
    frame = _utc_frame([
        (1.0, 1.123456789, 1.0, 1.1),
        (1.1, 1.2, .95, 1.05),
    ])
    trace = simulate_trade_trace(
        _execution_ir(stop={"type": "atr", "multiple": 1, "period": 14}),
        frame, 200)
    first = trace["trades"][0]
    assert first["exit_reason"] == "stop"
    assert first["exit_price"] == pytest.approx(1.1 - round(.123456789, 6))


def test_sq_sma_and_ema_match_installed_average_calculator_warmup():
    values = pd.Series([10.0, 20.0, 30.0, 40.0])
    assert sq_sma(values, 3).tolist() == pytest.approx([10, 15, 20, 30])
    # SQ: seed first input; alpha=2/(3+1)=0.5 from the second bar onward.
    assert sq_ema(values, 3).tolist() == pytest.approx([10, 15, 22.5, 31.25])


def test_sq_roc_returns_zero_until_period_like_installed_java_block():
    values = pd.Series([100.0, 110.0, 121.0, 133.1])
    assert sq_roc(values, 2).tolist() == pytest.approx([0, 0, 21, 21])


def test_sq_rsi_matches_installed_java_seed_and_wilder_recursion():
    values = pd.Series([10.0, 12.0, 11.0, 14.0, 13.0])
    result = sq_rsi(values, 3)
    # Bars 0..2 are explicitly zero. At bar 3: ups=(2+0+3)/3,
    # downs=(0+1+0)/3. Bar 4 then uses Wilder smoothing.
    assert result.iloc[:3].tolist() == [0, 0, 0]
    assert result.iloc[3] == pytest.approx(100 - 100 / (1 + 5))
    avg_up = ((5 / 3) * 2 + 0) / 3
    avg_down = ((1 / 3) * 2 + 1) / 3
    assert result.iloc[4] == pytest.approx(100 - 100 / (1 + avg_up / avg_down))
