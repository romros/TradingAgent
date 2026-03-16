"""
lab/setups/signal_generators.py — Generadors de senyals per T6

6 hipòtesis en 3 famílies:
  F1. Breakout post-compressió
    A) BB squeeze + breakout upper (vol comprimida → expansió)
    B) ATR low + big candle (vol baixa → impuls fort)
  F2. Sweep & reclaim
    A) Sweep low 4H + close recovery (false breakdown)
    B) Hammer a mínims (wick llarga inferior + close alt)
  F3. Trend pullback continuation
    A) Uptrend EMA + RSI dip (tendència + correcció → rebot)
    B) Pullback a EMA20 en tendència (retest de mitjana)

Totes generen list[TradeRecord] + all_candle_moves per MC random.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lab.harness.core import TradeRecord


# ══════════════════════════════════════════════════════════════
# INDICADORS COMUNS
# ══════════════════════════════════════════════════════════════

def _ema(c: np.ndarray, span: int) -> np.ndarray:
    e = np.zeros(len(c)); e[0] = c[0]; a = 2 / (span + 1)
    for i in range(1, len(c)):
        e[i] = a * c[i] + (1 - a) * e[i - 1]
    return e


def _bb(c: np.ndarray, p: int = 20, m: float = 2.0):
    n = len(c)
    lo = np.full(n, np.nan); hi = np.full(n, np.nan)
    width = np.full(n, np.nan)
    for i in range(p - 1, n):
        w = c[i - p + 1:i + 1]
        mu = np.mean(w); sd = np.std(w, ddof=0)
        lo[i] = mu - m * sd; hi[i] = mu + m * sd
        width[i] = (4 * m * sd) / mu * 100 if mu > 0 else 0  # % width
    return lo, hi, width


def _rsi(c: np.ndarray, p: int = 14) -> np.ndarray:
    n = len(c); r = np.full(n, np.nan); d = np.diff(c)
    g = np.where(d > 0, d, 0.0); lo = np.where(d < 0, -d, 0.0)
    if len(g) < p:
        return r
    ag = np.mean(g[:p]); al = np.mean(lo[:p])
    r[p] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    for i in range(p, len(d)):
        ag = (ag * (p - 1) + g[i]) / p; al = (al * (p - 1) + lo[i]) / p
        r[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    return r


def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, p: int = 14) -> np.ndarray:
    n = len(c); atr = np.full(n, np.nan)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    tr[0] = h[0] - l[0]
    if n > p:
        atr[p - 1] = np.mean(tr[:p])
        for i in range(p, n):
            atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
    return atr


def _rolling_low(l: np.ndarray, window: int) -> np.ndarray:
    n = len(l); rl = np.full(n, np.nan)
    for i in range(window, n):
        rl[i] = np.min(l[i - window:i])  # low dels anteriors (excloent actual)
    return rl


def _rolling_high(h: np.ndarray, window: int) -> np.ndarray:
    n = len(h); rh = np.full(n, np.nan)
    for i in range(window, n):
        rh[i] = np.max(h[i - window:i])
    return rh


def _make_trade(df, i, asset, score) -> TradeRecord:
    O = df["O"].values; H = df["H"].values; L = df["L"].values; C = df["C"].values
    o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
    move = (c1 - o1) / o1
    mae = (o1 - l1) / o1
    mfe = (h1 - o1) / o1
    return TradeRecord(
        ts=df.index[i].isoformat(), year=df.index[i].year,
        asset=asset, score=score, move=move, mae=mae, mfe=mfe, green=c1 > o1,
    )


def _all_moves(df) -> np.ndarray:
    O = df["O"].values; C = df["C"].values
    return np.array([(C[i + 1] - O[i + 1]) / O[i + 1] for i in range(200, len(df) - 1)])


# ══════════════════════════════════════════════════════════════
# F1A: BB Squeeze + Breakout Upper
# ══════════════════════════════════════════════════════════════

def f1a_bb_squeeze_breakout(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: quan BB width està al mínim (compressió), un close per sobre de BB upper
    indica expansió de volatilitat → continuació LONG.
    """
    C = df["C"].values; O = df["O"].values; N = len(df)
    _, bb_hi, bb_width = _bb(C, 20, 2.0)
    vol_ma = pd.Series(df["V"].values).rolling(20).mean().values
    vol_rel = df["V"].values / np.maximum(vol_ma, 1)

    # Percentil 20 de BB width (compressió)
    valid_widths = bb_width[~np.isnan(bb_width)]
    if len(valid_widths) < 100:
        return []
    squeeze_th = np.percentile(valid_widths, 25)

    trades = []
    for i in range(200, N - 1):
        if np.isnan(bb_width[i]) or np.isnan(bb_hi[i]):
            continue
        # Compressió recent (últimes 5 candles totes narrow)
        if any(np.isnan(bb_width[i - j]) or bb_width[i - j] > squeeze_th for j in range(5)):
            continue
        # Breakout: close > BB upper
        if C[i] <= bb_hi[i]:
            continue
        # Candle verda i decent
        body = (C[i] - O[i]) / O[i]
        if body < 0.005:
            continue
        # Score
        sc = 0
        if body > 0.02:
            sc += 2
        elif body > 0.01:
            sc += 1
        if vol_rel[i] > 2:
            sc += 1
        if vol_rel[i] > 3:
            sc += 1

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# F1B: ATR Low + Big Candle
# ══════════════════════════════════════════════════════════════

