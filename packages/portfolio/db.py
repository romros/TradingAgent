import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional

from packages.shared.models import SignalRecord, PaperTradeRecord, AgentState
from packages.portfolio.costs import analyse_trade, summarise_trades


_CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    candle_date TEXT NOT NULL,
    asset TEXT NOT NULL,
    strategy TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'long',
    body_pct REAL,
    bb_lower REAL,
    close_price REAL,
    mode TEXT DEFAULT 'paper',
    UNIQUE(candle_date, asset)
)
"""

_CREATE_PAPER_TRADES = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER,
    asset TEXT NOT NULL,
    strategy TEXT NOT NULL,
    status TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    entry_date TEXT,
    exit_date TEXT,
    entry_price REAL,
    exit_price REAL,
    collateral REAL,
    leverage INTEGER,
    nominal REAL,
    fee REAL,
    pnl REAL,
    pnl_pct REAL,
    liq_triggered INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_AGENT_STATE = """
CREATE TABLE IF NOT EXISTS agent_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_SCAN_RUNS = """
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_utc TEXT NOT NULL,
    value_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_CREATE_VALIDATION_RUNS = """
CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_utc TEXT NOT NULL,
    value_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def init_db(db_path: str) -> sqlite3.Connection:
    import os
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(_CREATE_SIGNALS)
    cur.execute(_CREATE_PAPER_TRADES)
    cur.execute(_CREATE_AGENT_STATE)
    cur.execute(_CREATE_SCAN_RUNS)
    cur.execute(_CREATE_VALIDATION_RUNS)
    conn.commit()
    return conn


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_signal(conn: sqlite3.Connection, signal: SignalRecord) -> int:
    now = _now_utc()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO signals (created_at, candle_date, asset, strategy, direction,
            body_pct, bb_lower, close_price, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now,
            signal.candle_date,
            signal.asset,
            signal.strategy,
            signal.direction,
            signal.body_pct,
            signal.bb_lower,
            signal.close_price,
            signal.mode,
        ),
    )
    conn.commit()
    return cur.lastrowid


def signal_exists(conn: sqlite3.Connection, candle_date: str, asset: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM signals WHERE candle_date=? AND asset=?",
        (candle_date, asset),
    )
    return cur.fetchone() is not None


