import json
from pathlib import Path

from lab.sq_bridge.python_parity_trace_v4 import build
from lab.sq_bridge.parity_artifact_v4 import compare_traces


def _write(tmp_path: Path):
    data = tmp_path / "data.csv"
    data.write_text("\n".join([
        "2024.01.01,00:00,100,101,99,100,1",
        "2024.01.02,00:00,102,103,101,102,1",
        "2024.01.03,00:00,104,105,103,104,1",
        "2024.01.04,00:00,106,107,105,106,1",
        "2024.01.05,00:00,108,109,107,108,1",
    ]) + "\n")
    ir = tmp_path / "ir.json"
    ir.write_text(json.dumps({
        "ir_type": "alquimia_strategy_ir", "strategy_id": "candidate",
        "execution": {"exit_at_end_of_day": False, "exit_on_friday": False},
        "entries": {
            "long": {"signal": {"op": "Boolean", "params": {"#Value#": True}}},
            "short": None},
        "trade_plans": {
            "long": {"entry_order": "market_at_signal_bar_open",
                     "allow_duplicate_trades": False, "exit_after_bars": 2,
                     "stop_loss": {"type": "percent", "percent": 10},
                     "profit_target": {"type": "none"}},
            "short": None},
    }, sort_keys=True) + "\n")
    return ir, data


def test_python_trace_is_deterministic_hashed_and_parity_compatible(tmp_path):
    ir, data = _write(tmp_path)
    first = build(ir, data, 200, tmp_path / "first.json")
    second = build(ir, data, 200, tmp_path / "second.json")
    assert first == second
    assert len(first["trades"]) == 2
    assert first["canonical_ir_sha256"]
    assert first["market_data_sha256"]
    sq = {**first, "source": "strategyquant"}
    metrics = compare_traces(sq, first)
    assert metrics["signal_match_rate"] == 1
    assert metrics["trade_match_rate"] == 1
    assert metrics["pnl_correlation"] == 1
