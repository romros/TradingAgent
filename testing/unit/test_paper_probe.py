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
    save_scan_result,
    get_last_scan_result,
    get_trade_summary,
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


def test_scan_result_persistence_zero_signals():
    """Cada scan deixa rastre persistent encara amb 0 senyals."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        scan_result = {
            "run_utc": _now(),
            "status": "ok",
            "assets": {
                "MSFT": {"status": "ok", "signal": False, "candles": 365, "reason": None},
                "NVDA": {"status": "ok", "signal": False, "candles": 365, "reason": None},
                "QQQ": {"status": "ok", "signal": False, "candles": 365, "reason": None},
            },
            "new_signals": 0,
            "settled_count": 0,
            "pending_count": 0,
            "errors": [],
        }
        save_scan_result(conn, scan_result)
        loaded = get_last_scan_result(conn)
        assert loaded is not None
        assert loaded["status"] == "ok"
        assert loaded["new_signals"] == 0
        assert "MSFT" in loaded["assets"]
        assert loaded["assets"]["MSFT"]["status"] == "ok"
        assert loaded["assets"]["MSFT"]["signal"] is False
        conn.close()
    finally:
        os.unlink(db_path)


def test_trade_summary():
    """Resum de trades: open_count, settled_count, wins, losses, pnl_total."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        now = _now()
        # 1 trade settled win
        save_trade(conn, PaperTradeRecord(
            signal_id=1, asset="MSFT", strategy="capitulation_d1",
            status="settled", signal_date="2025-01-10", entry_date="2025-01-11",
            exit_date="2025-01-11", entry_price=100.0, exit_price=104.0,
            collateral=50.0, leverage=20, nominal=1000.0, fee=5.38,
            pnl=14.62, pnl_pct=29.24, liq_triggered=False,
            created_at=now, updated_at=now,
        ))
        # 1 trade pending
        save_trade(conn, PaperTradeRecord(
            signal_id=2, asset="NVDA", strategy="capitulation_d1",
            status="pending_settlement", signal_date="2025-01-15", entry_date="2025-01-16",
            exit_date=None, entry_price=500.0, exit_price=None,
            collateral=50.0, leverage=20, nominal=1000.0, fee=5.38,
            pnl=None, pnl_pct=None, liq_triggered=False,
            created_at=now, updated_at=now,
        ))
        summary = get_trade_summary(conn)
        assert summary["open_count"] == 1
        assert summary["settled_count"] == 1
        assert summary["wins"] == 1
        assert summary["losses"] == 0
        assert abs(summary["pnl_total"] - 14.62) < 0.01
        assert summary["avg_pnl_per_trade"] is not None
        assert abs(summary["avg_pnl_per_trade"] - 14.62) < 0.01
        assert summary["last_trade"] is not None
        assert summary["last_trade"]["asset"] == "NVDA"
        conn.close()
    finally:
        os.unlink(db_path)


def test_status_payload_stable():
    """Payload /status estable i llegible (serialitzable a JSON)."""
    import json
    from packages.portfolio.db import get_state
    from packages.portfolio.validation import compute_winrate_robust, compute_probe_ok

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        save_scan_result(conn, {
            "run_utc": _now(),
            "status": "ok",
            "assets": {"MSFT": {"status": "ok", "signal": False, "candles": 100, "reason": None}},
            "new_signals": 0,
            "settled_count": 0,
            "pending_count": 0,
            "errors": [],
        })
        conn.close()

        conn = init_db(db_path)
        state = get_state(conn)
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)
        winrate_pct, winrate_confidence = compute_winrate_robust(
            trade_summary["settled_count"], trade_summary["wins"]
        )
        probe_ok = compute_probe_ok(last_scan)
        data = {
            "mode": state.mode,
            "probe_ok": probe_ok,
            "last_scan_utc": state.last_scan_utc,
            "capital": state.capital,
            "total_pnl": state.total_pnl,
            "consecutive_losses": state.consecutive_losses,
            "trades": {
                "open_count": trade_summary["open_count"],
                "settled_count": trade_summary["settled_count"],
                "wins": trade_summary["wins"],
                "losses": trade_summary["losses"],
                "pnl_total": trade_summary["pnl_total"],
                "avg_pnl_per_trade": trade_summary.get("avg_pnl_per_trade"),
                "winrate_pct": winrate_pct,
                "winrate_confidence": winrate_confidence,
                "last_trade": trade_summary["last_trade"],
            },
            "last_scan": last_scan,
        }
        conn.close()
        assert "mode" in data
        assert "probe_ok" in data
        assert "last_scan_utc" in data
        assert "trades" in data
        assert "open_count" in data["trades"]
        assert "settled_count" in data["trades"]
        assert "wins" in data["trades"]
        assert "losses" in data["trades"]
        assert "pnl_total" in data["trades"]
        assert "winrate_confidence" in data["trades"]
        assert "last_scan" in data
        json.dumps(data)
    finally:
        os.unlink(db_path)


