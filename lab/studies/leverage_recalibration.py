"""
leverage_recalibration.py — T1: Recalibrar leverage MVP amb liquidació simulada

Simula liquidació real d'Ostium per a Capitulation Scalp 1H.
Compara 10x, 15x, 20x, 30x, 50x, 100x.

Liquidació: si MAE >= 1/leverage → trade tancat amb pnl = -collateral (pèrdua total col)

Ús:
  python3 lab/studies/leverage_recalibration.py --cache /tmp/crypto_1h_cache.pkl
"""
from __future__ import annotations

import argparse
import os
import pickle
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════
# DATA + INDICATORS + SIGNALS (same logic as mc_walkforward)
# ══════════════════════════════════════════════════════════════

BAD_HOURS = {16, 17, 18, 19}
FEE = 3.36


def load_data(cache_path: str) -> dict[str, pd.DataFrame]:
    with open(cache_path, "rb") as f:
        raw = pickle.load(f)
    return {sym.replace("USDT", ""): pd.DataFrame(rows).set_index("ts")
            for sym, rows in raw.items()}


def calc_bb_lower(c, p=20, m=2.0):
    n = len(c); bb = np.full(n, np.nan)
    for i in range(p - 1, n):
        w = c[i - p + 1:i + 1]; bb[i] = np.mean(w) - m * np.std(w, ddof=0)
    return bb


def calc_rsi(c, p=7):
    n = len(c); r = np.full(n, np.nan); d = np.diff(c)
    g = np.where(d > 0, d, 0.0); lo = np.where(d < 0, -d, 0.0)
    if len(g) < p: return r
    ag = np.mean(g[:p]); al = np.mean(lo[:p])
    r[p] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    for i in range(p, len(d)):
        ag = (ag * (p - 1) + g[i]) / p; al = (al * (p - 1) + lo[i]) / p
        r[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    return r


def calc_drop(c, k=3):
    n = len(c); d = np.zeros(n)
    for i in range(k, n): d[i] = (c[i] - c[i - k]) / c[i - k]
    return d


def find_signals(df):
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    V = df["V"].values; N = len(df)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    bb_lo = calc_bb_lower(C); rsi7 = calc_rsi(C); drop3 = calc_drop(C)
    vol_ma = pd.Series(V).rolling(20).mean().values
    vol_rel = V / np.maximum(vol_ma, 1)

    signals = []
    for i in range(200, N - 1):
        if body_pct[i] >= -0.03: continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]: continue
        if drop3[i] >= -0.05: continue
        hour = df.index[i].hour
        if hour in BAD_HOURS or vol_rel[i] > 5: continue

        sc = 0
        if body_pct[i] < -0.075: sc += 2
        elif body_pct[i] < -0.045: sc += 1
        if drop3[i] < -0.125: sc += 2
        elif drop3[i] < -0.075: sc += 1
        if not np.isnan(rsi7[i]):
            if rsi7[i] < 15: sc += 2
            elif rsi7[i] < 25: sc += 1
        if vol_rel[i] > 3: sc += 1
        if hour in (20, 21): sc += 1

        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        mae = (o1 - l1) / o1
        mfe = (h1 - o1) / o1

        signals.append({
            "ts": df.index[i], "yr": df.index[i].year,
            "asset": "", "score": sc,
            "move": move, "mae": mae, "mfe": mfe,
            "green": c1 > o1,
        })
    return signals


# ══════════════════════════════════════════════════════════════
# CORE: Simulate with liquidation
# ══════════════════════════════════════════════════════════════

