import pandas as pd

from lab.sq_bridge.sqx_extract import SUPPORTED_SIGNAL_NODES
from lab.sq_bridge.strategy_ir_runtime import (
    RUNTIME_SIGNAL_NODES, SignalRuntime, evaluate_entries)


def _frame():
    index = pd.date_range("2024-01-29", periods=8, freq="B")
    close = pd.Series([10, 11, 12, 11, 13, 14, 13, 15], index=index, dtype=float)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1,
                         "close": close}, index=index)


def test_extractor_and_runtime_support_exactly_the_same_signal_nodes():
    assert RUNTIME_SIGNAL_NODES == SUPPORTED_SIGNAL_NODES


def test_runtime_evaluates_composed_signal_without_lookahead_at_dataset_edges():
    runtime = SignalRuntime(_frame())
    node = {"op": "AND", "children": [
        {"op": "IsGreater", "children": [
            {"op": "Close"}, {"op": "SMA", "params": {"#Period#": 3}}]},
        {"op": "IsRising", "params": {"#Bars#": 1},
         "children": [{"op": "ROC", "params": {"#Period#": 1}}]},
    ]}
    result = runtime.evaluate(node)
    assert list(result.astype(bool)) == [False, False, False, False, True, False, False, True]
    first = runtime.evaluate({"op": "IsMonthFirstTradingDay"})
    last = runtime.evaluate({"op": "IsMonthLastTradingDay"})
    assert not bool(first.iloc[0])
    assert not bool(last.iloc[-1])


def test_ir_entry_api_preserves_inactive_direction():
    ir = {"ir_type": "alquimia_strategy_ir", "entries": {
        "long": {"signal": {"op": "Boolean", "params": {"#Value#": True}}},
        "short": None,
    }}
    result = evaluate_entries(ir, _frame())
    assert result["long"].all()
    assert result["short"] is None