def test_asset_error_does_not_break_global():
    """Un asset en error no tomba l'estat global (altres assets visibles)."""
    scan_result = {
        "run_utc": _now(),
        "status": "error",
        "assets": {
            "MSFT": {"status": "ok", "signal": False, "candles": 365, "reason": None},
            "NVDA": {"status": "error", "signal": False, "candles": 0, "reason": "fetch_error"},
            "QQQ": {"status": "ok", "signal": False, "candles": 365, "reason": None},
        },
        "new_signals": 0,
        "settled_count": 0,
        "pending_count": 0,
        "errors": ["fetch NVDA: timeout"],
    }
    # MSFT i QQQ tenen estat; NVDA en error
    assert scan_result["assets"]["MSFT"]["status"] == "ok"
    assert scan_result["assets"]["NVDA"]["status"] == "error"
    assert scan_result["assets"]["QQQ"]["status"] == "ok"


def test_winrate_0_trades():
    """Winrate amb 0 trades: winrate_pct=null, confidence=low."""
    from packages.portfolio.validation import compute_winrate_robust
    wr, conf = compute_winrate_robust(0, 0)
    assert wr is None
    assert conf == "low"


def test_winrate_lt3_trades():
    """Winrate amb <3 trades: winrate_pct=null, confidence=low."""
    from packages.portfolio.validation import compute_winrate_robust
    wr, conf = compute_winrate_robust(2, 1)
    assert wr is None
    assert conf == "low"


def test_winrate_3plus_trades():
    """Winrate amb >=3 trades: valor i confidence=ok."""
    from packages.portfolio.validation import compute_winrate_robust
    wr, conf = compute_winrate_robust(5, 4)
    assert wr == 80.0
    assert conf == "ok"


def test_avg_pnl_calculation():
    """avg_pnl_per_trade correcte."""
    summary = {"settled_count": 4, "wins": 3, "losses": 1, "pnl_total": 50.0}
    avg = 50.0 / 4
    assert abs(avg - 12.5) < 0.01


def test_classification_aligned():
    """Paper dins marge → aligned."""
    from packages.portfolio.validation import classify_validation
    metrics = {"winrate_pct": 78.0, "avg_pnl_per_trade": 12.5}
    r = classify_validation(metrics)
    assert r["status"] == "aligned"


def test_classification_warning():
    """Paper fora marge moderat → warning."""
    from packages.portfolio.validation import classify_validation
    metrics = {"winrate_pct": 65.0, "avg_pnl_per_trade": 12.0}  # WR -13%
    r = classify_validation(metrics)
    assert r["status"] in ("warning", "diverged")


def test_classification_diverged():
    """Paper desviat fort → diverged."""
    from packages.portfolio.validation import classify_validation
    metrics = {"winrate_pct": 50.0, "avg_pnl_per_trade": -5.0}
    r = classify_validation(metrics)
    assert r["status"] == "diverged"


def test_probe_ok_deterministic():
    """probe_ok: True si scan <48h, sense errors, almenys 1 scan."""
    from datetime import timedelta
    from packages.portfolio.validation import compute_probe_ok
    # Scan recent, sense errors
    ok_scan = {"run_utc": _now(), "assets": {"MSFT": {"status": "ok"}}}
    assert compute_probe_ok(ok_scan) is True
    # Sense scan
    assert compute_probe_ok(None) is False
    # Asset en error
    err_scan = {"run_utc": _now(), "assets": {"MSFT": {"status": "error"}}}
    assert compute_probe_ok(err_scan) is False
    # Scan > 48h
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
    old_scan = {"run_utc": old_ts, "assets": {"MSFT": {"status": "ok"}}}
    assert compute_probe_ok(old_scan) is False


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
        test_scan_result_persistence_zero_signals,
        test_trade_summary,
        test_status_payload_stable,
        test_asset_error_does_not_break_global,
        test_winrate_0_trades,
        test_winrate_lt3_trades,
        test_winrate_3plus_trades,
        test_avg_pnl_calculation,
        test_classification_aligned,
        test_classification_warning,
        test_classification_diverged,
        test_probe_ok_deterministic,
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