def simulate_leverage(trades: list[dict], leverage: int,
                      col_pct: float = 0.20, col_min: float = 15.0,
                      col_max: float = 60.0, init_capital: float = 250.0,
                      paper_threshold: int = 2) -> dict:
    """
    Simula el backtest amb liquidació real.
    Si MAE >= 1/leverage → pnl = -collateral (liquidació total).
    Inclou paper mode: 2 losses → paper fins 1 win paper.
    1 posició max (processar sequencialment per timestamp).
    """
    liq_threshold = 1.0 / leverage
    capital = init_capital
    consec_loss = 0
    paper_mode = False
    in_trade = False

    results_by_yr = {}
    total_trades = 0
    total_liquidated = 0
    total_paper_skipped = 0
    all_pnls = []

    # Sort by timestamp
    sorted_trades = sorted(trades, key=lambda t: t["ts"])

    for t in sorted_trades:
        if in_trade:
            in_trade = False
            continue

        move = t["move"]
        mae = t["mae"]
        yr = t["yr"]

        # Paper mode check
        if paper_mode:
            # Simulate in paper: would this trade have won?
            if mae >= liq_threshold:
                paper_pnl = -1  # liquidated in paper too
            else:
                paper_pnl = move
            if paper_pnl > 0:
                paper_mode = False
                consec_loss = 0
            total_paper_skipped += 1
            in_trade = True
            continue

        # Real trade
        col = min(max(capital * col_pct, col_min), col_max)
        if capital < col_min:
            continue

        nominal = col * leverage

        # Liquidation check
        liquidated = mae >= liq_threshold
        if liquidated:
            pnl = -col  # lose entire collateral
            total_liquidated += 1
        else:
            pnl = nominal * move - FEE

        capital += pnl
        if capital < 0:
            capital = 0

        all_pnls.append(pnl)
        total_trades += 1
        in_trade = True

        if yr not in results_by_yr:
            results_by_yr[yr] = []
        results_by_yr[yr].append(pnl)

        # Paper mode state machine
        if pnl > 0:
            consec_loss = 0
        else:
            consec_loss += 1
            if consec_loss >= paper_threshold:
                paper_mode = True

    # Compute stats
    arr = np.array(all_pnls) if all_pnls else np.array([0])
    wr = 100 * np.mean(arr > 0) if len(arr) > 0 else 0
    w = arr[arr > 0]; l = arr[arr <= 0]
    pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99
    total_pnl = arr.sum()

    # Max drawdown
    eq = np.cumsum(arr) + init_capital
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    max_dd = dd.max() if len(dd) > 0 else 0
    max_dd_pct = (max_dd / peak[np.argmax(dd)] * 100) if max_dd > 0 and len(peak) > 0 else 0

    # Worst streak
    mx_streak = 0; cur = 0
    for p in arr:
        if p <= 0: cur += 1; mx_streak = max(mx_streak, cur)
        else: cur = 0

    # Per year
    yearly = {}
    neg_years = 0
    for yr in sorted(results_by_yr.keys()):
        ya = np.array(results_by_yr[yr])
        ytot = ya.sum()
        ywr = 100 * np.mean(ya > 0)
        if ytot < 0:
            neg_years += 1
        yearly[yr] = {"n": len(ya), "wr": round(ywr, 0), "total": round(ytot, 0)}

    return {
        "leverage": leverage,
        "liq_threshold_pct": round(100 / leverage, 2),
        "total_trades": total_trades,
        "liquidated": total_liquidated,
        "liquidated_pct": round(100 * total_liquidated / total_trades, 1) if total_trades > 0 else 0,
        "paper_skipped": total_paper_skipped,
        "wr": round(wr, 1),
        "pf": round(pf, 2),
        "total_pnl": round(total_pnl, 0),
        "avg_pnl": round(arr.mean(), 1) if len(arr) > 0 else 0,
        "capital_final": round(capital, 0),
        "capital_x": round(capital / init_capital, 1),
        "max_dd_pct": round(max_dd_pct, 1),
        "max_dd_abs": round(max_dd, 0),
        "worst_streak": mx_streak,
        "neg_years": neg_years,
        "pos_years": len(yearly) - neg_years,
        "yearly": yearly,
        "ev_per_trade": round(arr.mean(), 2) if len(arr) > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="/tmp/crypto_1h_cache.pkl")
    parser.add_argument("--out", default="lab/out/leverage_recalibration.json")
    args = parser.parse_args()

    print("=" * 90)
    print("T1: RECALIBRAR LEVERAGE MVP — Liquidació simulada")
    print("=" * 90)

    # Load
    all_data = load_data(args.cache)
    all_trades = []
    for name, df in all_data.items():
        sigs = find_signals(df)
        for s in sigs:
            s["asset"] = name
        all_trades.extend(sigs)
        print(f"  {name}: {len(sigs)} trades")
    print(f"  TOTAL: {len(all_trades)} trades")

    # ────────────────────────────────────────────────────────
    # BASELINE: sense liquidació (el que teníem)
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("BASELINE: Sense liquidació (referència)")
    print(f"{'=' * 90}")

    baseline = simulate_leverage(all_trades, leverage=100, col_pct=0.20)
    # Override: disable liquidation for baseline
    capital = 250.0; consec_loss = 0; paper = False; arr_bl = []
    sorted_t = sorted(all_trades, key=lambda t: t["ts"])
    in_tr = False
    for t in sorted_t:
        if in_tr: in_tr = False; continue
        if paper:
            if t["move"] > 0: paper = False; consec_loss = 0
            in_tr = True; continue
        col = min(max(capital * 0.20, 15), 60)
        if capital < 15: continue
        pnl = col * 100 * t["move"] - FEE
        capital += pnl
        if capital < 0: capital = 0
        arr_bl.append(pnl)
        in_tr = True
        if pnl > 0: consec_loss = 0
        else:
            consec_loss += 1
            if consec_loss >= 2: paper = True

    arr_bl = np.array(arr_bl)
    bl_wr = 100 * np.mean(arr_bl > 0)
    bl_w = arr_bl[arr_bl > 0]; bl_l = arr_bl[arr_bl <= 0]
    bl_pf = abs(bl_w.sum() / bl_l.sum()) if len(bl_l) > 0 and bl_l.sum() != 0 else 99
    print(f"  N={len(arr_bl)} WR={bl_wr:.0f}% PF={bl_pf:.1f} Capital=250$→{capital:.0f}$ (x{capital/250:.0f})")
    print(f"  (Sense liquidació — resultats optimistes)")

    # ────────────────────────────────────────────────────────
    # COMPARATIVA AMB LIQUIDACIÓ
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("COMPARATIVA AMB LIQUIDACIÓ SIMULADA")
    print(f"{'=' * 90}")

    LEVERAGES = [10, 15, 20, 30, 50, 100]
    results = {}

    print(f"\n  {'Lev':>5} {'LiqTh':>6} {'N':>5} {'Liq':>5} {'Liq%':>6} {'Paper':>6} "
          f"{'WR':>5} {'PF':>5} {'Total$':>8} {'Avg$':>7} {'Cap$':>7} {'x':>5} "
          f"{'MaxDD%':>7} {'Streak':>6} {'Yr+':>4} {'Yr-':>4}")
    print(f"  {'─' * 105}")

    for lev in LEVERAGES:
        r = simulate_leverage(all_trades, lev)
        results[lev] = r
        print(f"  {lev:>4}x {r['liq_threshold_pct']:>5.1f}% {r['total_trades']:>5} "
              f"{r['liquidated']:>5} {r['liquidated_pct']:>5.1f}% {r['paper_skipped']:>6} "
              f"{r['wr']:>4.0f}% {r['pf']:>4.1f} {r['total_pnl']:>+7.0f}$ "
              f"{r['avg_pnl']:>+6.1f}$ {r['capital_final']:>6.0f}$ {r['capital_x']:>4.1f}x "
              f"{r['max_dd_pct']:>6.1f}% {r['worst_streak']:>6} "
              f"{r['pos_years']:>4} {r['neg_years']:>4}")

    # ────────────────────────────────────────────────────────
    # DETALL PER ANY dels candidats (20x, 30x)
    # ────────────────────────────────────────────────────────
    for lev in [20, 30, 50]:
        r = results[lev]
        print(f"\n  DETALL {lev}x per any:")
        print(f"  {'Any':>6} {'N':>4} {'WR':>5} {'Total':>8}")
        print(f"  {'─' * 30}")
        for yr, yd in sorted(r["yearly"].items()):
            flag = " ***NEG***" if yd["total"] < 0 else ""
            print(f"  {yr:>6} {yd['n']:>4} {yd['wr']:>4.0f}% {yd['total']:>+7.0f}${flag}")

    # ────────────────────────────────────────────────────────
    # ANÀLISI: EV per trade ajustat
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("EV PER TRADE AJUSTAT (amb liquidació)")
    print(f"{'=' * 90}")

    for lev in LEVERAGES:
        r = results[lev]
        ev = r["ev_per_trade"]
        trades_yr = r["total_trades"] / 8.6
        annual_ev = ev * trades_yr
        print(f"  {lev:>4}x: EV={ev:>+6.1f}$/trade × {trades_yr:.0f}t/any = {annual_ev:>+7.0f}$/any  "
              f"(cap final={r['capital_final']:.0f}$, liq={r['liquidated_pct']:.0f}%)")

    # ────────────────────────────────────────────────────────
    # RECOMANACIÓ
    # ────────────────────────────────────────────────────────
    print(f"\n{'█' * 90}")
    print("RECOMANACIÓ LEVERAGE MVP")
    print(f"{'█' * 90}")

    # Criteri: max EV amb liquidació < 20% i max DD < 50%
    candidates = []
    for lev in LEVERAGES:
        r = results[lev]
        if r["liquidated_pct"] <= 20 and r["max_dd_pct"] <= 60:
            candidates.append((lev, r))

    if candidates:
        # Sort by EV descending
        candidates.sort(key=lambda x: x[1]["ev_per_trade"], reverse=True)
        best_lev, best = candidates[0]
        runner_lev, runner = candidates[1] if len(candidates) > 1 else (None, None)

        print(f"\n  RECOMANAT:  {best_lev}x")
        print(f"    Liquidacions: {best['liquidated_pct']:.0f}%")
        print(f"    WR: {best['wr']:.0f}% | PF: {best['pf']:.1f}")
        print(f"    EV/trade: {best['ev_per_trade']:+.1f}$")
        print(f"    Capital: 250$ → {best['capital_final']:.0f}$ (x{best['capital_x']:.1f})")
        print(f"    Max DD: {best['max_dd_pct']:.0f}%")
        print(f"    Anys: {best['pos_years']}+ / {best['neg_years']}-")

        if runner:
            print(f"\n  RUNNER-UP:  {runner_lev}x")
            print(f"    Liquidacions: {runner['liquidated_pct']:.0f}%")
            print(f"    EV/trade: {runner['ev_per_trade']:+.1f}$")
            print(f"    Capital: 250$ → {runner['capital_final']:.0f}$ (x{runner['capital_x']:.1f})")
            print(f"    Max DD: {runner['max_dd_pct']:.0f}%")
    else:
        print("\n  CAP LEVERAGE COMPLEIX CRITERIS (liq<20%, DD<50%)")
        print("  Considerar augmentar col·lateral o reduir leverage més")
        best_lev = 10
        best = results[10]

    # ────────────────────────────────────────────────────────
    # SAVE ARTIFACT
    # ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    artifact = {
        "task": "T1_recalibrar_leverage",
        "date": datetime.now(timezone.utc).isoformat(),
        "total_signals": len(all_trades),
        "leverages_tested": LEVERAGES,
        "results": {str(k): v for k, v in results.items()},
        "recommended_leverage": best_lev,
        "criteria": "max EV amb liquidació <= 20% i max DD <= 60%",
    }
    # Convert non-serializable
    for k, v in artifact["results"].items():
        if "yearly" in v:
            v["yearly"] = {str(yr): yd for yr, yd in v["yearly"].items()}

    with open(args.out, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    print(f"\n  Artifact guardat: {args.out}")


if __name__ == "__main__":
    main()
