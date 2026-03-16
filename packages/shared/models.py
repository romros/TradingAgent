from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SignalRecord:
    candle_date: str
    asset: str
    strategy: str
    direction: str = "long"
    body_pct: Optional[float] = None
    bb_lower: Optional[float] = None
    close_price: Optional[float] = None
    mode: str = "paper"
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class PaperTradeRecord:
    signal_id: Optional[int]
    asset: str
    strategy: str
    status: str  # pending_entry / pending_settlement / settled / liq_settled
    signal_date: str
    collateral: float
    leverage: int
    nominal: float
    fee: float
    created_at: str
    updated_at: str
    id: Optional[int] = None
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    liq_triggered: bool = False


@dataclass
class AgentState:
    mode: str = "paper"
    last_scan_utc: Optional[str] = None
    open_trade_count: int = 0
    settled_count: int = 0
    total_pnl: float = 0.0
    capital: float = 250.0
    consecutive_losses: int = 0
