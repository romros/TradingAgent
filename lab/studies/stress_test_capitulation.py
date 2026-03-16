"""
stress_test_capitulation.py — Stress Test + Sizing Optimization
Capitulation Scalp 1H (ETH + BTC + SOL)

Tests:
  1. Worst streak analysis (consec losses)
  2. Kelly criterion (optimal sizing)
  3. Drawdown stress (MC equity curves)
  4. Liquidation risk analysis (MAE vs collateral)
  5. Sensitivity to fee changes

Ús:
  python3 lab/studies/stress_test_capitulation.py --cache /tmp/crypto_1h_cache.pkl
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
import urllib.request
from datetime import datetime, timezone
from math import log

import numpy as np
import pandas as pd


# Reuse data/indicator/signal logic from mc script
ASSETS = {"ETH": "ETHUSDT", "BTC": "BTCUSDT", "SOL": "SOLUSDT"}
FEE = 3.36
NOM = 4000
BAD_HOURS = {16, 17, 18, 19}


def load_data(cache_path: str | None) -> dict[str, pd.DataFrame]:
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            raw = pickle.load(f)
        return {sym.replace("USDT", ""): pd.DataFrame(rows).set_index("ts")
                for sym, rows in raw.items()}
    raise RuntimeError("Cache not found. Run mc_walkforward first.")


def calc_bb_lower(c, p=20, m=2.0):
    n = len(c)
    bb = np.full(n, np.nan)
    for i in range(p - 1, n):
        w = c[i - p + 1:i + 1]
        bb[i] = np.mean(w) - m * np.std(w, ddof=0)
    return bb


def calc_rsi(c, p=7):
    n = len(c)
    r = np.full(n, np.nan)
    d = np.diff(c)
    g = np.where(d > 0, d, 0.0)
    lo = np.where(d < 0, -d, 0.0)
    if len(g) < p:
        return r
    ag = np.mean(g[:p]); al = np.mean(lo[:p])
    r[p] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    for i in range(p, len(d)):
        ag = (ag * (p - 1) + g[i]) / p
        al = (al * (p - 1) + lo[i]) / p
        r[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    return r


def calc_drop(c, k=3):
    n = len(c)
    d = np.zeros(n)
    for i in range(k, n):
        d[i] = (c[i] - c[i - k]) / c[i - k]
    return d


def find_signals(df, body_th=-0.03, drop_th=-0.05):
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    V = df["V"].values; N = len(df)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    bb_lo = calc_bb_lower(C)
    rsi7 = calc_rsi(C)
    drop3 = calc_drop(C)
    vol_ma = pd.Series(V).rolling(20).mean().values
    vol_rel = V / np.maximum(vol_ma, 1)

    signals = []
    for i in range(200, N - 1):
        if body_pct[i] >= body_th:
            continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]:
            continue
        if drop3[i] >= drop_th:
            continue
        hour = df.index[i].hour
        if hour in BAD_HOURS or vol_rel[i] > 5:
            continue

        sc = 0
        if body_pct[i] < body_th * 2.5: sc += 2
        elif body_pct[i] < body_th * 1.5: sc += 1
        if drop3[i] < drop_th * 2.5: sc += 2
        elif drop3[i] < drop_th * 1.5: sc += 1
        if not np.isnan(rsi7[i]):
            if rsi7[i] < 15: sc += 2
            elif rsi7[i] < 25: sc += 1
        if vol_rel[i] > 3: sc += 1
        if hour in (20, 21): sc += 1

        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1  # max adverse excursion
        mfe = (h1 - o1) / o1  # max favorable excursion
        pnl = NOM * move - FEE

        signals.append({
            "ts": df.index[i], "yr": df.index[i].year,
            "score": sc, "move": move, "pnl": pnl,
            "mae": mae, "mfe": mfe, "green": c1 > o1,
            "body": body_pct[i], "drop3": drop3[i],
        })
    return signals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="/tmp/crypto_1h_cache.pkl")
    args = parser.parse_args()

    print("=" * 90)
    print("CAPITULATION SCALP 1H — Stress Test + Sizing Optimization")
    print("=" * 90)

    all_data = load_data(args.cache)
    all_trades = []
    for name, df in all_data.items():
        sigs = find_signals(df)
        for s in sigs:
            s["asset"] = name
        all_trades.extend(sigs)

    all_trades.sort(key=lambda t: t["ts"])
    pnls = np.array([t["pnl"] for t in all_trades])
    moves = np.array([t["move"] for t in all_trades])
    maes = np.array([t["mae"] for t in all_trades])
    mfes = np.array([t["mfe"] for t in all_trades])
    greens = np.array([t["green"] for t in all_trades])

    print(f"\n  {len(all_trades)} trades, WR={100 * greens.mean():.0f}%, "
          f"Total={pnls.sum():+.0f}$, Avg={pnls.mean():+.1f}$/t")

    # ══════════════════════════════════════════════════════════
    # 1. WORST STREAK ANALYSIS
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 90}")
    print("1. WORST STREAK ANALYSIS")
    print(f"{'=' * 90}")

    # Real consecutive losses
    max_consec_loss = 0
    current = 0
    streaks = []
    for p in pnls:
        if p <= 0:
            current += 1
            max_consec_loss = max(max_consec_loss, current)
        else:
            if current > 0:
                streaks.append(current)
            current = 0
    if current > 0:
        streaks.append(current)

    print(f"\n  Streak real de pèrdues consecutives:")
    print(f"    Max:     {max_consec_loss}")
    print(f"    Mean:    {np.mean(streaks):.1f}" if streaks else "    Mean:    0")

    # MC simulation of worst streaks (10K sims)
    rng = np.random.default_rng(42)
    mc_max_streaks = []
    for _ in range(10000):
        shuf = rng.permutation(pnls)
        mx = 0; cur = 0
        for p in shuf:
            if p <= 0:
                cur += 1
                mx = max(mx, cur)
            else:
                cur = 0
        mc_max_streaks.append(mx)
    mc_max_streaks = np.array(mc_max_streaks)

    print(f"\n  MC (10K sims) max streak consecutiu:")
    print(f"    Mean:    {mc_max_streaks.mean():.1f}")
    print(f"    P50:     {np.percentile(mc_max_streaks, 50):.0f}")
    print(f"    P75:     {np.percentile(mc_max_streaks, 75):.0f}")
    print(f"    P90:     {np.percentile(mc_max_streaks, 90):.0f}")
    print(f"    P95:     {np.percentile(mc_max_streaks, 95):.0f}")
    print(f"    P99:     {np.percentile(mc_max_streaks, 99):.0f}")

    print(f"\n  Recomanació paper mode threshold:")
    p90 = int(np.percentile(mc_max_streaks, 90))
    print(f"    Actual: 2 losses → paper")
    print(f"    P90 worst streak: {p90} → threshold 2 és conservador (bé)")

    # ══════════════════════════════════════════════════════════
    # 2. KELLY CRITERION
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 90}")
    print("2. KELLY CRITERION — Sizing Optimal")
    print(f"{'=' * 90}")

    wr = greens.mean()
    avg_win = moves[greens].mean()
    avg_loss = abs(moves[~greens].mean())

    # Kelly: f* = (p * b - q) / b  where b = avg_win/avg_loss, p = WR, q = 1-WR
    b = avg_win / avg_loss if avg_loss > 0 else 1
    kelly_f = (wr * b - (1 - wr)) / b if b > 0 else 0
    half_kelly = kelly_f / 2
    quarter_kelly = kelly_f / 4

    print(f"\n  WR = {100 * wr:.1f}%")
    print(f"  Avg win move = +{100 * avg_win:.3f}%")
    print(f"  Avg loss move = -{100 * avg_loss:.3f}%")
    print(f"  W/L ratio (b) = {b:.2f}")
    print(f"\n  Kelly fraction f* = {100 * kelly_f:.1f}% del capital per trade")
    print(f"  Half Kelly        = {100 * half_kelly:.1f}%")
    print(f"  Quarter Kelly     = {100 * quarter_kelly:.1f}%")

    print(f"\n  Actual sizing: 20% capital (col) × 100x leverage")
    print(f"  Kelly diu: {100 * kelly_f:.0f}% — {'sizing actual dins de Kelly' if 0.20 <= kelly_f else 'sizing actual EXCEDIT vs Kelly!'}")

    # Simulate different sizing
    print(f"\n  Simulació compounding amb different % capital:")
    print(f"  {'%Cap':>6} {'Kelly':>8} {'Final$':>9} {'MaxDD%':>7} {'MaxDD$':>8}")
    print(f"  {'─' * 45}")
    for pct in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
        cap = 250.0
        peak = cap
        max_dd_pct = 0
        max_dd_abs = 0
        for t in all_trades:
            col = min(max(cap * pct, 15), 60)
            if cap < 15:
                break
            nom_t = col * 100
            p = nom_t * t["move"] - FEE
            cap += p
            if cap < 0:
                cap = 0
            if cap > peak:
                peak = cap
            dd = peak - cap
            dd_pct = dd / peak * 100 if peak > 0 else 0
            max_dd_pct = max(max_dd_pct, dd_pct)
            max_dd_abs = max(max_dd_abs, dd)
        kelly_label = ""
        if abs(pct - kelly_f) < 0.02:
            kelly_label = " ← Kelly"
        elif abs(pct - half_kelly) < 0.02:
            kelly_label = " ← ½Kelly"
        print(f"  {100 * pct:>5.0f}% {kelly_label:>8} {cap:>8.0f}$ {max_dd_pct:>6.1f}% {max_dd_abs:>7.0f}$")

    # ══════════════════════════════════════════════════════════
    # 3. DRAWDOWN STRESS (MC equity curves)
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 90}")
    print("3. DRAWDOWN STRESS — MC Equity Curves (5.000 sims)")
    print(f"{'=' * 90}")

    n_sim = 5000
    rng2 = np.random.default_rng(123)
    max_dds_pct = []
    max_dds_abs = []
    recovery_times = []
    end_capitals = []

    for _ in range(n_sim):
        shuf = rng2.permutation(pnls)
        cap = 250.0
        peak = cap
        max_dd = 0
        max_dd_pct_sim = 0
        in_dd_since = 0
        max_recovery = 0
        for j, p in enumerate(shuf):
            col = min(max(cap * 0.20, 15), 60)
            if cap < 15:
                break
            nom_t = col * 100
            real_p = nom_t / NOM * p  # scale pnl by actual sizing
            cap += real_p
            if cap < 0:
                cap = 0
            if cap > peak:
                if in_dd_since > 0:
                    max_recovery = max(max_recovery, j - in_dd_since)
                    in_dd_since = 0
                peak = cap
            else:
                if in_dd_since == 0:
                    in_dd_since = j
                dd = peak - cap
                dd_pct = dd / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)
                max_dd_pct_sim = max(max_dd_pct_sim, dd_pct)

        max_dds_pct.append(max_dd_pct_sim)
        max_dds_abs.append(max_dd)
        recovery_times.append(max_recovery)
        end_capitals.append(cap)

    max_dds_pct = np.array(max_dds_pct)
    max_dds_abs = np.array(max_dds_abs)
    recovery_times = np.array(recovery_times)
    end_capitals = np.array(end_capitals)

    print(f"\n  Max Drawdown %:")
    for p in [50, 75, 90, 95, 99]:
        print(f"    P{p}: {np.percentile(max_dds_pct, p):.1f}%")

    print(f"\n  Max Drawdown $:")
    for p in [50, 75, 90, 95, 99]:
        print(f"    P{p}: {np.percentile(max_dds_abs, p):+.0f}$")

    print(f"\n  Max Recovery Time (trades):")
    for p in [50, 75, 90, 95]:
        print(f"    P{p}: {np.percentile(recovery_times, p):.0f} trades")

    print(f"\n  Capital final:")
    print(f"    P5 (pitjor):  {np.percentile(end_capitals, 5):.0f}$")
    print(f"    P25:          {np.percentile(end_capitals, 25):.0f}$")
    print(f"    P50 (median): {np.percentile(end_capitals, 50):.0f}$")
    print(f"    P75:          {np.percentile(end_capitals, 75):.0f}$")
    print(f"    P95 (millor): {np.percentile(end_capitals, 95):.0f}$")
    print(f"    % sims > 250$ (break-even): {100 * np.mean(end_capitals > 250):.1f}%")
    print(f"    % sims > 1000$: {100 * np.mean(end_capitals > 1000):.1f}%")

    # ══════════════════════════════════════════════════════════
    # 4. LIQUIDATION RISK
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 90}")
    print("4. LIQUIDATION RISK — MAE vs Collateral")
    print(f"{'=' * 90}")

    # Amb lev 100x i col 40$, nominal = 4000$
    # Liquidation quan loss >= collateral = 40$
    # Liq price = entry * (1 - col/nom) = entry * (1 - 1/lev) = entry * 0.99
    # Amb col 20% cap i lev 100x: liq = entry * (1 - 0.20*cap / (0.20*cap*100))
    # Simplificat: liq threshold = 1/leverage = 1% move adversa
    # PERÒ Ostium té maintenance margin, no liq al 100% loss del collateral

    print(f"\n  Amb lev 100x: liquidació teòrica si MAE >= 1% (1/leverage)")
    print(f"  Amb lev 50x:  liquidació teòrica si MAE >= 2%")
    print(f"  Amb lev 30x:  liquidació teòrica si MAE >= 3.3%")

    print(f"\n  Distribució MAE dels {len(maes)} trades:")
    for p in [50, 75, 90, 95, 99, 100]:
        v = np.percentile(maes, p) if p < 100 else maes.max()
        label = "MAX" if p == 100 else f"P{p}"
        print(f"    {label}: {100 * v:.2f}%")

    # % trades que es liquidarien per leverage
    for lev in [100, 75, 50, 30, 20]:
        liq_th = 1.0 / lev
        pct_liq = 100 * np.mean(maes >= liq_th)
        print(f"\n  Lev {lev}x: MAE liq threshold = {100 * liq_th:.1f}% → {pct_liq:.1f}% trades liquidats")
        if pct_liq > 0:
            # Quins anys?
            liq_trades = [t for t in all_trades if t["mae"] >= liq_th]
            by_yr = {}
            for t in liq_trades:
                by_yr.setdefault(t["yr"], []).append(t)
            yrs = sorted(by_yr.keys())
            yr_str = ", ".join(f"{yr}:{len(by_yr[yr])}" for yr in yrs)
            print(f"    Per any: {yr_str}")

    # ══════════════════════════════════════════════════════════
    # 5. FEE SENSITIVITY
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 90}")
    print("5. FEE SENSITIVITY")
    print(f"{'=' * 90}")

    for fee in [0, 1, 2, 3.36, 5, 7, 10]:
        adj_pnl = NOM * moves - fee
        wr_adj = 100 * np.mean(adj_pnl > 0)
        total_adj = adj_pnl.sum()
        w = adj_pnl[adj_pnl > 0]
        l = adj_pnl[adj_pnl <= 0]
        pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
        print(f"  Fee={fee:>5.2f}$: WR={wr_adj:.0f}% PF={pf:.1f} Total={total_adj:+.0f}$")

    # ══════════════════════════════════════════════════════════
    # RESUM
    # ══════════════════════════════════════════════════════════
    print(f"\n{'█' * 90}")
    print("RESUM STRESS TEST")
    print(f"{'█' * 90}")

    p95_streak = int(np.percentile(mc_max_streaks, 95))
    p95_dd = np.percentile(max_dds_pct, 95)
    pct_liq_100x = 100 * np.mean(maes >= 0.01)
    pct_profitable = 100 * np.mean(end_capitals > 250)

    print(f"  Worst streak P95:        {p95_streak} losses consecutives")
    print(f"  Paper mode threshold 2:  {'ADEQUAT' if p95_streak <= 5 else 'MASSA CONSERVADOR'}")
    print(f"  Kelly fraction:          {100 * kelly_f:.0f}% (actual 20% {'OK' if 0.20 <= kelly_f else 'EXCEDIT'})")
    print(f"  Max DD P95:              {p95_dd:.1f}%")
    print(f"  Liquidation risk 100x:   {pct_liq_100x:.1f}% trades")
    print(f"  MC sims profitable:      {pct_profitable:.1f}%")
    print(f"  Fee breakeven:           ~{NOM * moves.mean():.1f}$ (actual fee {FEE}$)")

    # Recomanacions
    print(f"\n  RECOMANACIONS:")
    if pct_liq_100x > 10:
        rec_lev = 50 if 100 * np.mean(maes >= 0.02) < 5 else 30
        print(f"    ⚠ Liquidation risk alt amb 100x ({pct_liq_100x:.0f}%). Recomanem lev {rec_lev}x")
    else:
        print(f"    ✓ Liquidation risk acceptable amb 100x ({pct_liq_100x:.0f}%)")

    if kelly_f < 0.20:
        print(f"    ⚠ Sizing 20% excedeix Kelly ({100 * kelly_f:.0f}%). Considerar baixar a {100 * half_kelly:.0f}%")
    else:
        print(f"    ✓ Sizing 20% dins de Kelly ({100 * kelly_f:.0f}%)")

    if p95_dd > 50:
        print(f"    ⚠ Max DD P95 alt ({p95_dd:.0f}%). Considerar sizing més conservador")
    else:
        print(f"    ✓ Max DD P95 acceptable ({p95_dd:.0f}%)")


if __name__ == "__main__":
    main()
