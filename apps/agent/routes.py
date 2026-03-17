import sqlite3
from typing import Optional

from fastapi import APIRouter, Query

from packages.shared import config
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
    compute_live_readiness,
)
from packages.market.bs_probe import run_bs_audit, run_proxy_validation
from packages.market.data_quality import get_data_quality_result
from packages.runtime.daily_snapshot import build_daily_snapshot
from packages.runtime.scan_runner import run_daily_scan

router = APIRouter()


def _get_conn() -> sqlite3.Connection:
    return init_db(config.DB_PATH)


@router.get("/health")
def health():
    return {"status": "ok", "mode": "paper", "assets": config.ASSETS}


@router.get("/quick-status")
def quick_status():
    """T8d: Resum ràpid per consulta humana 'com va?'. Curt i útil."""
    conn = _get_conn()
    try:
        state = get_state(conn)
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)
        winrate_pct, winrate_confidence = compute_winrate_robust(
            trade_summary["settled_count"], trade_summary["wins"]
        )
        probe_ok = compute_probe_ok(last_scan)
        validation_result = run_validation(trade_summary, last_scan)
        proxy_result = run_proxy_validation(base_url=config.BS_BASE_URL, days=config.DATA_LOOKBACK_DAYS)
        data_quality_result = _get_data_quality_result()
        bs_audit_result = run_bs_audit(assets=config.ASSETS, base_url=config.BS_BASE_URL)
        live_result = compute_live_readiness(
            validation_result=validation_result,
            proxy_result=proxy_result,
            data_quality_result=data_quality_result,
            bs_audit_result=bs_audit_result,
        )
        return {
            "ok": True,
            "probe_ok": probe_ok,
            "last_scan_utc": state.last_scan_utc,
            "trades": {
                "settled": trade_summary["settled_count"],
                "wins": trade_summary["wins"],
                "losses": trade_summary["losses"],
                "pnl": trade_summary["pnl_total"],
                "winrate_pct": winrate_pct,
            },
            "validation": validation_result.get("validation", {}).get("status"),
            "live_readiness": live_result.get("status"),
        }
    finally:
        conn.close()


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


@router.get("/bs-audit")
def bs_audit():
    """Auditoria de BrokerageService: assets disponibles, qualitat D1, comparació vs yfinance."""
    return run_bs_audit(assets=config.ASSETS, base_url=config.BS_BASE_URL)


@router.get("/proxy-validation")
def proxy_validation():
    """T8b: Validació proxy QQQ vs NASDAQUSD/NDXUSD. Correlació returns, classificació aligned|warning|diverged."""
    return run_proxy_validation(base_url=config.BS_BASE_URL, days=config.DATA_LOOKBACK_DAYS)


def _get_data_quality_result() -> dict:
    """Retorna resultat data_quality (reutilitzat per /live-readiness)."""
    return get_data_quality_result(config.ASSETS, config.DATA_LOOKBACK_DAYS)


@router.get("/live-readiness")
def live_readiness():
    """T8c: Decision gate probe → shadow/live. Agrega validation, proxy, data_quality, bs_audit."""
    conn = _get_conn()
    try:
        trade_summary = get_trade_summary(conn)
        last_scan = get_last_scan_result(conn)
        validation_result = run_validation(trade_summary, last_scan)
    finally:
        conn.close()
    proxy_result = run_proxy_validation(base_url=config.BS_BASE_URL, days=config.DATA_LOOKBACK_DAYS)
    data_quality_result = _get_data_quality_result()
    bs_audit_result = run_bs_audit(assets=config.ASSETS, base_url=config.BS_BASE_URL)
    return compute_live_readiness(
        validation_result=validation_result,
        proxy_result=proxy_result,
        data_quality_result=data_quality_result,
        bs_audit_result=bs_audit_result,
    )


@router.get("/data-quality")
def data_quality():
    """Qualitat del data feed per asset. Valida candles D1 (yfinance)."""
    import logging
    result = _get_data_quality_result()
    for asset, info in result["assets"].items():
        logging.getLogger(__name__).info(
            "data_quality_check asset=%s status=%s candles=%s",
            asset, info.get("status"), info.get("candles_count", 0),
        )
    return result


@router.post("/snapshot")
def generate_snapshot():
    """T7d: Genera snapshot diari del probe. Format Markdown a data/probe_snapshots/."""
    result = build_daily_snapshot(
        db_path=config.DB_PATH,
        output_dir=config.PROBE_SNAPSHOTS_DIR,
        assets=config.ASSETS,
        base_url=config.BS_BASE_URL,
        days=config.DATA_LOOKBACK_DAYS,
    )
    return result


@router.post("/scan")
def manual_scan():
    """Executa scan diari. També cridat pel scheduler automàtic."""
    return run_daily_scan()
