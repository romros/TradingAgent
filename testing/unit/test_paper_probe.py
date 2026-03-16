import sys
import os
import math
import tempfile
import sqlite3
from datetime import datetime, timezone

# Assegura que el PYTHONPATH inclou l'arrel del projecte
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from packages.shared.models import SignalRecord, PaperTradeRecord, AgentState
from packages.strategy.capitulation_d1 import CapitulationD1Strategy
from packages.execution.paper import PaperExecutor
from packages.portfolio.db import (
    init_db,
    save_signal,
    signal_exists,
    save_trade,
    get_all_trades,
    get_all_signals,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_candles(n: int = 25, base_close: float = 100.0) -> list:
    """Genera n candles normals (sense senyal)."""
    candles = []
    for i in range(n):
        c = base_close + i * 0.1
        candles.append({
            "date": f"2025-01-{i+1:02d}",
            "open": c,
            "high": c + 0.5,
            "low": c - 0.5,
            "close": c,
        })
    return candles


def _bb_lower(closes: list, period: int = 20, std_mult: float = 2.0) -> float:
    c = closes[-period:]
    mean = sum(c) / len(c)
    variance = sum((x - mean) ** 2 for x in c) / len(c)
    return mean - std_mult * math.sqrt(variance)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_strategy_detect():
    """L'última candle és un senyal: body<-2% i close<BB_lower."""
    candles = _make_candles(25, base_close=200.0)

    # Última candle: open=200, close=193 → body=-3.5% (< -2%)
    # I close ha de ser < BB_lower
    # BB_lower de les 20 candles anteriors (índex 5..24) → les últimes 20
    # Substituïm l'última
    signal_candle = {
        "date": "2025-01-26",
        "open": 200.0,
        "high": 200.0,
        "low": 192.0,
        "close": 193.0,  # body=-3.5%
    }
    candles.append(signal_candle)

    # Calcular BB_lower de les 20 candles (les últimes 20 del total ara són les 20 ja afegides)
    closes = [float(c["close"]) for c in candles[-20:]]
    # Substituïm l'últim close (193) en el càlcul — ja és a candles[-20:]
    bb_val = _bb_lower(closes)

    # Comprovem que la condició es compleix
    assert 193.0 < bb_val, f"close {193.0} ha de ser < bb_lower {bb_val} per al test"

    strategy = CapitulationD1Strategy(body_thresh=-0.02, bb_period=20, bb_std=2.0)
    result = strategy.detect(candles, asset="MSFT")

    assert result is not None, "Hauria de detectar senyal"
    assert result.asset == "MSFT"
    assert result.strategy == "capitulation_d1"
    assert result.direction == "long"
    assert result.body_pct < -0.02
    assert result.close_price == 193.0


def test_strategy_no_signal():
    """Candle normal sense senyal."""
    candles = _make_candles(26, base_close=100.0)
    strategy = CapitulationD1Strategy(body_thresh=-0.02, bb_period=20, bb_std=2.0)
    result = strategy.detect(candles, asset="NVDA")
    assert result is None, "No hauria de detectar senyal en candles normals"


def test_paper_executor_settle_win():
    """Trade guanyador: close > open."""
    executor = PaperExecutor(leverage=20, col_pct=0.20, col_max=60.0, col_min=15.0, fee=5.38)

    signal = SignalRecord(
        id=1,
        candle_date="2025-01-10",
        asset="MSFT",
        strategy="capitulation_d1",
        created_at=_now(),
    )
    entry_candle = {"date": "2025-01-11", "open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0}
    trade = executor.open_trade(signal, capital=250.0, entry_candle=entry_candle)

    assert trade.collateral == min(max(250.0 * 0.20, 15.0), 60.0)
    assert trade.nominal == trade.collateral * 20

    settlement_candle = {"date": "2025-01-11", "open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0}
    settled = executor.settle_trade(trade, settlement_candle)

    expected_pnl = trade.nominal * (104.0 - 100.0) / 100.0 - 5.38
    assert settled.status == "settled"
    assert not settled.liq_triggered
    assert abs(settled.pnl - expected_pnl) < 0.01
    assert settled.pnl > 0


def test_paper_executor_settle_loss():
    """Trade perdedor: close < open, però sense liquidació."""
    executor = PaperExecutor(leverage=20, col_pct=0.20, col_max=60.0, col_min=15.0, fee=5.38)

    signal = SignalRecord(
        id=2,
        candle_date="2025-01-10",
        asset="MSFT",
        strategy="capitulation_d1",
        created_at=_now(),
    )
    entry_candle = {"date": "2025-01-11", "open": 100.0, "high": 100.0, "low": 99.0, "close": 99.0}
    trade = executor.open_trade(signal, capital=250.0, entry_candle=entry_candle)

    # close < open però MAE = (100-99)/100 = 1% < 5% → no liq
    settlement_candle = {"date": "2025-01-11", "open": 100.0, "high": 100.0, "low": 99.0, "close": 99.0}
    settled = executor.settle_trade(trade, settlement_candle)

    assert settled.status == "settled"
    assert not settled.liq_triggered
    assert settled.pnl < 0


def test_paper_executor_settle_liq():
    """Trade liquidat: MAE >= 5%."""
    executor = PaperExecutor(leverage=20, col_pct=0.20, col_max=60.0, col_min=15.0, fee=5.38)

    signal = SignalRecord(
        id=3,
        candle_date="2025-01-10",
        asset="MSFT",
        strategy="capitulation_d1",
        created_at=_now(),
    )
    entry_candle = {"date": "2025-01-11", "open": 100.0, "high": 100.0, "low": 94.0, "close": 94.5}
    trade = executor.open_trade(signal, capital=250.0, entry_candle=entry_candle)

    # MAE = (100-94)/100 = 6% >= 5% → liquidació
    settlement_candle = {"date": "2025-01-11", "open": 100.0, "high": 100.0, "low": 94.0, "close": 94.5}
    settled = executor.settle_trade(trade, settlement_candle)

    assert settled.status == "liq_settled"
    assert settled.liq_triggered
    expected_pnl = -trade.collateral - 5.38
    assert abs(settled.pnl - expected_pnl) < 0.01


def test_db_round_trip():
    """Crear signal + trade, guardar, carregar."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)

        signal = SignalRecord(
            candle_date="2025-02-01",
            asset="QQQ",
            strategy="capitulation_d1",
            direction="long",
            body_pct=-0.03,
            bb_lower=420.0,
            close_price=418.0,
            mode="paper",
            created_at=_now(),
        )
        signal_id = save_signal(conn, signal)
        assert signal_id is not None and signal_id > 0

        now = _now()
        trade = PaperTradeRecord(
            signal_id=signal_id,
            asset="QQQ",
            strategy="capitulation_d1",
            status="pending_settlement",
            signal_date="2025-02-01",
            entry_date="2025-02-02",
            entry_price=419.0,
            collateral=50.0,
            leverage=20,
            nominal=1000.0,
            fee=5.38,
            created_at=now,
            updated_at=now,
        )
        trade_id = save_trade(conn, trade)
        assert trade_id is not None and trade_id > 0

        signals = get_all_signals(conn, asset="QQQ")
        assert len(signals) == 1
        assert signals[0]["candle_date"] == "2025-02-01"

        trades = get_all_trades(conn, status="pending_settlement")
        assert len(trades) == 1
        assert trades[0]["asset"] == "QQQ"

        conn.close()
    finally:
        os.unlink(db_path)


def test_db_no_duplicate_signal():
    """signal_exists retorna True per duplicat."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)

        signal = SignalRecord(
            candle_date="2025-03-01",
            asset="NVDA",
            strategy="capitulation_d1",
            created_at=_now(),
        )
        save_signal(conn, signal)

        exists = signal_exists(conn, "2025-03-01", "NVDA")
        assert exists is True, "Ha de retornar True per duplicat"

        not_exists = signal_exists(conn, "2025-03-01", "MSFT")
        assert not_exists is False, "Ha de retornar False per asset diferent"

        conn.close()
    finally:
        os.unlink(db_path)


# ─── Runner ──────────────────────────────────────────────────────────────────

def _run_tests():
    ok = True
    tests = [
        test_strategy_detect,
        test_strategy_no_signal,
        test_paper_executor_settle_win,
        test_paper_executor_settle_loss,
        test_paper_executor_settle_liq,
        test_db_round_trip,
        test_db_no_duplicate_signal,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except Exception as e:
            import traceback
            print(f"  FAIL {t.__name__}: {e}")
            traceback.print_exc()
            ok = False
    return ok


if __name__ == "__main__":
    print("=== Paper Probe Unit Tests ===")
    sys.exit(0 if _run_tests() else 1)