def f1b_atr_low_big_candle(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: ATR(14) al mínim (volatilitat comprimida) + candle 1H amb body > 2x ATR
    = impuls d'expansió → continuació LONG.
    """
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    N = len(df)
    atr14 = _atr(H, L, C, 14)
    atr_rel = np.full(N, np.nan)
    for i in range(100, N):
        window = atr14[i - 100:i]
        valid = window[~np.isnan(window)]
        if len(valid) > 20:
            atr_rel[i] = atr14[i] / np.mean(valid)

    trades = []
    for i in range(200, N - 1):
        if np.isnan(atr14[i]) or np.isnan(atr_rel[i]):
            continue
        # ATR baixa (per sota de la mitjana)
        if atr_rel[i] > 0.8:
            continue
        # Big candle: body > 2x ATR
        body_abs = abs(C[i] - O[i])
        if body_abs < 2 * atr14[i]:
            continue
        # LONG only: candle verda
        if C[i] <= O[i]:
            continue
        body_pct = (C[i] - O[i]) / O[i]
        sc = 0
        if body_pct > 0.03:
            sc += 2
        elif body_pct > 0.015:
            sc += 1
        if atr_rel[i] < 0.5:
            sc += 2
        elif atr_rel[i] < 0.7:
            sc += 1

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# F2A: Sweep Low + Close Recovery (False Breakdown)
# ══════════════════════════════════════════════════════════════

def f2a_sweep_reclaim(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: el low de la candle actual trenca per sota del mínim de les últimes 4 candles,
    però el close torna per sobre → false breakdown, smart money compra.
    """
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    N = len(df)
    rolling_low4 = _rolling_low(L, 4)

    trades = []
    for i in range(200, N - 1):
        if np.isnan(rolling_low4[i]):
            continue
        # Sweep: low actual < low de les últimes 4
        if L[i] >= rolling_low4[i]:
            continue
        # Reclaim: close torna per sobre del rolling low
        if C[i] <= rolling_low4[i]:
            continue
        # Idealment candle verda
        if C[i] <= O[i]:
            continue
        # Score
        sweep_depth = (rolling_low4[i] - L[i]) / rolling_low4[i]
        body_pct = (C[i] - O[i]) / O[i]
        sc = 0
        if sweep_depth > 0.02:
            sc += 2
        elif sweep_depth > 0.01:
            sc += 1
        if body_pct > 0.015:
            sc += 1
        if C[i] > O[i] and (C[i] - O[i]) > (O[i] - L[i]):
            sc += 1  # body > lower wick = força de recuperació

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# F2B: Hammer (wick llarga inferior + close alt)
# ══════════════════════════════════════════════════════════════

def f2b_hammer(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: candle amb wick inferior > 60% del rang total + close al terç superior
    = rebuig de mínims, smart money entra → LONG.
    """
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    N = len(df)
    bb_lo, _, _ = _bb(C, 20, 2.0)

    trades = []
    for i in range(200, N - 1):
        rng = H[i] - L[i]
        if rng <= 0:
            continue
        lower_wick = min(O[i], C[i]) - L[i]
        wick_ratio = lower_wick / rng
        # Hammer: wick inferior > 60% del rang
        if wick_ratio < 0.60:
            continue
        # Close al terç superior
        close_pos = (C[i] - L[i]) / rng
        if close_pos < 0.67:
            continue
        # Filtre: prop de BB lower (no al mig de res)
        if not np.isnan(bb_lo[i]) and C[i] > bb_lo[i] * 1.02:
            continue  # massa lluny de BB lower, no és a mínims
        # Score
        sc = 0
        if wick_ratio > 0.75:
            sc += 2
        elif wick_ratio > 0.65:
            sc += 1
        rng_pct = rng / O[i]
        if rng_pct > 0.02:
            sc += 1
        if rng_pct > 0.03:
            sc += 1

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# F3A: Uptrend EMA + RSI Dip
# ══════════════════════════════════════════════════════════════

def f3a_trend_rsi_dip(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: en tendència alcista (EMA20 > EMA50 > EMA200), un dip de RSI(14) < 40
    indica pullback temporal → rebot en tendència.
    """
    C = df["C"].values; N = len(df)
    ema20 = _ema(C, 20); ema50 = _ema(C, 50); ema200 = _ema(C, 200)
    rsi14 = _rsi(C, 14)

    trades = []
    for i in range(200, N - 1):
        if np.isnan(rsi14[i]):
            continue
        # Uptrend: EMAs alineades
        if not (ema20[i] > ema50[i] > ema200[i]):
            continue
        # Preu per sobre d'EMA50
        if C[i] < ema50[i]:
            continue
        # RSI dip
        if rsi14[i] >= 40:
            continue
        # Score
        sc = 0
        if rsi14[i] < 30:
            sc += 2
        elif rsi14[i] < 35:
            sc += 1
        # Tendència forta
        trend_strength = (ema20[i] - ema200[i]) / ema200[i]
        if trend_strength > 0.10:
            sc += 2
        elif trend_strength > 0.05:
            sc += 1

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# F3B: Pullback a EMA20 en tendència
# ══════════════════════════════════════════════════════════════

def f3b_pullback_ema20(df: pd.DataFrame, asset: str) -> list[TradeRecord]:
    """
    Tesi: en tendència alcista, quan el preu toca EMA20 (pullback)
    i fa una candle verda → continuació LONG.
    """
    C = df["C"].values; O = df["O"].values; L = df["L"].values; N = len(df)
    ema20 = _ema(C, 20); ema50 = _ema(C, 50)

    trades = []
    for i in range(200, N - 1):
        # Uptrend
        if not (ema20[i] > ema50[i]):
            continue
        # Preu tocant EMA20: low <= EMA20 <= high o close prop d'EMA20
        ema_dist = abs(C[i] - ema20[i]) / ema20[i]
        if ema_dist > 0.005:  # close a menys del 0.5% d'EMA20
            if L[i] > ema20[i]:  # low no toca EMA20
                continue
        # Candle verda (rebuig del pullback)
        if C[i] <= O[i]:
            continue
        body_pct = (C[i] - O[i]) / O[i]
        if body_pct < 0.003:
            continue  # massa petita
        # Score
        sc = 0
        if L[i] <= ema20[i] and C[i] > ema20[i]:
            sc += 2  # sweep de l'EMA i recuperació
        if body_pct > 0.01:
            sc += 1
        trend_spread = (ema20[i] - ema50[i]) / ema50[i]
        if trend_spread > 0.03:
            sc += 1

        trades.append(_make_trade(df, i, asset, sc))
    return trades


# ══════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════

SETUP_GENERATORS = {
    "f1a_bb_squeeze_breakout": f1a_bb_squeeze_breakout,
    "f1b_atr_low_big_candle": f1b_atr_low_big_candle,
    "f2a_sweep_reclaim": f2a_sweep_reclaim,
    "f2b_hammer": f2b_hammer,
    "f3a_trend_rsi_dip": f3a_trend_rsi_dip,
    "f3b_pullback_ema20": f3b_pullback_ema20,
}
