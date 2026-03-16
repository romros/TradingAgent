import sqlite3
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
        Retorna dict amb resum: new_signals, settled_trades, pending_trades, errors
        """
        conn = init_db(self.db_path)
        result = {
            "new_signals": [],
            "settled_trades": [],
            "pending_trades": [],
            "errors": [],
        }

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
                    result["errors"].append(f"fetch {asset}: {e}")
                    candles_by_asset[asset] = []

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
                candles = candles_by_asset.get(asset, [])
                if len(candles) < self.strategy.bb_period:
                    continue

                # Detectar senyal sobre la candle d'ahir (la més recent tancada)
                # Usem totes les candles però el senyal es basa en la última
                signal = self.strategy.detect(candles, asset=asset, mode=state.mode)

                if signal is None:
                    continue

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

            # Actualitzar last_scan_utc
            state = get_state(conn)
            state.last_scan_utc = datetime.now(timezone.utc).isoformat()
            save_state(conn, state)

            # Trades que continuen pendents
            for asset in pending_by_asset:
                if asset not in [t["asset"] for t in result["settled_trades"]]:
                    if asset not in result["pending_trades"]:
                        result["pending_trades"].append(asset)

        finally:
            conn.close()

        return result

    def _find_next_candle(self, candles: list, signal_date: str) -> Optional[dict]:
        """Trobar la candle immediatament posterior a signal_date."""
        for i, c in enumerate(candles):
            if str(c["date"]) == signal_date and i + 1 < len(candles):
                return candles[i + 1]
        return None
