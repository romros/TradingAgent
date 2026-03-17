import sqlite3
from typing import Optional

from fastapi import APIRouter, Query

from packages.shared import config
from packages.shared.models import AgentState
from packages.portfolio.db import (
    init_db,
    get_all_signals,
    get_all_trades,
    get_state,
    get_last_scan_result,
    get_trade_summary,
    save_validation_run,
    get_scan_runs,
    get_validation_runs,
    get_equity_curve,
    get_drawdown,
)
from packages.portfolio.validation import (
    compute_probe_ok,
    compute_winrate_robust,
    run_validation,
)
from packages.strategy.capitulation_d1 import CapitulationD1Strategy
from packages.market.data_feed import YFinanceD1Feed, validate_candles
from packages.execution.paper import PaperExecutor
from packages.portfolio.tracker import PortfolioTracker
from packages.runtime.engine import DailyEngine

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    return init_db(config.DB_PATH)


@router.get("/health")
def health():
    return {"status": "ok", "mode": "paper", "assets": config.ASSETS}


@router.get("/status")
def status():
    """Estat operatiu enriquit del paper probe. Permet verificar el probe sense obrir la DB."""
    conn = _get_conn()
    try:
        state = get_state(conn)
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)

        winrate_pct, winrate_confidence = compute_winrate_robust(
            trade_summary["settled_count"], trade_summary["wins"]
        )
        probe_ok = compute_probe_ok(last_scan)

        payload = {
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
        return payload
    finally:
        conn.close()


@router.get("/probe-summary")
def probe_summary():
    """Resum compacte per verificació diària. Subconjunt de /status."""
    conn = _get_conn()
    try:
        state = get_state(conn)
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)
        winrate_pct, winrate_confidence = compute_winrate_robust(
            trade_summary["settled_count"], trade_summary["wins"]
        )
        probe_ok = compute_probe_ok(last_scan)
        return {
            "probe_ok": probe_ok,
            "last_scan_utc": state.last_scan_utc,
            "last_scan_status": last_scan.get("status") if last_scan else None,
            "assets": last_scan.get("assets", {}) if last_scan else {},
            "trades_open": trade_summary["open_count"],
            "trades_settled": trade_summary["settled_count"],
            "wins": trade_summary["wins"],
            "losses": trade_summary["losses"],
            "pnl_total": trade_summary["pnl_total"],
            "avg_pnl_per_trade": trade_summary.get("avg_pnl_per_trade"),
            "winrate_pct": winrate_pct,
            "winrate_confidence": winrate_confidence,
        }
    finally:
        conn.close()


@router.get("/validation")
def validation():
    """Validació paper vs backtest. Mètriques + classificació aligned/warning/diverged."""
    import logging
    conn = _get_conn()
    try:
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)
        result = run_validation(trade_summary, last_scan)
        save_validation_run(conn, result)
        logging.getLogger(__name__).info("validation_run_saved")
        return result
    finally:
        conn.close()


@router.get("/probe-history")
def probe_history(limit: int = 100):
    """Historial de scans, validacions, equity curve i drawdown."""
    conn = _get_conn()
    try:
        state = get_state(conn)
        capital = state.capital if state.capital > 0 else config.CAPITAL_INITIAL
        return {
            "scan_runs": get_scan_runs(conn, limit=limit),
            "validation_runs": get_validation_runs(conn, limit=limit),
            "equity_curve": get_equity_curve(conn, capital_initial=capital),
            "drawdown": get_drawdown(conn, capital_initial=capital),
        }
    finally:
        conn.close()


@router.get("/signals")
def get_signals(
    asset: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    conn = _get_conn()
    try:
        return get_all_signals(conn, asset=asset, limit=limit)
    finally:
        conn.close()


@router.get("/trades")
def get_trades(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
):
    conn = _get_conn()
    try:
        return get_all_trades(conn, status=status, limit=limit)
    finally:
        conn.close()


@router.get("/data-quality")
def data_quality():
    """Qualitat del data feed per asset. Valida candles D1 (yfinance)."""
    import logging
    feed = YFinanceD1Feed()
    result = {"source": "yfinance", "assets": {}}
    for asset in config.ASSETS:
        try:
            candles = feed.fetch(asset, days=config.DATA_LOOKBACK_DAYS)
            validation = validate_candles(candles)
            result["assets"][asset] = {
                "status": validation["status"],
                "candles_count": len(candles),
                "warnings": validation["warnings"],
                "errors": validation["errors"],
            }
            logging.getLogger(__name__).info(
                "data_quality_check asset=%s status=%s candles=%s",
                asset, validation["status"], len(candles),
            )
        except Exception as e:
            result["assets"][asset] = {
                "status": "error",
                "candles_count": 0,
                "warnings": [],
                "errors": [str(e)[:100]],
            }
    return result


@router.post("/scan")
def manual_scan():
    strategy = CapitulationD1Strategy(
        body_thresh=config.BODY_THRESH,
        bb_period=config.BB_PERIOD,
        bb_std=config.BB_STD,
    )
    feed = YFinanceD1Feed()
    executor = PaperExecutor(
        leverage=config.LEVERAGE,
        col_pct=config.COL_PCT,
        col_max=config.COL_MAX,
        col_min=config.COL_MIN,
        fee=config.FEE,
    )
    tracker = PortfolioTracker(db_path=config.DB_PATH)
    engine = DailyEngine(
        assets=config.ASSETS,
        strategy=strategy,
        feed=feed,
        executor=executor,
        tracker=tracker,
        db_path=config.DB_PATH,
    )
    return engine.run()
