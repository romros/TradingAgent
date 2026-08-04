from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from packages.strategy.msft_close_drift import MsftCloseDriftStrategy


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CloseHoldProbeConfig:
    db_path: str = "data/msft_close_drift_probe.db"
    capital_initial: float = 200.0
    leverage: int = 4
    risk_per_trade_pct: float = 0.01
    sizing_adverse_move_pct: float = 0.1906644080557125
    fee_roundtrip_bps: float = 36.0
    maximum_margin_pct: float = 0.35


class CloseHoldPaperProbe:
    """Isolated close-to-close paper ledger; never sends broker orders."""

    def __init__(self, strategy: MsftCloseDriftStrategy, config: CloseHoldProbeConfig):
        self.strategy = strategy
        self.config = config
        if config.leverage < 1 or not 0 < config.risk_per_trade_pct <= 1:
            raise ValueError("INVALID_RISK_CONFIG")
        if not 0 < config.sizing_adverse_move_pct < 1:
            raise ValueError("INVALID_SIZING_ADVERSE_MOVE")

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.config.db_path); path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS probe_state (
                key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL, asset TEXT NOT NULL, signal_date TEXT NOT NULL,
                entry_date TEXT NOT NULL, entry_close REAL NOT NULL,
                roc REAL NOT NULL, sma REAL NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(strategy, asset, signal_date)
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER NOT NULL,
                strategy TEXT NOT NULL, asset TEXT NOT NULL, status TEXT NOT NULL,
                entry_date TEXT NOT NULL, exit_date TEXT, entry_price REAL NOT NULL,
                exit_price REAL, holding_days INTEGER NOT NULL, collateral REAL NOT NULL,
                leverage INTEGER NOT NULL, nominal REAL NOT NULL, fee REAL NOT NULL,
                pnl REAL, pnl_pct REAL, liq_triggered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_utc TEXT NOT NULL,
                status TEXT NOT NULL, latest_session TEXT, complete_sessions INTEGER NOT NULL,
                value_json TEXT NOT NULL
            );
        """)
        conn.commit(); return conn

    def _state(self, conn: sqlite3.Connection) -> dict:
        row = conn.execute("SELECT value_json FROM probe_state WHERE key='runtime'").fetchone()
        if row:
            return json.loads(row[0])
        return {"capital": self.config.capital_initial, "total_pnl": 0.0,
                "settled_count": 0, "open_trade_count": 0,
                "mode": "paper", "status": "WARMING_UP", "last_session": None}

    def _save_state(self, conn: sqlite3.Connection, state: dict) -> None:
        conn.execute("INSERT OR REPLACE INTO probe_state VALUES ('runtime', ?, ?)",
                     (json.dumps(state, sort_keys=True), _utc_now()))

    def _record_run(self, conn: sqlite3.Connection, result: dict) -> None:
        conn.execute(
            "INSERT INTO scan_runs(run_utc,status,latest_session,complete_sessions,value_json) VALUES(?,?,?,?,?)",
            (_utc_now(), result["status"], result.get("latest_session"),
             result["complete_sessions"], json.dumps(result, sort_keys=True)),
        )

    def _settle_if_due(self, conn: sqlite3.Connection, candles: list[dict], state: dict) -> dict | None:
        trade = conn.execute("SELECT * FROM trades WHERE status='open' ORDER BY id LIMIT 1").fetchone()
        if trade is None:
            return None
        dates = [str(candle["date"]) for candle in candles]
        if trade["entry_date"] not in dates:
            raise ValueError("OPEN_TRADE_ENTRY_SESSION_MISSING")
        entry_index = dates.index(trade["entry_date"]); exit_index = entry_index + trade["holding_days"]
        if exit_index >= len(candles):
            return None
        held = candles[entry_index + 1:exit_index + 1]
        minimum_low = min(float(candle["low"]) for candle in held)
        adverse = max(0.0, 1 - minimum_low / trade["entry_price"])
        liquidated = adverse >= 1 / trade["leverage"]
        exit_candle = candles[exit_index]
        if liquidated:
            exit_price = trade["entry_price"] * (1 - 1 / trade["leverage"])
            pnl = -trade["collateral"] - trade["fee"]
            status = "liq_settled"
        else:
            exit_price = float(exit_candle["close"])
            pnl = trade["nominal"] * (exit_price / trade["entry_price"] - 1) - trade["fee"]
            status = "settled"
        pnl_pct = pnl / trade["collateral"] * 100
        conn.execute("""UPDATE trades SET status=?,exit_date=?,exit_price=?,pnl=?,pnl_pct=?,
                     liq_triggered=?,updated_at=? WHERE id=?""",
                     (status, str(exit_candle["date"]), exit_price, pnl, pnl_pct,
                      int(liquidated), _utc_now(), trade["id"]))
        state["capital"] += pnl; state["total_pnl"] += pnl
        state["settled_count"] += 1; state["open_trade_count"] = 0
        return {"trade_id": trade["id"], "status": status,
                "exit_date": str(exit_candle["date"]), "pnl": pnl, "adverse_move": adverse}

    def _open(self, conn: sqlite3.Connection, signal, latest: dict, state: dict) -> dict | None:
        try:
            cursor = conn.execute(
                "INSERT INTO signals(strategy,asset,signal_date,entry_date,entry_close,roc,sma,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (signal.strategy, signal.asset, signal.candle_date, str(latest["date"]),
                 float(latest["close"]), float(signal.body_pct), float(signal.bb_lower), _utc_now()),
            )
        except sqlite3.IntegrityError:
            return None
        capital = float(state["capital"])
        risk_nominal = capital * self.config.risk_per_trade_pct / self.config.sizing_adverse_move_pct
        margin_cap_nominal = capital * self.config.maximum_margin_pct * self.config.leverage
        nominal = min(risk_nominal, margin_cap_nominal)
        collateral = nominal / self.config.leverage
        fee = nominal * self.config.fee_roundtrip_bps / 10_000
        now = _utc_now()
        trade_cursor = conn.execute(
            """INSERT INTO trades(signal_id,strategy,asset,status,entry_date,entry_price,
               holding_days,collateral,leverage,nominal,fee,created_at,updated_at)
               VALUES(?,?,?,'open',?,?,?,?,?,?,?,?,?)""",
            (cursor.lastrowid, signal.strategy, signal.asset, str(latest["date"]),
             float(latest["close"]), self.strategy.holding_days, collateral,
             self.config.leverage, nominal, fee, now, now),
        )
        state["open_trade_count"] = 1
        return {"trade_id": trade_cursor.lastrowid, "entry_date": str(latest["date"]),
                "entry_price": float(latest["close"]), "nominal": nominal,
                "collateral": collateral, "leverage": self.config.leverage, "fee": fee}

    def run(self, candles: list[dict]) -> dict:
        conn = self._connect(); state = self._state(conn)
        latest = str(candles[-1]["date"]) if candles else None
        result = {"strategy": self.strategy.STRATEGY_NAME,
                  "complete_sessions": len(candles), "required_sessions": self.strategy.minimum_candles,
                  "latest_session": latest, "status": "WARMING_UP", "opened": None,
                  "settled": None, "capital": state["capital"]}
        try:
            if len(candles) < self.strategy.minimum_candles:
                state["status"] = "WARMING_UP"
            elif state.get("last_session") == latest:
                result["status"] = state.get("status", "READY")
                result["reason"] = "SESSION_ALREADY_PROCESSED"
            else:
                state["status"] = result["status"] = "READY"
                result["settled"] = self._settle_if_due(conn, candles, state)
                open_trade = conn.execute("SELECT 1 FROM trades WHERE status='open'").fetchone()
                if result["settled"] is None and open_trade is None:
                    signal = self.strategy.detect(candles, asset="MSFT", mode="paper")
                    if signal:
                        result["opened"] = self._open(conn, signal, candles[-1], state)
                state["last_session"] = latest
            result["capital"] = state["capital"]
            self._save_state(conn, state); self._record_run(conn, result); conn.commit()
            return result
        finally:
            conn.close()
