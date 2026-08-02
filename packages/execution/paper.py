from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence

from packages.portfolio.risk_policy import CapitalRiskTier, risk_pct_for_capital
from packages.shared.models import SignalRecord, PaperTradeRecord


class PaperExecutor:
    def __init__(
        self,
        leverage: int,
        col_pct: float,
        col_max: float,
        col_min: float,
        fee: Optional[float] = None,
        fee_bps: float = 6.0,
        leverage_by_asset: Optional[Mapping[str, int]] = None,
        risk_per_trade_pct: Optional[float] = None,
        stop_distance_by_asset: Optional[Mapping[str, float]] = None,
        risk_glidepath: Optional[Sequence[CapitalRiskTier]] = None,
    ):
        self.leverage = leverage
        self.col_pct = col_pct
        self.col_max = col_max
        self.col_min = col_min
        self.fee = fee
        self.fee_bps = fee_bps
        self.leverage_by_asset = {asset.upper(): int(value)
                                  for asset, value in (leverage_by_asset or {}).items()}
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_distance_by_asset = {asset.upper(): float(value)
                                       for asset, value in (stop_distance_by_asset or {}).items()}
        self.risk_glidepath = tuple(risk_glidepath or ())

    def leverage_for_asset(self, asset: str) -> int:
        return self.leverage_by_asset.get(asset.upper(), self.leverage)

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

        leverage = self.leverage_for_asset(signal.asset)
        collateral = min(max(capital * self.col_pct, self.col_min), self.col_max)
        nominal = collateral * leverage
        stop_distance = self.stop_distance_by_asset.get(signal.asset.upper())
        if self.risk_per_trade_pct is not None and stop_distance is not None:
            risk_pct = risk_pct_for_capital(
                capital, self.risk_glidepath, self.risk_per_trade_pct
            ) if self.risk_glidepath else self.risk_per_trade_pct
            if not 0 < risk_pct <= 1 or not 0 < stop_distance < 1:
                raise ValueError("risk_per_trade_pct and stop distance must be in (0, 1]")
            risk_limited_nominal = capital * risk_pct / stop_distance
            nominal = min(nominal, risk_limited_nominal)
            collateral = nominal / leverage
        trade_fee = self.fee if self.fee is not None else nominal * self.fee_bps / 10_000.0
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
            leverage=leverage,
            nominal=nominal,
            fee=trade_fee,
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
        stop_distance = self.stop_distance_by_asset.get(trade.asset.upper())

        liq_triggered = mae >= liq_threshold

        if stop_distance is not None and mae >= stop_distance:
            pnl = -trade.nominal * stop_distance - trade.fee
            status = "stop_settled"
            exit_price = open_price * (1.0 - stop_distance)
            liq_triggered = False
        elif liq_triggered:
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
