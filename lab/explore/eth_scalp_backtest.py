"""
eth_scalp_backtest.py — Backtest realista de la funció entry() Capitulation Scalp 1H

Simulació candle a candle:
  - Multi-asset: ETH, BTC, SOL (+ XAU si dades disponibles)
  - Capital real amb compounding
  - Sizing: col = 20% capital (min 15$, max 60$), leverage 100x (crypto) / 50x (XAU)
  - Fee real per trade
  - Walk-forward: recomputa indicadors cada candle
  - Filtre horari integrat (no operar 16-19 UTC)
  - Circuit breakers actius
  - Màx 1 posició simultània per asset (no overlap)
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ── Config ────────────────────────────────────────────────────────────────────

ASSETS = {
    "ETH": {"symbol": "ETHUSDT", "body_th": -0.03, "drop_th": -0.05, "fee": 3.36, "lev": 100},
    "BTC": {"symbol": "BTCUSDT", "body_th": -0.03, "drop_th": -0.05, "fee": 3.36, "lev": 100},
    "SOL": {"symbol": "SOLUSDT", "body_th": -0.03, "drop_th": -0.05, "fee": 3.36, "lev": 100},
}

CAPITAL_INIT = 250.0
COL_PCT = 0.20
COL_MIN = 15.0
COL_MAX = 60.0
BAD_HOURS = {16, 17, 18, 19}
MAX_VOL_REL = 5.0

# Circuit breakers
CB_CONSECUTIVE_LOSSES = 3
CB_PAUSE_CANDLES = 48  # 48h pause = 48 candles 1H

# Walk-forward: no hi ha res a "entrenar" — els indicadors (BB, RSI) son rolling.
# Simplement iterem candle a candle cronològicament.


# ── Download ──────────────────────────────────────────────────────────────────

def download_binance(symbol):
    all_k = []
    start_ms = 0
    while True:
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
               f"&interval=1h&startTime={start_ms}&limit=1000")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if not data:
            break
        all_k.extend(data)
        start_ms = data[-1][0] + 1
        if len(data) < 1000:
            break
        time.sleep(0.1)
    rows = []
    for k in all_k:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
        rows.append({"ts": ts, "O": float(k[1]), "H": float(k[2]),
                     "L": float(k[3]), "C": float(k[4]), "V": float(k[5])})
    return pd.DataFrame(rows).set_index("ts")


# ── Indicadors rolling ────────────────────────────────────────────────────────

class Indicators:
    """Calcula indicadors de forma incremental per cada candle nova."""

    def __init__(self):
        self.closes = []
        self.volumes = []
        self.rsi7_avg_gain = 0.0
        self.rsi7_avg_loss = 0.0
        self.rsi7_initialized = False
        self.rsi7_value = 50.0

    def update(self, close, volume):
        self.closes.append(close)
        self.volumes.append(volume)
        n = len(self.closes)

        # RSI(7) Wilder incremental
        if n >= 2:
            delta = self.closes[-1] - self.closes[-2]
            gain = max(delta, 0)
            loss = max(-delta, 0)

            if not self.rsi7_initialized and n >= 8:
                # Primera inicialització
                deltas = [self.closes[i] - self.closes[i - 1] for i in range(1, 8)]
                self.rsi7_avg_gain = sum(max(d, 0) for d in deltas) / 7
                self.rsi7_avg_loss = sum(max(-d, 0) for d in deltas) / 7
                self.rsi7_initialized = True
            elif self.rsi7_initialized:
                self.rsi7_avg_gain = (self.rsi7_avg_gain * 6 + gain) / 7
                self.rsi7_avg_loss = (self.rsi7_avg_loss * 6 + loss) / 7

            if self.rsi7_initialized:
                if self.rsi7_avg_loss == 0:
                    self.rsi7_value = 100.0
                else:
                    rs = self.rsi7_avg_gain / self.rsi7_avg_loss
                    self.rsi7_value = 100.0 - 100.0 / (1.0 + rs)

    @property
    def bb_lower(self):
        if len(self.closes) < 20:
            return None
        w = self.closes[-20:]
        m = np.mean(w)
        s = np.std(w, ddof=0)
        return m - 2 * s

    @property
    def drop3h(self):
        if len(self.closes) < 4:
            return 0
        return (self.closes[-1] - self.closes[-4]) / self.closes[-4]

    @property
    def vol_rel(self):
        if len(self.volumes) < 20:
            return 1.0
        ma = np.mean(self.volumes[-20:])
        return self.volumes[-1] / ma if ma > 0 else 1.0

    @property
    def rsi7(self):
        return self.rsi7_value


# ── Entry function ────────────────────────────────────────────────────────────

def entry(body_pct, bb_lo, close, drop3h, rsi7, vol_rel, hour, body_th, drop_th):
    if body_pct >= body_th:
        return None
    if bb_lo is None or close >= bb_lo:
        return None
    if drop3h >= drop_th:
        return None
    if hour in BAD_HOURS:
        return None
    if vol_rel > MAX_VOL_REL:
        return None

    score = 0
    if body_pct < body_th * 2.5:
        score += 2
    elif body_pct < body_th * 1.5:
        score += 1
    if drop3h < drop_th * 2.5:
        score += 2
    elif drop3h < drop_th * 1.5:
        score += 1
    if rsi7 < 15:
        score += 2
    elif rsi7 < 25:
        score += 1
    if vol_rel > 3:
        score += 1
    if hour in (20, 21):
        score += 1

    if score >= 5:
        return ("LONG", score, 0.0524, 0.0427)
    elif score >= 3:
        return ("LONG", score, 0.0288, 0.0221)
    else:
        return ("LONG", score, 0.0235, 0.0232)


# ── Backtest engine ───────────────────────────────────────────────────────────

@dataclass
class Trade:
    asset: str
    ts_signal: pd.Timestamp
    ts_entry: pd.Timestamp
    score: int
    tier: str
    entry_price: float
    exit_price: float
    collateral: float
    nominal: float
    fee: float
    move_pct: float
    pnl: float
    capital_before: float
    capital_after: float
    is_win: bool
    mae: float
    mfe: float


def run_backtest(all_data: dict, start_date: str = "2018-01-01"):
    """
    Backtest candle a candle, multi-asset, capital real.

    all_data: {asset_name: DataFrame amb OHLCV 1H}
    """
    start_ts = pd.Timestamp(start_date, tz=timezone.utc)
    capital = CAPITAL_INIT
    trades = []
    equity_curve = []

    # State per asset
    indicators = {name: Indicators() for name in all_data}
    in_position = {name: False for name in all_data}  # no overlap

    # Circuit breaker
    consecutive_losses = 0
    pause_until_candle = 0
    candle_count = 0

    # Unificar timestamps
    all_ts = set()
    for name, df in all_data.items():
        all_ts.update(df.index)
    all_ts = sorted(all_ts)

    for ts in all_ts:
        candle_count += 1

        # Actualitzar indicadors per cada asset
        for name, df in all_data.items():
            if ts not in df.index:
                continue
            row = df.loc[ts]
            indicators[name].update(row["C"], row["V"])

        # Buscar senyals si no estem en pausa
        if candle_count <= pause_until_candle:
            continue

        for name, df in all_data.items():
            if ts not in df.index:
                continue
            if in_position[name]:
                continue
            if ts < start_ts:
                continue

            row = df.loc[ts]
            o, h, l, c = row["O"], row["H"], row["L"], row["C"]
            if o <= 0:
                continue

            body_pct = (c - o) / o
            ind = indicators[name]
            cfg = ASSETS[name]

            result = entry(
                body_pct=body_pct,
                bb_lo=ind.bb_lower,
                close=c,
                drop3h=ind.drop3h,
                rsi7=ind.rsi7,
                vol_rel=ind.vol_rel,
                hour=ts.hour,
                body_th=cfg["body_th"],
                drop_th=cfg["drop_th"],
            )

            if result is None:
                continue

            direction, score, exp_mfe, exp_mae = result

            # Buscar la SEGUENT candle per executar
            idx = df.index.get_loc(ts)
            if idx + 1 >= len(df):
                continue

            next_ts = df.index[idx + 1]
            next_row = df.iloc[idx + 1]
            entry_price = next_row["O"]
            exit_price = next_row["C"]
            next_h = next_row["H"]
            next_l = next_row["L"]

            if entry_price <= 0:
                continue

            # Sizing
            col = min(max(capital * COL_PCT, COL_MIN), COL_MAX)
            if col > capital * 0.5:  # no arriscar mes de 50% capital
                col = max(capital * 0.5, COL_MIN)
            if capital < COL_MIN:
                continue  # no prou capital

            lev = cfg["lev"]
            nominal = col * lev
            fee = cfg["fee"]

            move = (exit_price - entry_price) / entry_price
            mae = (entry_price - next_l) / entry_price
            mfe = (next_h - entry_price) / entry_price
            pnl = nominal * move - fee

            is_win = pnl > 0
            capital_before = capital
            capital += pnl
            if capital < 0:
                capital = 0

            tier = "HIGH" if score >= 5 else ("MID" if score >= 3 else "LOW")

            trades.append(Trade(
                asset=name, ts_signal=ts, ts_entry=next_ts, score=score, tier=tier,
                entry_price=entry_price, exit_price=exit_price,
                collateral=col, nominal=nominal, fee=fee,
                move_pct=move, pnl=pnl,
                capital_before=capital_before, capital_after=capital,
                is_win=is_win, mae=mae, mfe=mfe,
            ))

            equity_curve.append({"ts": next_ts, "capital": capital, "asset": name})

            # Circuit breaker
            if is_win:
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                if consecutive_losses >= CB_CONSECUTIVE_LOSSES:
                    pause_until_candle = candle_count + CB_PAUSE_CANDLES
                    consecutive_losses = 0

    return trades, equity_curve


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(trades, equity_curve):
    if not trades:
        print("  0 trades")
        return

    tdf = pd.DataFrame([{
        "ts": t.ts_signal, "yr": t.ts_signal.year, "asset": t.asset,
        "score": t.score, "tier": t.tier,
        "col": t.collateral, "nom": t.nominal,
        "move": t.move_pct, "pnl": t.pnl,
        "cap_before": t.capital_before, "cap_after": t.capital_after,
        "win": t.is_win, "mae": t.mae, "mfe": t.mfe,
    } for t in trades])

    n = len(tdf)
    wr = 100 * tdf["win"].mean()
    w = tdf[tdf["pnl"] > 0]["pnl"]
    l = tdf[tdf["pnl"] <= 0]["pnl"]
    pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
    final_cap = trades[-1].capital_after

    print(f"\n{'=' * 100}")
    print(f"BACKTEST REALISTA — Capitulation Scalp 1H Multi-Asset")
    print(f"Capital inicial: {CAPITAL_INIT}$ | Sizing: {COL_PCT*100:.0f}% cap "
          f"(min {COL_MIN}$, max {COL_MAX}$)")
    print(f"{'=' * 100}")

    print(f"\n  RESUM GLOBAL:")
    print(f"    Trades:      {n}")
    print(f"    WR:          {wr:.1f}%")
    print(f"    PF:          {pf:.2f}")
    print(f"    Avg $/trade: {tdf['pnl'].mean():+.2f}$")
    print(f"    Total PnL:   {tdf['pnl'].sum():+.2f}$")
    print(f"    Capital:     {CAPITAL_INIT}$ -> {final_cap:.0f}$ "
          f"(x{final_cap/CAPITAL_INIT:.1f})")

    # Max drawdown
    eq = [CAPITAL_INIT] + [t.capital_after for t in trades]
    peak = eq[0]
    max_dd = 0
    max_dd_pct = 0
    for e in eq:
        if e > peak:
            peak = e
        dd = peak - e
        dd_pct = dd / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
    print(f"    Max DD:      {max_dd:.0f}$ ({max_dd_pct*100:.1f}%)")

    # Per asset
    print(f"\n  PER ASSET:")
    print(f"    {'Asset':<6} {'N':>4} {'WR':>5} {'Avg$':>7} {'Total$':>8}")
    print(f"    {'---' * 10}")
    for asset in sorted(tdf["asset"].unique()):
        adf = tdf[tdf["asset"] == asset]
        print(f"    {asset:<6} {len(adf):>4} {100*adf['win'].mean():>4.0f}% "
              f"{adf['pnl'].mean():>+6.1f}$ {adf['pnl'].sum():>+7.0f}$")

    # Per any
    print(f"\n  PER ANY:")
    print(f"    {'Any':>6} {'N':>4} {'WR':>5} {'Avg$':>7} {'Total$':>8} "
          f"{'Cap ini':>8} {'Cap fi':>8} {'DD max':>8}")
    print(f"    {'---' * 18}")

    for yr in sorted(tdf["yr"].unique()):
        ydf = tdf[tdf["yr"] == yr]
        cap_ini = ydf.iloc[0]["cap_before"]
        cap_fi = ydf.iloc[-1]["cap_after"]
        # DD dins l'any
        yr_eq = list(ydf["cap_after"])
        yr_peak = cap_ini
        yr_dd = 0
        for e in yr_eq:
            if e > yr_peak:
                yr_peak = e
            yr_dd = max(yr_dd, yr_peak - e)
        print(f"    {yr:>6} {len(ydf):>4} {100*ydf['win'].mean():>4.0f}% "
              f"{ydf['pnl'].mean():>+6.1f}$ {ydf['pnl'].sum():>+7.0f}$ "
              f"{cap_ini:>7.0f}$ {cap_fi:>7.0f}$ {yr_dd:>7.0f}$")

    # Per tier
    print(f"\n  PER TIER:")
    for tier in ["LOW", "MID", "HIGH"]:
        sub = tdf[tdf["tier"] == tier]
        if len(sub) == 0:
            continue
        print(f"    {tier:<6} N={len(sub):>3} WR={100*sub['win'].mean():>4.0f}% "
              f"avg={sub['pnl'].mean():>+6.1f}$ total={sub['pnl'].sum():>+7.0f}$")

    # Equity curve per semestre
    print(f"\n  EQUITY CURVE (per semestre):")
    edf = pd.DataFrame(equity_curve)
    edf["semester"] = edf["ts"].dt.year.astype(str) + "-" + np.where(edf["ts"].dt.month <= 6, "H1", "H2")
    for sem in sorted(edf["semester"].unique()):
        sdf = edf[edf["semester"] == sem]
        print(f"    {sem}: capital={sdf.iloc[-1]['capital']:>8.0f}$")

    # Distribució
    print(f"\n  DISTRIBUCIO PnL (amb sizing real):")
    print(f"    Avg win:   {w.mean():>+8.2f}$")
    print(f"    Avg loss:  {l.mean():>+8.2f}$")
    print(f"    W/L:       {abs(w.mean()/l.mean()):.2f}" if len(l) > 0 and l.mean() != 0 else "")
    print(f"    Best:      {tdf['pnl'].max():>+8.2f}$")
    print(f"    Worst:     {tdf['pnl'].min():>+8.2f}$")
    print(f"    Median:    {tdf['pnl'].median():>+8.2f}$")
    for p in [5, 25, 50, 75, 95]:
        print(f"    P{p}:       {np.percentile(tdf['pnl'], p):>+8.2f}$")

    # Últims 20 trades
    print(f"\n  ÚLTIMS 20 TRADES:")
    print(f"    {'Data':>16} {'Asset':<5} {'Sc':>2} {'Tier':<4} {'Col':>5} "
          f"{'Move':>7} {'PnL':>8} {'Cap':>8}")
    print(f"    {'---' * 18}")
    for t in trades[-20:]:
        print(f"    {t.ts_signal.strftime('%Y-%m-%d %H:%M'):>16} {t.asset:<5} "
              f"{t.score:>2} {t.tier:<4} {t.collateral:>4.0f}$ "
              f"{t.move_pct*100:>+6.2f}% {t.pnl:>+7.1f}$ {t.capital_after:>7.0f}$")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Download
    all_data = {}
    for name, cfg in ASSETS.items():
        print(f"Baixant {name} ({cfg['symbol']}) 1H...")
        df = download_binance(cfg["symbol"])
        print(f"  {len(df)} candles, {df.index[0].date()} -> {df.index[-1].date()}")
        all_data[name] = df

    # Backtest
    print("\nExecutant backtest...")
    trades, equity = run_backtest(all_data, start_date="2018-01-01")
    print_report(trades, equity)


if __name__ == "__main__":
    main()
