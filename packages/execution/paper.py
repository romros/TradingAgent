from datetime import datetime, timezone
from typing import Optional

from packages.shared.models import SignalRecord, PaperTradeRecord


class PaperExecutor:
    def __init__(self, leverage: int, col_pct: float, col_max: float, col_min: float, fee: float):
        self.leverage = leverage
        self.col_pct = col_pct
        self.col_max = col_max
        self.col_min = col_min
        self.fee = fee

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def open_trade(
        self,
        signal: SignalRecord,
        capital: float,
        entry_candle: dict,
    ) -> PaperTradeRecord:
        """
        entry_candle: {date, open, high, low, close} — la candle T+1
        collateral = min(max(capital*col_pct, col_min), col_max)
        nominal = collateral * leverage
        Si entry_candle és d'avui i mercat no ha tancat: status='pending_settlement',
        entry_price=open
        """
        from datetime import date

        collateral = min(max(capital * self.col_pct, self.col_min), self.col_max)
        nominal = collateral * self.leverage
        now = self._now_utc()

        candle_date_str = str(entry_candle["date"])
        today_str = date.today().isoformat()

        # Si la candle és d'avui, el mercat pot no haver tancat → pending_settlement
        if candle_date_str >= today_str:
            status = "pending_settlement"
        else:
            # Candle d'ahir o anterior → ja tancada, pending_settlement igualment
            # fins que es faci el settle explícit
            status = "pending_settlement"

        entry_price = float(entry_candle["open"])

        return PaperTradeRecord(
            signal_id=signal.id,
            asset=signal.asset,
            strategy=signal.strategy,
            status=status,
            signal_date=signal.candle_date,
            entry_date=candle_date_str,
            exit_date=None,
            entry_price=entry_price,
            exit_price=None,
            collateral=collateral,
            leverage=self.leverage,
            nominal=nominal,
            fee=self.fee,
            pnl=None,
            pnl_pct=None,
            liq_triggered=False,
            created_at=now,
            updated_at=now,
        )

    def settle_trade(
        self,
        trade: PaperTradeRecord,
        settlement_candle: dict,
    ) -> PaperTradeRecord:
        """
        settlement_candle: {date, open, high, low, close} — la candle T+1 tancada
        MAE = (open - low) / open
        liq_triggered = MAE >= 1/leverage
        Si liq: pnl = -collateral - fee
        Sinó: pnl = nominal * (close - open) / open - fee
        pnl_pct = pnl / collateral * 100
        status = 'liq_settled' si liq, 'settled' sinó
        """
        open_price = float(settlement_candle["open"])
        low_price = float(settlement_candle["low"])
        close_price = float(settlement_candle["close"])

        liq_threshold = 1.0 / trade.leverage
        mae = (open_price - low_price) / open_price if open_price > 0 else 0.0

        liq_triggered = mae >= liq_threshold

        if liq_triggered:
            pnl = -trade.collateral - trade.fee
            status = "liq_settled"
            exit_price = open_price * (1.0 - liq_threshold)
        else:
            pnl = trade.nominal * (close_price - open_price) / open_price - trade.fee
            status = "settled"
            exit_price = close_price

        pnl_pct = pnl / trade.collateral * 100.0

        trade.status = status
        trade.exit_date = str(settlement_candle["date"])
        trade.entry_price = open_price
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.liq_triggered = liq_triggered
        trade.updated_at = self._now_utc()

        return trade