def save_trade(conn: sqlite3.Connection, trade: PaperTradeRecord) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO paper_trades (
            signal_id, asset, strategy, status, signal_date,
            entry_date, exit_date, entry_price, exit_price,
            collateral, leverage, nominal, fee, pnl, pnl_pct,
            liq_triggered, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            trade.signal_id,
            trade.asset,
            trade.strategy,
            trade.status,
            trade.signal_date,
            trade.entry_date,
            trade.exit_date,
            trade.entry_price,
            trade.exit_price,
            trade.collateral,
            trade.leverage,
            trade.nominal,
            trade.fee,
            trade.pnl,
            trade.pnl_pct,
            1 if trade.liq_triggered else 0,
            trade.created_at,
            trade.updated_at,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_trade(conn: sqlite3.Connection, trade: PaperTradeRecord) -> None:
    now = _now_utc()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE paper_trades SET
            status=?, entry_date=?, exit_date=?, entry_price=?, exit_price=?,
            collateral=?, leverage=?, nominal=?, fee=?, pnl=?, pnl_pct=?,
            liq_triggered=?, updated_at=?
        WHERE id=?
        """,
        (
            trade.status,
            trade.entry_date,
            trade.exit_date,
            trade.entry_price,
            trade.exit_price,
            trade.collateral,
            trade.leverage,
            trade.nominal,
            trade.fee,
            trade.pnl,
            trade.pnl_pct,
            1 if trade.liq_triggered else 0,
            now,
            trade.id,
        ),
    )
    conn.commit()


def _row_to_trade(row) -> PaperTradeRecord:
    return PaperTradeRecord(
        id=row["id"],
        signal_id=row["signal_id"],
        asset=row["asset"],
        strategy=row["strategy"],
        status=row["status"],
        signal_date=row["signal_date"],
        entry_date=row["entry_date"],
        exit_date=row["exit_date"],
        entry_price=row["entry_price"],
        exit_price=row["exit_price"],
        collateral=row["collateral"],
        leverage=row["leverage"],
        nominal=row["nominal"],
        fee=row["fee"],
        pnl=row["pnl"],
        pnl_pct=row["pnl_pct"],
        liq_triggered=bool(row["liq_triggered"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_pending_trades(conn: sqlite3.Connection) -> list:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM paper_trades WHERE status IN ('pending_entry','pending_settlement')"
    )
    return [_row_to_trade(r) for r in cur.fetchall()]


def get_all_signals(conn: sqlite3.Connection, asset: Optional[str] = None, limit: int = 100) -> list:
    cur = conn.cursor()
    if asset:
        cur.execute(
            "SELECT * FROM signals WHERE asset=? ORDER BY id DESC LIMIT ?",
            (asset, limit),
        )
    else:
        cur.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in cur.fetchall()]


def get_all_trades(conn: sqlite3.Connection, status: Optional[str] = None, limit: int = 100) -> list:
    cur = conn.cursor()
    if status:
        cur.execute(
            "SELECT * FROM paper_trades WHERE status=? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        cur.execute("SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,))
    trades = [dict(r) for r in cur.fetchall()]
    for trade in trades:
        if trade.get("pnl") is not None:
            trade["cost_analysis"] = analyse_trade(trade)
    return trades


def get_state(conn: sqlite3.Connection) -> AgentState:
    cur = conn.cursor()
    cur.execute("SELECT key, value_json FROM agent_state")
    rows = {r["key"]: json.loads(r["value_json"]) for r in cur.fetchall()}
    state = AgentState()
    if "runtime_state" in rows:
        d = rows["runtime_state"]
        state.mode = d.get("mode", state.mode)
        state.last_scan_utc = d.get("last_scan_utc", state.last_scan_utc)
        state.open_trade_count = d.get("open_trade_count", state.open_trade_count)
        state.settled_count = d.get("settled_count", state.settled_count)
        state.total_pnl = d.get("total_pnl", state.total_pnl)
        state.capital = d.get("capital", state.capital)
        state.consecutive_losses = d.get("consecutive_losses", state.consecutive_losses)
    return state


def save_state(conn: sqlite3.Connection, state: AgentState) -> None:
    now = _now_utc()
    value = json.dumps({
        "mode": state.mode,
        "last_scan_utc": state.last_scan_utc,
        "open_trade_count": state.open_trade_count,
        "settled_count": state.settled_count,
        "total_pnl": state.total_pnl,
        "capital": state.capital,
        "consecutive_losses": state.consecutive_losses,
    })
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO agent_state (key, value_json, updated_at) VALUES (?,?,?)",
        ("runtime_state", value, now),
    )
    conn.commit()


def save_scan_result(conn: sqlite3.Connection, result: dict) -> None:
    """Persisteix el resultat de l'últim scan (agent_state key last_scan_result)."""
    now = _now_utc()
    value = json.dumps(result)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO agent_state (key, value_json, updated_at) VALUES (?,?,?)",
        ("last_scan_result", value, now),
    )
    conn.commit()


def get_last_scan_result(conn: sqlite3.Connection) -> Optional[dict]:
    """Retorna l'últim resultat de scan o None si no n'hi ha."""
    cur = conn.cursor()
    cur.execute("SELECT value_json FROM agent_state WHERE key=?", ("last_scan_result",))
    row = cur.fetchone()
    if row is None:
        return None
    return json.loads(row["value_json"])


def save_scan_run(conn: sqlite3.Connection, result: dict) -> int:
    """Persisteix un scan run a l'historial. Retorna id."""
    now = _now_utc()
    new_signals = result.get("new_signals", [])
    signals_count = len(new_signals) if isinstance(new_signals, list) else 0
    value = json.dumps({
        "run_utc": result.get("run_utc", now),
        "assets": result.get("assets", {}),
        "signals_count": signals_count,
        "status": result.get("status", "ok"),
    })
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO scan_runs (run_utc, value_json, created_at) VALUES (?,?,?)",
        (result.get("run_utc", now), value, now),
    )
    conn.commit()
    return cur.lastrowid


def save_validation_run(conn: sqlite3.Connection, result: dict) -> int:
    """Persisteix una validació a l'historial. Retorna id."""
    now = _now_utc()
    paper = result.get("paper_metrics", {})
    validation = result.get("validation", {})
    value = json.dumps({
        "run_utc": now,
        "trades_total": paper.get("trades_total", 0),
        "winrate": paper.get("winrate_pct"),
        "ev": paper.get("avg_pnl_per_trade"),
        "status": validation.get("status", "aligned"),
    })
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO validation_runs (run_utc, value_json, created_at) VALUES (?,?,?)",
        (now, value, now),
    )
    conn.commit()
    return cur.lastrowid


def get_scan_runs(conn: sqlite3.Connection, limit: int = 100) -> list:
    """Retorna l'historial de scans, més recents primer."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, run_utc, value_json, created_at FROM scan_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    return [{"id": r["id"], "run_utc": r["run_utc"], **json.loads(r["value_json"])} for r in rows]


def get_validation_runs(conn: sqlite3.Connection, limit: int = 100) -> list:
    """Retorna l'historial de validacions, més recents primer."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, run_utc, value_json, created_at FROM validation_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    return [{"id": r["id"], "run_utc": r["run_utc"], **json.loads(r["value_json"])} for r in rows]


