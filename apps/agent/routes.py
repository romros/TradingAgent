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
)
from packages.strategy.capitulation_d1 import CapitulationD1Strategy
from packages.market.data_feed import YFinanceD1Feed
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
    conn = _get_conn()
    try:
        state = get_state(conn)
        trades = get_all_trades(conn, limit=1000)
        signals = get_all_signals(conn, limit=1000)
        return {
            "mode": state.mode,
            "last_scan_utc": state.last_scan_utc,
            "capital": state.capital,
            "total_pnl": state.total_pnl,
            "open_trade_count": state.open_trade_count,
            "settled_count": state.settled_count,
            "consecutive_losses": state.consecutive_losses,
            "total_signals": len(signals),
            "total_trades": len(trades),
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
