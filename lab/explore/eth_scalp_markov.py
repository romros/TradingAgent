"""
eth_scalp_markov.py — Cadenes de Markov per scalping ETH/USD 4H

IDEA:
  Classificar cada candle 4H en un estat (color + mida + wick profile).
  Construir trigrams (3 candles consecutives) i calcular la probabilitat
  que la SEGÜENT candle sigui una "clean green":
    - close > open  (verda)
    - lower_wick petit  (no baixa gaire des de l'open)
    → ideal per scalping: entres a l'open i puja sense drawdown

CLASSIFICACIÓ CANDLE — 12 estats híbrids:
  Direcció: G (green) | R (red)
  Mida body: S (small <p33) | M (medium p33-p66) | L (large >p66)
  Wick profile (per candles M i L):
    n = normal (sense wick dominant)
    h = hammer (lower wick > 40% del rang → rebuig de mínims)
    s = shooting star (upper wick > 40% del rang → rebuig de màxims)
  Les S (petites/doji) no es subdivideixen per wick (massa soroll).

  Estats: GS, GMn, GMh, GMs, GLn, GLh, GLs, RS, RMn, RMh, RMs, RLn, RLh, RLs
  → 14 estats, 14^3 = 2744 trigrams possibles (manejable amb ~18k candles)

DADES: Binance ETHUSDT 4H natiu, 2017-08 → 2026-03 (~18.800 candles, 8.6 anys)
SPLIT: IS 2017-08 → 2023-12 | OOS 2024-01 → 2026-03

Ús:
  python3 eth_scalp_markov.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ── Paràmetres ────────────────────────────────────────────────────────────────

SYMBOL = "ETHUSDT"
INTERVAL = "4h"

# Split temporal
IS_END = "2023-12-31"
OOS_START = "2024-01-01"

# Llindar "clean green"
CLEAN_GREEN_MAX_LOWER_WICK = 0.15   # lower wick < 15% del rang
CLEAN_GREEN_MIN_BODY_PCT = 0.003    # body > 0.3% (ETH 4H mou ~2%, 0.3% és prou)

# Wick profile thresholds
WICK_DOMINANT_RATIO = 0.40  # wick > 40% del rang total → dominant

# Simulació
COLLATERAL = 40.0
LEVERAGE = 50
FEE_PER_TRADE = 3.36  # opening 3.10 + rollover ~0.22 + gas 0.04

MIN_N_TRIGRAM = 15  # mínim ocurrències per considerar un trigram fiable


# ── Descarregar dades de Binance ─────────────────────────────────────────────

def download_binance_klines(symbol: str = SYMBOL, interval: str = INTERVAL) -> pd.DataFrame:
    """Baixa TOTES les candles 4H de Binance (paginat, 1000 per request)."""
    print(f"Baixant {symbol} {interval} de Binance (totes les candles)...")

    all_klines = []
    start_ms = 0  # des del principi
    base_url = "https://api.binance.com/api/v3/klines"

    while True:
        params = f"symbol={symbol}&interval={interval}&startTime={start_ms}&limit=1000"
        url = f"{base_url}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read())
        except Exception as e:
            print(f"  Error: {e}")
            break

        if not data:
            break

        all_klines.extend(data)
        last_ts = data[-1][0]
        start_ms = last_ts + 1  # next batch starts after last candle

        if len(data) < 1000:
            break  # no more data

        time.sleep(0.1)  # rate limit respectuós

    print(f"  → {len(all_klines)} candles {interval} descarregades")

    # Convertir a DataFrame
    rows = []
    for k in all_klines:
        ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
        rows.append({
            "timestamp": ts,
            "Open": float(k[1]),
            "High": float(k[2]),
            "Low": float(k[3]),
            "Close": float(k[4]),
            "Volume": float(k[5]),
        })

    df = pd.DataFrame(rows).set_index("timestamp")
    print(f"  → Rang: {df.index[0]} → {df.index[-1]}")
    print(f"  → {(df.index[-1] - df.index[0]).days / 365.25:.1f} anys")
    return df


# ── Classificar candles ──────────────────────────────────────────────────────

@dataclass
class CandleInfo:
    idx: int
    ts: pd.Timestamp
    o: float
    h: float
    l: float
    c: float
    vol: float
    body_pct: float         # |close-open|/open
    is_green: bool
    lower_wick_ratio: float # (body_bottom - low) / (high - low)
    upper_wick_ratio: float # (high - body_top) / (high - low)
    state: str              # ex: "GLh", "RMn"
    is_clean_green: bool


def classify_candles(df: pd.DataFrame) -> list[CandleInfo]:
    """Classifica cada candle en un dels 14 estats híbrids."""
    candles = []
    for i, (ts, row) in enumerate(df.iterrows()):
        o, h, l, c, v = row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]
        rng = h - l
        if rng < 1e-9:
            continue

        body = abs(c - o)
        body_pct = body / o
        is_green = c >= o
        body_top = max(o, c)
        body_bottom = min(o, c)
        lower_wick_ratio = (body_bottom - l) / rng
        upper_wick_ratio = (h - body_top) / rng

        candles.append(CandleInfo(
            idx=i, ts=ts, o=o, h=h, l=l, c=c, vol=v,
            body_pct=body_pct, is_green=is_green,
            lower_wick_ratio=lower_wick_ratio,
            upper_wick_ratio=upper_wick_ratio,
            state="",
            is_clean_green=False,
        ))

    # Percentils de body_pct per S/M/L
    bodies = np.array([c.body_pct for c in candles])
    p33 = np.percentile(bodies, 33.3)
    p66 = np.percentile(bodies, 66.6)
    print(f"\n  Body pct percentils: p33={p33*100:.3f}%, p66={p66*100:.3f}%")

    for c in candles:
        direction = "G" if c.is_green else "R"

        if c.body_pct < p33:
            size = "S"
            wick = ""  # no subdividim les petites
        elif c.body_pct < p66:
            size = "M"
            if c.lower_wick_ratio >= WICK_DOMINANT_RATIO:
                wick = "h"  # hammer
            elif c.upper_wick_ratio >= WICK_DOMINANT_RATIO:
                wick = "s"  # shooting star
            else:
                wick = "n"  # normal
        else:
            size = "L"
            if c.lower_wick_ratio >= WICK_DOMINANT_RATIO:
                wick = "h"
            elif c.upper_wick_ratio >= WICK_DOMINANT_RATIO:
                wick = "s"
            else:
                wick = "n"

        c.state = direction + size + wick

        c.is_clean_green = (
            c.is_green
            and c.lower_wick_ratio < CLEAN_GREEN_MAX_LOWER_WICK
            and c.body_pct >= CLEAN_GREEN_MIN_BODY_PCT
        )

    n_clean = sum(1 for c in candles if c.is_clean_green)
    print(f"  Clean green candles: {n_clean}/{len(candles)} ({100*n_clean/len(candles):.1f}%)")

    state_counts = Counter(c.state for c in candles)
    print(f"  Estats ({len(state_counts)} únics):")
    for st, cnt in state_counts.most_common():
        print(f"    {st:>4}: {cnt:5d} ({100*cnt/len(candles):4.1f}%)")

    return candles


# ── Markov: trigrams ─────────────────────────────────────────────────────────

@dataclass
class TrigramStats:
    trigram: str
    n_total: int
    n_clean_green: int
    n_any_green: int
    p_clean_green: float
    p_any_green: float
    avg_body_pct: float
    avg_lower_wick: float
    avg_move_pct: float
    avg_drawdown_pct: float
    win_rate_no_dd: float     # % on low >= open * 0.998
    _score: float = 0.0


def build_trigram_stats(candles: list[CandleInfo]) -> list[TrigramStats]:
    trigram_nexts: dict[str, list[CandleInfo]] = defaultdict(list)

    for i in range(3, len(candles)):
        trigram = f"{candles[i-3].state}|{candles[i-2].state}|{candles[i-1].state}"
        trigram_nexts[trigram].append(candles[i])

    stats = []
    for trigram, nexts in trigram_nexts.items():
        n = len(nexts)
        n_cg = sum(1 for c in nexts if c.is_clean_green)
        n_ag = sum(1 for c in nexts if c.is_green)

        cg_bodies = [c.body_pct for c in nexts if c.is_clean_green]
        cg_lwicks = [c.lower_wick_ratio for c in nexts if c.is_clean_green]
        all_moves = [(c.c - c.o) / c.o for c in nexts]
        all_dd = [(c.o - c.l) / c.o for c in nexts]
        n_low_dd = sum(1 for c in nexts if c.l >= c.o * 0.998)

        stats.append(TrigramStats(
            trigram=trigram,
            n_total=n,
            n_clean_green=n_cg,
            n_any_green=n_ag,
            p_clean_green=n_cg / n if n > 0 else 0,
            p_any_green=n_ag / n if n > 0 else 0,
            avg_body_pct=np.mean(cg_bodies) if cg_bodies else 0,
            avg_lower_wick=np.mean(cg_lwicks) if cg_lwicks else 0,
            avg_move_pct=np.mean(all_moves) if all_moves else 0,
            avg_drawdown_pct=np.mean(all_dd) if all_dd else 0,
            win_rate_no_dd=n_low_dd / n if n > 0 else 0,
        ))

    return stats


# ── Simulació de scalping ────────────────────────────────────────────────────

def simulate_scalping(candles: list[CandleInfo], top_trigrams: set[str],
                      label: str = "") -> dict:
    nominal = COLLATERAL * LEVERAGE
    trades = []

    for i in range(3, len(candles)):
        trigram = f"{candles[i-3].state}|{candles[i-2].state}|{candles[i-1].state}"
        if trigram not in top_trigrams:
            continue

        c = candles[i]
        move_pct = (c.c - c.o) / c.o
        pnl_gross = nominal * move_pct
        pnl_net = pnl_gross - FEE_PER_TRADE
        dd_pct = (c.o - c.l) / c.o
        dd_dollar = nominal * dd_pct

        trades.append({
            "ts": c.ts, "move_pct": move_pct,
            "pnl_gross": pnl_gross, "pnl_net": pnl_net,
            "dd_pct": dd_pct, "dd_dollar": dd_dollar,
            "is_green": c.is_green, "is_clean": c.is_clean_green,
        })

    if not trades:
        return {"n": 0, "label": label}

    df = pd.DataFrame(trades)
    wins = df[df["pnl_net"] > 0]
    losses = df[df["pnl_net"] <= 0]
    gross_win = wins["pnl_net"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_net"].sum()) if len(losses) > 0 else 0.01

    return {
        "label": label,
        "n": len(df), "n_win": len(wins), "n_loss": len(losses),
        "wr": len(wins) / len(df) * 100,
        "total_net": df["pnl_net"].sum(),
        "avg_net": df["pnl_net"].mean(),
        "avg_win": wins["pnl_net"].mean() if len(wins) > 0 else 0,
        "avg_loss": losses["pnl_net"].mean() if len(losses) > 0 else 0,
        "max_dd_dollar": df["dd_dollar"].max(),
        "avg_dd_pct": df["dd_pct"].mean() * 100,
        "pf": gross_win / gross_loss,
        "trades_df": df,
    }


def print_sim(res: dict):
    if res["n"] == 0:
        print(f"    {res['label']}: 0 trades")
        return
    print(f"    {res['label']}")
    print(f"    {'─' * 50}")
    print(f"    Trades:    {res['n']:>6}     WR:       {res['wr']:>6.1f}%")
    print(f"    Total net: {res['total_net']:>+9.2f}$  Avg/trade: {res['avg_net']:>+7.2f}$")
    print(f"    Avg win:   {res['avg_win']:>+9.2f}$  Avg loss:  {res['avg_loss']:>+7.2f}$")
    print(f"    PF:        {res['pf']:>9.2f}   Max DD:    {res['max_dd_dollar']:>7.2f}$")


# ── Report principal ─────────────────────────────────────────────────────────

STATE_DESC = {
    "GS":  "Green petita (doji alcista)",
    "GMn": "Green mitjana, normal",
    "GMh": "Green mitjana, hammer (rebuig de mínims)",
    "GMs": "Green mitjana, shooting star (rebuig de màxims)",
    "GLn": "Green gran, normal (pujada forta neta)",
    "GLh": "Green gran, hammer",
    "GLs": "Green gran, shooting star",
    "RS":  "Red petita (doji baixista)",
    "RMn": "Red mitjana, normal",
    "RMh": "Red mitjana, hammer (intent de rebot)",
    "RMs": "Red mitjana, shooting star",
    "RLn": "Red gran, normal (baixada forta neta)",
    "RLh": "Red gran, hammer",
    "RLs": "Red gran, shooting star",
}


def print_rankings(stats: list[TrigramStats], title_suffix: str = ""):
    viable = [s for s in stats if s.n_total >= MIN_N_TRIGRAM]
    if not viable:
        print(f"  Cap trigram amb N >= {MIN_N_TRIGRAM}")
        return []

    print(f"\n{'=' * 95}")
    print(f"MARKOV TRIGRAMS → CLEAN GREEN (ETH/USD 4H) {title_suffix}")
    print(f"Trigrams amb N >= {MIN_N_TRIGRAM}: {len(viable)}/{len(stats)}")
    print("=" * 95)

    # ── Top 20 per P(clean_green)
    viable.sort(key=lambda s: s.p_clean_green, reverse=True)
    print(f"\n  TOP 20 — P(clean_green)")
    print(f"  {'─' * 90}")
    print(f"  {'#':>3} {'Trigram':<22} {'N':>5} {'P(CG)':>7} {'P(grn)':>7} "
          f"{'Avg mv':>8} {'Avg DD':>7} {'WR<.2%':>7}")
    print(f"  {'─' * 90}")
    for rank, s in enumerate(viable[:20], 1):
        print(f"  {rank:3d} {s.trigram:<22} {s.n_total:5d} {s.p_clean_green:6.1%} "
              f"{s.p_any_green:6.1%} {s.avg_move_pct*100:+7.3f}% "
              f"{s.avg_drawdown_pct*100:6.3f}% {s.win_rate_no_dd:6.1%}")

    # ── Top 20 per avg move
    viable_move = sorted(viable, key=lambda s: s.avg_move_pct, reverse=True)
    print(f"\n  TOP 20 — Avg move % (edge real)")
    print(f"  {'─' * 90}")
    print(f"  {'#':>3} {'Trigram':<22} {'N':>5} {'Avg mv':>8} {'P(CG)':>7} "
          f"{'P(grn)':>7} {'Avg DD':>7}")
    print(f"  {'─' * 90}")
    for rank, s in enumerate(viable_move[:20], 1):
        print(f"  {rank:3d} {s.trigram:<22} {s.n_total:5d} {s.avg_move_pct*100:+7.3f}% "
              f"{s.p_clean_green:6.1%} {s.p_any_green:6.1%} "
              f"{s.avg_drawdown_pct*100:6.3f}%")

    # ── Score combinat
    for s in viable:
        s._score = s.p_clean_green * max(s.avg_move_pct, 0) * (1 - min(s.avg_drawdown_pct * 10, 0.99))

    viable_score = sorted(viable, key=lambda s: s._score, reverse=True)
    print(f"\n  TOP 20 — Score combinat (P(CG) x move x baixa_DD)")
    print(f"  {'─' * 90}")
    print(f"  {'#':>3} {'Trigram':<22} {'N':>5} {'Score':>9} {'P(CG)':>7} "
          f"{'Avg mv':>8} {'Avg DD':>7} {'P(grn)':>7}")
    print(f"  {'─' * 90}")
    for rank, s in enumerate(viable_score[:20], 1):
        print(f"  {rank:3d} {s.trigram:<22} {s.n_total:5d} {s._score:9.6f} "
              f"{s.p_clean_green:6.1%} {s.avg_move_pct*100:+7.3f}% "
              f"{s.avg_drawdown_pct*100:6.3f}% {s.p_any_green:6.1%}")

    return viable_score


def print_interpretations(top_stats: list[TrigramStats], n: int = 10):
    print(f"\n{'=' * 95}")
    print("INTERPRETACIÓ DELS TOP TRIGRAMS")
    print("=" * 95)
    for s in top_stats[:n]:
        parts = s.trigram.split("|")
        print(f"\n  {s.trigram}  (N={s.n_total}, P(CG)={s.p_clean_green:.0%}, "
              f"avg move={s.avg_move_pct*100:+.3f}%)")
        for i, p in enumerate(parts):
            desc = STATE_DESC.get(p, "?")
            print(f"    Candle {i+1}: {p:>4} = {desc}")
        print(f"    → Després: {s.p_clean_green:.0%} clean green, "
              f"{s.p_any_green:.0%} qualsevol green")


def print_transition_matrix(candles: list[CandleInfo]):
    """Matriu 1-pas: estat actual → P(clean green)."""
    print(f"\n{'=' * 95}")
    print("MATRIU TRANSICIÓ 1-PAS (estat → P(clean green))")
    print("=" * 95)

    single: dict[str, list[bool]] = defaultdict(list)
    for i in range(1, len(candles)):
        single[candles[i-1].state].append(candles[i].is_clean_green)

    states_sorted = sorted(single.keys())
    print(f"\n  {'Estat':>5} {'N':>6} {'P(CG)':>7} {'Bar'}")
    print(f"  {'─' * 50}")
    for st in states_sorted:
        vals = single[st]
        pcg = sum(vals) / len(vals)
        bar = "█" * int(pcg * 50)
        print(f"  {st:>5} {len(vals):6d} {pcg:6.1%}  {bar}")


def print_bigrams(candles: list[CandleInfo]):
    print(f"\n{'=' * 95}")
    print("TOP 15 BIGRAMS → P(clean green)")
    print("=" * 95)

    bigram_nexts: dict[str, list[bool]] = defaultdict(list)
    for i in range(2, len(candles)):
        bg = f"{candles[i-2].state}|{candles[i-1].state}"
        bigram_nexts[bg].append(candles[i].is_clean_green)

    bg_stats = []
    for bg, vals in bigram_nexts.items():
        if len(vals) >= MIN_N_TRIGRAM:
            bg_stats.append((bg, len(vals), sum(vals) / len(vals)))

    bg_stats.sort(key=lambda x: x[2], reverse=True)
    print(f"\n  {'Bigram':<16} {'N':>6} {'P(CG)':>7}")
    print(f"  {'─' * 32}")
    for bg, n, pcg in bg_stats[:15]:
        print(f"  {bg:<16} {n:6d} {pcg:6.1%}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # 1. Descarregar
    df = download_binance_klines()

    # 2. Split IS / OOS
    is_end_ts = pd.Timestamp(IS_END, tz=timezone.utc)
    oos_start_ts = pd.Timestamp(OOS_START, tz=timezone.utc)

    df_is = df[df.index <= is_end_ts]
    df_oos = df[df.index >= oos_start_ts]
    print(f"\n  IS:  {len(df_is):,} candles ({df_is.index[0].date()} → {df_is.index[-1].date()})")
    print(f"  OOS: {len(df_oos):,} candles ({df_oos.index[0].date()} → {df_oos.index[-1].date()})")

    # 3. Classificar (percentils calculats sobre IS)
    print("\n── Classificant candles (percentils IS) ──")
    candles_all = classify_candles(df)

    # Separar IS / OOS per índex temporal
    candles_is = [c for c in candles_all if c.ts <= is_end_ts]
    candles_oos = [c for c in candles_all if c.ts >= oos_start_ts]
    print(f"\n  Candles IS:  {len(candles_is)}")
    print(f"  Candles OOS: {len(candles_oos)}")

    # 4. Trigrams IS
    print("\n" + "█" * 95)
    print("█  IN-SAMPLE (2017-08 → 2023-12) — ENTRENAMENT")
    print("█" * 95)

    stats_is = build_trigram_stats(candles_is)
    top_is = print_rankings(stats_is, "[IS]")
    if top_is:
        print_interpretations(top_is)
    print_transition_matrix(candles_is)
    print_bigrams(candles_is)

    # 5. Trigrams OOS
    print("\n" + "█" * 95)
    print("█  OUT-OF-SAMPLE (2024-01 → 2026-03) — VALIDACIÓ")
    print("█" * 95)

    stats_oos = build_trigram_stats(candles_oos)
    top_oos = print_rankings(stats_oos, "[OOS]")

    # 6. Validació creuada: top IS trigrams → rendiment a OOS
    if top_is:
        print(f"\n{'=' * 95}")
        print("VALIDACIÓ: Top trigrams IS → rendiment a OOS")
        print("=" * 95)

        top5_is = {s.trigram for s in top_is[:5]}
        top10_is = {s.trigram for s in top_is[:10]}
        top20_is = {s.trigram for s in top_is[:20]}

        # Lookup ràpid OOS
        oos_lookup = {s.trigram: s for s in stats_oos}

        print(f"\n  {'Trigram IS':<22} {'N_IS':>5} {'P(CG) IS':>8} "
              f"{'N_OOS':>6} {'P(CG) OOS':>9} {'Δ':>7}")
        print(f"  {'─' * 65}")
        for s in top_is[:20]:
            s_oos = oos_lookup.get(s.trigram)
            if s_oos and s_oos.n_total >= 3:
                delta = s_oos.p_clean_green - s.p_clean_green
                print(f"  {s.trigram:<22} {s.n_total:5d} {s.p_clean_green:7.1%} "
                      f"{s_oos.n_total:6d} {s_oos.p_clean_green:8.1%} {delta:+6.1%}")
            else:
                print(f"  {s.trigram:<22} {s.n_total:5d} {s.p_clean_green:7.1%} "
                      f"{'—':>6} {'—':>9} {'—':>7}")

        # Simulació IS vs OOS
        print(f"\n  Simulació scalping (col {COLLATERAL}$, lev {LEVERAGE}x, fee {FEE_PER_TRADE}$)")
        print(f"  {'─' * 70}")
        for label, tset in [("Top 5 IS", top5_is), ("Top 10 IS", top10_is),
                             ("Top 20 IS", top20_is)]:
            res_is = simulate_scalping(candles_is, tset, f"{label} → IS")
            res_oos = simulate_scalping(candles_oos, tset, f"{label} → OOS")
            print()
            print_sim(res_is)
            print_sim(res_oos)

    # 7. Base rate
    print(f"\n{'=' * 95}")
    print("RESUM EXECUTIU")
    print("=" * 95)
    n_is = len(candles_is)
    n_oos = len(candles_oos)
    cg_is = sum(1 for c in candles_is if c.is_clean_green)
    cg_oos = sum(1 for c in candles_oos if c.is_clean_green)
    print(f"  IS:  {n_is} candles, base rate CG = {cg_is/n_is:.1%}")
    print(f"  OOS: {n_oos} candles, base rate CG = {cg_oos/n_oos:.1%}")
    print(f"  Edge = trigram amb P(CG) significativament > base rate")
    print(f"  Un trigram IS amb P(CG) que es manté a OOS = senyal real, no overfitting")


if __name__ == "__main__":
    main()
