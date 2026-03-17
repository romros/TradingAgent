import sqlite3
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from packages.shared.models import SignalRecord, PaperTradeRecord, AgentState
from packages.portfolio.db import (
    init_db,
    save_signal,
    signal_exists,
    save_trade,
    update_trade,
    get_pending_trades,
    get_state,
    save_state,
    save_scan_result,
)

logger = logging.getLogger(__name__)


def _log_scan(asset: str, status: str, signal: bool = False, candles: int = 0, reason: Optional[str] = None):
    """Log estructurat per resultat de scan per asset."""
    parts = [f"asset={asset}", f"status={status}", f"signal={signal}", f"candles={candles}"]
    if reason:
        parts.append(f'reason="{reason}"')
    logger.info("scan_completed " + " ".join(parts))


def _log_settlement(trades_open: int, trades_settled: int, pnl_total: float):
    """Log estructurat per settlement."""
    logger.info(
        f"settlement_completed trades_open={trades_open} trades_settled={trades_settled} pnl_total={pnl_total:.2f}"
    )


class DailyEngine:
    """
    Engine per al paper probe D1. Executar un cop al dia (idealment post-close).
    Fa:
    1. Fetch candles D1 per cada asset
    2. Detecta senyals nous (no duplicats)
    3. Tanca trades pending (si tenim la candle T+1)
    4. Obre trades nous (si hi ha senyal i no hi ha trade pendent obert)
    5. Actualitza estat
    """

    def __init__(self, assets, strategy, feed, executor, tracker, db_path: str):
        self.assets = assets
        self.strategy = strategy
        self.feed = feed
        self.executor = executor
        self.tracker = tracker
        self.db_path = db_path

    def _today(self) -> str:
        return date.today().isoformat()

    def _yesterday(self) -> str:
        return (date.today() - timedelta(days=1)).isoformat()

    def run(self) -> dict:
        """
        Retorna dict amb resum: new_signals, settled_trades, pending_trades, errors.
        Persisteix resultat de scan i emet logs estructurats.
        """
        conn = init_db(self.db_path)
        result = {
            "new_signals": [],
            "settled_trades": [],
            "pending_trades": [],
            "errors": [],
        }
        assets_result = {}  # {asset: {status, signal, candles, reason}}

        try:
            # Carregar tots els trades pendents
            pending_by_asset = {}
            for trade in get_pending_trades(conn):
                pending_by_asset[trade.asset] = trade

            candles_by_asset = {}

            # 1. Fetch candles per cada asset
            for asset in self.assets:
                try:
                    candles = self.feed.fetch(asset)
                    candles_by_asset[asset] = candles
                except Exception as e:
                    err_msg = str(e)
                    result["errors"].append(f"fetch {asset}: {e}")
                    candles_by_asset[asset] = []
                    assets_result[asset] = {
                        "status": "error",
                        "signal": False,
                        "candles": 0,
                        "reason": f"fetch_error: {err_msg[:80]}",
                    }
                    _log_scan(asset, "error", signal=False, candles=0, reason=err_msg)

            # 2. Tanca trades pendents
            for asset, trade in list(pending_by_asset.items()):
                candles = candles_by_asset.get(asset, [])
                if not candles:
                    result["pending_trades"].append(asset)
                    continue

                # Buscar la candle corresponent a entry_date (T+1 ja tancada)
                settlement_candle = None
                entry_date = trade.entry_date
                today = self._today()

                for c in reversed(candles):
                    if str(c["date"]) == entry_date and str(c["date"]) < today:
                        settlement_candle = c
                        break
                    elif str(c["date"]) > entry_date and str(c["date"]) < today:
                        # Agafem la candle més propera disponible
                        if settlement_candle is None or str(c["date"]) < str(settlement_candle["date"]):
                            settlement_candle = c

                if settlement_candle is None:
                    result["pending_trades"].append(asset)
                    continue

                try:
                    settled = self.executor.settle_trade(trade, settlement_candle)
                    update_trade(conn, settled)
                    self.tracker.update_after_settlement(settled)
                    result["settled_trades"].append({
                        "asset": asset,
                        "pnl": settled.pnl,
                        "status": settled.status,
                    })
                    del pending_by_asset[asset]
                except Exception as e:
                    result["errors"].append(f"settle {asset}: {e}")

            # 3. Detecta senyals nous i obre trades
            state = get_state(conn)

            for asset in self.assets:
                if asset in assets_result:
                    continue  # Ja registrat (error fetch)
                candles = candles_by_asset.get(asset, [])
                n_candles = len(candles)
                if n_candles < self.strategy.bb_period:
                    assets_result[asset] = {
                        "status": "warning",
                        "signal": False,
                        "candles": n_candles,
                        "reason": "insufficient_candles",
                    }
                    _log_scan(asset, "warning", signal=False, candles=n_candles, reason="insufficient_candles")
                    continue

                # Detectar senyal sobre la candle d'ahir (la més recent tancada)
                # Usem totes les candles però el senyal es basa en la última
                signal = self.strategy.detect(candles, asset=asset, mode=state.mode)

                if signal is None:
                    assets_result[asset] = {"status": "ok", "signal": False, "candles": n_candles, "reason": None}
                    _log_scan(asset, "ok", signal=False, candles=n_candles)
                    continue

                assets_result[asset] = {"status": "ok", "signal": True, "candles": n_candles, "reason": None}
                _log_scan(asset, "ok", signal=True, candles=n_candles)

                # Comprovar duplicats
                if signal_exists(conn, signal.candle_date, asset):
                    continue

                # Guardar senyal
                try:
                    signal_id = save_signal(conn, signal)
                    signal.id = signal_id
                    result["new_signals"].append({
                        "asset": asset,
                        "candle_date": signal.candle_date,
                    })
                except Exception as e:
                    result["errors"].append(f"save_signal {asset}: {e}")
                    assets_result[asset]["status"] = "error"
                    assets_result[asset]["reason"] = f"save_signal: {str(e)[:60]}"
                    _log_scan(asset, "error", signal=True, candles=n_candles, reason=str(e))
                    continue

                # No obrir si ja hi ha un trade pendent per aquest asset
                if asset in pending_by_asset:
                    continue

                # Buscar la candle T+1 (entry)
                entry_candle = self._find_next_candle(candles, signal.candle_date)
                if entry_candle is None:
                    # No tenim T+1 encara → crear trade pending_entry
                    entry_candle = {
                        "date": self._today(),
                        "open": candles[-1]["close"],  # estimació
                        "high": candles[-1]["close"],
                        "low": candles[-1]["close"],
                        "close": candles[-1]["close"],
                    }

                try:
                    trade = self.executor.open_trade(signal, state.capital, entry_candle)
                    trade_id = save_trade(conn, trade)
                    trade.id = trade_id
                    pending_by_asset[asset] = trade

                    state.open_trade_count += 1
                    save_state(conn, state)
                except Exception as e:
                    result["errors"].append(f"open_trade {asset}: {e}")
                    assets_result[asset]["status"] = "error"
                    assets_result[asset]["reason"] = f"open_trade: {str(e)[:60]}"
                    _log_scan(asset, "error", signal=True, candles=n_candles, reason=str(e))

            # Completar assets_result per assets sense candles (no processats)
            for asset in self.assets:
                if asset not in assets_result:
                    candles = candles_by_asset.get(asset, [])
                    n = len(candles)
                    assets_result[asset] = {
                        "status": "ok" if n >= self.strategy.bb_period else "warning",
                        "signal": False,
                        "candles": n,
                        "reason": None if n >= self.strategy.bb_period else "insufficient_candles",
                    }

            # Determinar status global
            has_error = any(a.get("status") == "error" for a in assets_result.values())
            has_warning = any(a.get("status") == "warning" for a in assets_result.values())
            run_status = "error" if has_error else ("warning" if has_warning else "ok")

            # Persistir resultat de scan
            scan_result = {
                "run_utc": datetime.now(timezone.utc).isoformat(),
                "status": run_status,
                "assets": assets_result,
                "new_signals": len(result["new_signals"]),
                "settled_count": len(result["settled_trades"]),
                "pending_count": len(pending_by_asset),
                "errors": result["errors"],
            }
            save_scan_result(conn, scan_result)

            # Actualitzar last_scan_utc
            state = get_state(conn)
            state.last_scan_utc = scan_result["run_utc"]
            save_state(conn, state)

            # Trades que continuen pendents
            for asset in pending_by_asset:
                if asset not in [t["asset"] for t in result["settled_trades"]]:
                    if asset not in result["pending_trades"]:
                        result["pending_trades"].append(asset)

            # Log settlement
            pnl_this_run = sum(
                (t.get("pnl") or 0) for t in result["settled_trades"] if t.get("pnl") is not None
            )
            _log_settlement(
                trades_open=len(pending_by_asset),
                trades_settled=len(result["settled_trades"]),
                pnl_total=pnl_this_run,
            )

        finally:
            conn.close()

        return result

    def _find_next_candle(self, candles: list, signal_date: str) -> Optional[dict]:
        """Trobar la candle immediatament posterior a signal_date."""
        for i, c in enumerate(candles):
            if str(c["date"]) == signal_date and i + 1 < len(candles):
                return candles[i + 1]
        return None