def get_settled_trades_ordered(conn: sqlite3.Connection) -> list:
    """Trades settled cronològics, revalorats amb el cost base canònic."""
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM paper_trades
           WHERE status IN ('settled','liq_settled') AND pnl IS NOT NULL
           ORDER BY id ASC"""
    )
    result = []
    for row in cur.fetchall():
        trade = dict(row)
        analysis = analyse_trade(trade)
        result.append({"id": trade["id"], "pnl": analysis["scenarios"]["base"]["pnl"],
                       "recorded_pnl": trade["pnl"], "updated_at": trade["updated_at"]})
    return result


def get_equity_curve(conn: sqlite3.Connection, capital_initial: float = 250.0) -> list:
    """
    Equity curve: [{trade_id, equity, pnl, updated_at}, ...]
    equity[n] = equity[n-1] + pnl_trade, equity[0] = capital_initial
    """
    trades = get_settled_trades_ordered(conn)
    curve = []
    equity = capital_initial
    for t in trades:
        pnl = float(t["pnl"]) if t["pnl"] is not None else 0.0
        equity += pnl
        curve.append({
            "trade_id": t["id"],
            "equity": round(equity, 2),
            "pnl": pnl,
            "updated_at": t["updated_at"],
        })
    return curve


def get_drawdown(conn: sqlite3.Connection, capital_initial: float = 250.0) -> dict:
    """
    Drawdown bàsic. max_drawdown_pct = (equity - peak) / peak * 100.
    Retorna max_drawdown_pct i peak_equity.
    """
    curve = get_equity_curve(conn, capital_initial)
    if not curve:
        return {"max_drawdown_pct": 0.0, "peak_equity": capital_initial, "equity_curve": []}
    peak = capital_initial
    max_dd_pct = 0.0
    for pt in curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        if peak > 0:
            dd_pct = (peak - eq) / peak * 100
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
    return {
        "max_drawdown_pct": round(max_dd_pct, 2),
        "peak_equity": peak,
        "equity_curve": curve,
    }


def get_trade_summary(conn: sqlite3.Connection) -> dict:
    """Resum canònic revalorat, preservant totals enregistrats per auditoria."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as n FROM paper_trades WHERE status IN ('pending_entry','pending_settlement')"
    )
    open_count = cur.fetchone()["n"]

    cur.execute("""SELECT * FROM paper_trades
                   WHERE status IN ('settled','liq_settled') AND pnl IS NOT NULL
                   ORDER BY id ASC""")
    settled = [dict(row) for row in cur.fetchall()]
    cost_summary = summarise_trades(settled)
    base = cost_summary["scenarios"]["base"]

    cur.execute("SELECT * FROM paper_trades ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    last_trade = {k: row[k] for k in row.keys()} if row else None
    if last_trade and last_trade.get("pnl") is not None:
        last_trade["cost_analysis"] = analyse_trade(last_trade)

    return {
        "open_count": open_count,
        "settled_count": len(settled),
        "wins": base["wins"],
        "losses": base["losses"],
        "pnl_total": round(base["pnl_total"], 2),
        "avg_pnl_per_trade": round(base["avg_pnl_per_trade"], 2) if settled else None,
        "gross_pnl_total": round(cost_summary["gross_pnl_total"], 2),
        "recorded_pnl_total": round(cost_summary["recorded_pnl_total"], 2),
        "recorded_fee_total": round(cost_summary["recorded_fee_total"], 2),
        "cost_model": cost_summary["model"],
        "cost_scenarios": {
            name: {key: round(value, 2) if isinstance(value, float) else value
                   for key, value in values.items()}
            for name, values in cost_summary["scenarios"].items()
        },
        "last_trade": last_trade,
    }


def reconcile_runtime_state(conn: sqlite3.Connection, capital_initial: float = 250.0) -> AgentState:
    """Revalora l'estat agregat sense modificar cap fila de paper_trades."""
    state = get_state(conn)
    summary = get_trade_summary(conn)
    state.total_pnl = summary["pnl_total"]
    state.capital = round(capital_initial + state.total_pnl, 2)
    state.settled_count = summary["settled_count"]
    state.open_trade_count = summary["open_count"]
    pnls = [trade["pnl"] for trade in get_settled_trades_ordered(conn)]
    consecutive_losses = 0
    for pnl in reversed(pnls):
        if pnl > 0:
            break
        consecutive_losses += 1
    state.consecutive_losses = consecutive_losses
    save_state(conn, state)
    return state
