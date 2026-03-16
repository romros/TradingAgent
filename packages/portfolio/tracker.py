import sqlite3
from datetime import datetime, timezone

from packages.shared.models import AgentState, PaperTradeRecord
from packages.portfolio.db import init_db, get_state, save_state


class PortfolioTracker:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return init_db(self.db_path)

    def get_state(self) -> AgentState:
        conn = self._conn()
        try:
            return get_state(conn)
        finally:
            conn.close()

    def update_after_settlement(self, trade: PaperTradeRecord) -> AgentState:
        """
        Actualitza capital, total_pnl, consecutive_losses i settled_count
        a partir del trade liquidat.
        """
        conn = self._conn()
        try:
            state = get_state(conn)

            if trade.pnl is not None:
                state.capital += trade.pnl
                state.total_pnl += trade.pnl

                if trade.pnl < 0:
                    state.consecutive_losses += 1
                else:
                    state.consecutive_losses = 0

            state.settled_count += 1
            state.open_trade_count = max(0, state.open_trade_count - 1)
            state.last_scan_utc = datetime.now(timezone.utc).isoformat()

            save_state(conn, state)
            return state
        finally:
            conn.close()
