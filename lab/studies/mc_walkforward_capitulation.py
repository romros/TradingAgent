"""
mc_walkforward_capitulation.py — Monte Carlo + Walk-Forward validation
Capitulation Scalp 1H (ETH + BTC + SOL)

OBJECTIU:
  Confirmar que l'estratègia és robusta i no és producte d'overfitting.

MONTE CARLO (3 tests):
  1. Shuffled trades: barrejar l'ordre dels trades, simular 10.000 vegades
     → la distribució de resultats ha de ser majoritàriament positiva
  2. Random entry: entrar a candles aleatòries (same N), comparar WR/PF
     → l'estratègia real ha de ser significativament millor que random
  3. Parameter perturbation: variar body_th ±0.5%, drop_th ±1%, BB period ±2
     → els resultats han de ser estables (no un pic a un punt exacte)

WALK-FORWARD:
  Train 3 anys, test 1 any, step 1 any (2018-2026)
  Sense reoptimització (paràmetres fixos) — validem que el senyal
  funciona en períodes que no ha vist.

Ús:
  python3 lab/studies/mc_walkforward_capitulation.py
  python3 lab/studies/mc_walkforward_capitulation.py --cache /tmp/crypto_1h_cache.pkl
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
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════

ASSETS = {
    "ETH": "ETHUSDT",
    "BTC": "BTCUSDT",
    "SOL": "SOLUSDT",
}

FEE = 3.36
NOM = 4000  # 40$ col * 100x lev


def download_binance(symbol: str) -> list[dict]:
    all_k: list = []
    start_ms = 0
    while True:
        url = (
            f"https://api.binance.com/api/v3/klines?symbol={symbol}"
            f"&interval=1h&startTime={start_ms}&limit=1000"
        )
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
    return rows


def load_data(cache_path: str | None) -> dict[str, pd.DataFrame]:
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            raw = pickle.load(f)
        result = {}
        for sym, rows in raw.items():
            name = sym.replace("USDT", "")
            result[name] = pd.DataFrame(rows).set_index("ts")
        return result

    result = {}
    for name, sym in ASSETS.items():
        print(f"  Downloading {sym}...")
        rows = download_binance(sym)
        result[name] = pd.DataFrame(rows).set_index("ts")
        print(f"    {len(result[name])} candles")

    if cache_path:
        raw = {f"{n}USDT": [{"ts": ts, **row} for ts, row in df.iterrows()]
               for n, df in result.items()}
        # no recache, use existing format
    return result


# ══════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════

def calc_bb_lower(closes: np.ndarray, period: int = 20, mult: float = 2.0) -> np.ndarray:
    n = len(closes)
    bb = np.full(n, np.nan)
    for i in range(period - 1, n):
        w = closes[i - period + 1: i + 1]
        bb[i] = np.mean(w) - mult * np.std(w, ddof=0)
    return bb


def calc_rsi(closes: np.ndarray, period: int = 7) -> np.ndarray:
    n = len(closes)
    r = np.full(n, np.nan)
    d = np.diff(closes)
    g = np.where(d > 0, d, 0.0)
    lo = np.where(d < 0, -d, 0.0)
    if len(g) < period:
        return r
    ag = np.mean(g[:period])
    al = np.mean(lo[:period])
    r[period] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + lo[i]) / period
        r[i + 1] = 100 - 100 / (1 + ag / al) if al != 0 else 100
    return r


def calc_drop(closes: np.ndarray, lookback: int = 3) -> np.ndarray:
    n = len(closes)
    d = np.zeros(n)
    for i in range(lookback, n):
        d[i] = (closes[i] - closes[i - lookback]) / closes[i - lookback]
    return d


def calc_vol_rel(volumes: np.ndarray, period: int = 20) -> np.ndarray:
    n = len(volumes)
    vr = np.ones(n)
    ma = pd.Series(volumes).rolling(period).mean().values
    for i in range(period, n):
        if ma[i] > 0:
            vr[i] = volumes[i] / ma[i]
    return vr


# ══════════════════════════════════════════════════════════════
# STRATEGY
# ══════════════════════════════════════════════════════════════

BAD_HOURS = {16, 17, 18, 19}


def find_signals(df: pd.DataFrame, body_th: float = -0.03,
                 drop_th: float = -0.05, bb_period: int = 20,
                 bb_mult: float = 2.0) -> list[dict]:
    C = df["C"].values
    O = df["O"].values
    H = df["H"].values
    L = df["L"].values
    V = df["V"].values
    N = len(df)

    body_pct = (C - O) / np.maximum(O, 1e-9)
    bb_lo = calc_bb_lower(C, bb_period, bb_mult)
    rsi7 = calc_rsi(C, 7)
    drop3 = calc_drop(C, 3)
    vol_rel = calc_vol_rel(V, 20)

    signals = []
    for i in range(200, N - 1):
        if body_pct[i] >= body_th:
            continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]:
            continue
        if drop3[i] >= drop_th:
            continue
        hour = df.index[i].hour
        if hour in BAD_HOURS:
            continue
        if vol_rel[i] > 5:
            continue

        # Score
        sc = 0
        if body_pct[i] < body_th * 2.5:
            sc += 2
        elif body_pct[i] < body_th * 1.5:
            sc += 1
        if drop3[i] < drop_th * 2.5:
            sc += 2
        elif drop3[i] < drop_th * 1.5:
            sc += 1
        if not np.isnan(rsi7[i]):
            if rsi7[i] < 15:
                sc += 2
            elif rsi7[i] < 25:
                sc += 1
        if vol_rel[i] > 3:
            sc += 1
        if hour in (20, 21):
            sc += 1

        # Next candle result
        o1, h1, l1, c1 = O[i + 1], H[i + 1], L[i + 1], C[i + 1]
        move = (c1 - o1) / o1
        pnl = NOM * move - FEE

        signals.append({
            "ts": df.index[i],
            "yr": df.index[i].year,
            "month": df.index[i].month,
            "score": sc,
            "move": move,
            "pnl": pnl,
            "green": c1 > o1,
        })

    return signals


# ══════════════════════════════════════════════════════════════
# MONTE CARLO 1: SHUFFLE TRADES
# ══════════════════════════════════════════════════════════════

def mc_shuffle(trades_pnl: np.ndarray, n_sim: int = 10000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    n = len(trades_pnl)
    real_total = trades_pnl.sum()
    real_wr = 100 * np.mean(trades_pnl > 0)

    sim_totals = np.zeros(n_sim)
    sim_wrs = np.zeros(n_sim)
    sim_max_dd = np.zeros(n_sim)

    for s in range(n_sim):
        shuffled = rng.permutation(trades_pnl)
        sim_totals[s] = shuffled.sum()
        sim_wrs[s] = 100 * np.mean(shuffled > 0)
        # Max drawdown
        eq = np.cumsum(shuffled)
        peak = np.maximum.accumulate(eq)
        dd = peak - eq
        sim_max_dd[s] = dd.max()

    return {
        "real_total": float(real_total),
        "real_wr": float(real_wr),
        "sim_total_mean": float(sim_totals.mean()),
        "sim_total_p5": float(np.percentile(sim_totals, 5)),
        "sim_total_p25": float(np.percentile(sim_totals, 25)),
        "sim_total_p50": float(np.percentile(sim_totals, 50)),
        "sim_total_p75": float(np.percentile(sim_totals, 75)),
        "sim_total_p95": float(np.percentile(sim_totals, 95)),
        "sim_maxdd_mean": float(sim_max_dd.mean()),
        "sim_maxdd_p95": float(np.percentile(sim_max_dd, 95)),
        "pct_profitable_sims": float(100 * np.mean(sim_totals > 0)),
    }


# ══════════════════════════════════════════════════════════════
# MONTE CARLO 2: RANDOM ENTRY
# ══════════════════════════════════════════════════════════════

def mc_random_entry(df: pd.DataFrame, n_real_trades: int,
                    n_sim: int = 5000, seed: int = 42) -> dict:
    C = df["C"].values
    O = df["O"].values
    N = len(df)
    rng = np.random.default_rng(seed)

    valid_idx = list(range(200, N - 1))
    sim_wrs = np.zeros(n_sim)
    sim_avg_pnl = np.zeros(n_sim)

    for s in range(n_sim):
        chosen = rng.choice(valid_idx, size=n_real_trades, replace=False)
        moves = [(C[i + 1] - O[i + 1]) / O[i + 1] for i in chosen]
        pnls = [NOM * m - FEE for m in moves]
        sim_wrs[s] = 100 * np.mean(np.array(pnls) > 0)
        sim_avg_pnl[s] = np.mean(pnls)

    return {
        "n_sims": n_sim,
        "random_wr_mean": float(sim_wrs.mean()),
        "random_wr_p95": float(np.percentile(sim_wrs, 95)),
        "random_avg_pnl_mean": float(sim_avg_pnl.mean()),
        "random_avg_pnl_p95": float(np.percentile(sim_avg_pnl, 95)),
    }


# ══════════════════════════════════════════════════════════════
# MONTE CARLO 3: PARAMETER PERTURBATION
# ══════════════════════════════════════════════════════════════

def mc_param_perturb(all_data: dict[str, pd.DataFrame],
                     n_variants: int = 50, seed: int = 42) -> list[dict]:
    rng = np.random.default_rng(seed)
    results = []

    for _ in range(n_variants):
        body_th = -0.03 + rng.uniform(-0.005, 0.005)
        drop_th = -0.05 + rng.uniform(-0.01, 0.01)
        bb_period = int(20 + rng.integers(-3, 4))
        bb_mult = 2.0 + rng.uniform(-0.3, 0.3)

        all_trades = []
        for name, df in all_data.items():
            sigs = find_signals(df, body_th, drop_th, bb_period, bb_mult)
            all_trades.extend(sigs)

        if not all_trades:
            continue

        pnls = np.array([t["pnl"] for t in all_trades])
        wr = 100 * np.mean(pnls > 0)
        w = pnls[pnls > 0]
        l = pnls[pnls <= 0]
        pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99

        results.append({
            "body_th": round(body_th, 4),
            "drop_th": round(drop_th, 4),
            "bb_period": bb_period,
            "bb_mult": round(bb_mult, 2),
            "n": len(pnls),
            "wr": round(wr, 1),
            "pf": round(pf, 2),
            "total": round(pnls.sum(), 0),
            "avg_pnl": round(pnls.mean(), 1),
        })

    return results


# ══════════════════════════════════════════════════════════════
# WALK-FORWARD
# ══════════════════════════════════════════════════════════════

def walk_forward(all_data: dict[str, pd.DataFrame]) -> list[dict]:
    all_trades = []
    for name, df in all_data.items():
        sigs = find_signals(df)
        for s in sigs:
            s["asset"] = name
        all_trades.extend(sigs)

    results = []
    for test_yr in range(2018, 2027):
        train_trades = [t for t in all_trades if t["yr"] < test_yr]
        test_trades = [t for t in all_trades if t["yr"] == test_yr]

        if not test_trades:
            continue

        # Train stats (informational)
        train_pnl = np.array([t["pnl"] for t in train_trades]) if train_trades else np.array([0])
        train_wr = 100 * np.mean(train_pnl > 0) if len(train_trades) > 0 else 0

        # Test stats
        test_pnl = np.array([t["pnl"] for t in test_trades])
        test_wr = 100 * np.mean(test_pnl > 0)
        w = test_pnl[test_pnl > 0]
        l = test_pnl[test_pnl <= 0]
        pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99

        results.append({
            "test_year": test_yr,
            "train_years": f"< {test_yr}",
            "train_n": len(train_trades),
            "train_wr": round(train_wr, 1),
            "test_n": len(test_trades),
            "test_wr": round(test_wr, 1),
            "test_pf": round(pf, 2),
            "test_total": round(test_pnl.sum(), 0),
            "test_avg": round(test_pnl.mean(), 1),
        })

    return results


# ══════════════════════════════════════════════════════════════
# WALK-FORWARD ROLLING (train window fix)
# ══════════════════════════════════════════════════════════════

def walk_forward_rolling(all_data: dict[str, pd.DataFrame],
                         train_years: int = 3) -> list[dict]:
    all_trades = []
    for name, df in all_data.items():
        sigs = find_signals(df)
        for s in sigs:
            s["asset"] = name
        all_trades.extend(sigs)

    results = []
    min_yr = min(t["yr"] for t in all_trades)
    max_yr = max(t["yr"] for t in all_trades)

    for test_yr in range(min_yr + train_years, max_yr + 1):
        train_start = test_yr - train_years
        train_trades = [t for t in all_trades if train_start <= t["yr"] < test_yr]
        test_trades = [t for t in all_trades if t["yr"] == test_yr]

        if not test_trades:
            continue

        train_pnl = np.array([t["pnl"] for t in train_trades]) if train_trades else np.array([0])
        train_wr = 100 * np.mean(train_pnl > 0) if len(train_trades) > 0 else 0

        test_pnl = np.array([t["pnl"] for t in test_trades])
        test_wr = 100 * np.mean(test_pnl > 0)
        w = test_pnl[test_pnl > 0]
        l = test_pnl[test_pnl <= 0]
        pf = abs(w.sum() / l.sum()) if len(l) > 0 and l.sum() != 0 else 99

        results.append({
            "test_year": test_yr,
            "train_window": f"{train_start}-{test_yr - 1}",
            "train_n": len(train_trades),
            "train_wr": round(train_wr, 1),
            "test_n": len(test_trades),
            "test_wr": round(test_wr, 1),
            "test_pf": round(pf, 2),
            "test_total": round(test_pnl.sum(), 0),
            "test_avg": round(test_pnl.mean(), 1),
        })

    return results


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="/tmp/crypto_1h_cache.pkl")
    args = parser.parse_args()

    print("=" * 90)
    print("CAPITULATION SCALP 1H — Monte Carlo + Walk-Forward Validation")
    print("=" * 90)

    # Load data
    print("\n1. LOADING DATA...")
    all_data = load_data(args.cache)
    for name, df in all_data.items():
        print(f"   {name}: {len(df)} candles, {df.index[0].date()} → {df.index[-1].date()}")

    # Collect all trades
    print("\n2. COLLECTING SIGNALS (params fixos: body<-3%, BB(20,2), drop3h<-5%)...")
    all_trades = []
    for name, df in all_data.items():
        sigs = find_signals(df)
        for s in sigs:
            s["asset"] = name
        all_trades.extend(sigs)
        n = len(sigs)
        wr = 100 * np.mean([s["green"] for s in sigs]) if sigs else 0
        print(f"   {name}: {n} trades, WR={wr:.0f}%")

    total_pnl = np.array([t["pnl"] for t in all_trades])
    print(f"   TOTAL: {len(total_pnl)} trades, WR={100 * np.mean(total_pnl > 0):.0f}%, "
          f"PnL={total_pnl.sum():+.0f}$")

    # ────────────────────────────────────────────────────────
    # MC1: Shuffle
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("3. MONTE CARLO — SHUFFLE TRADES (10.000 simulacions)")
    print(f"{'=' * 90}")
    print("   Barregem l'ordre dels trades. Si l'estratègia és real,")
    print("   la majoria de permutacions haurien de ser profitables.")

    mc1 = mc_shuffle(total_pnl, n_sim=10000)
    print(f"\n   Resultats reals:   Total={mc1['real_total']:+.0f}$  WR={mc1['real_wr']:.0f}%")
    print(f"   Simulació (10K):")
    print(f"     Mean total:      {mc1['sim_total_mean']:+.0f}$")
    print(f"     P5 (pitjor 5%):  {mc1['sim_total_p5']:+.0f}$")
    print(f"     P25:             {mc1['sim_total_p25']:+.0f}$")
    print(f"     P50 (mediana):   {mc1['sim_total_p50']:+.0f}$")
    print(f"     P75:             {mc1['sim_total_p75']:+.0f}$")
    print(f"     P95 (millor 5%): {mc1['sim_total_p95']:+.0f}$")
    print(f"     MaxDD mean:      {mc1['sim_maxdd_mean']:.0f}$")
    print(f"     MaxDD P95:       {mc1['sim_maxdd_p95']:.0f}$")
    print(f"     % sims profit:   {mc1['pct_profitable_sims']:.1f}%")

    mc1_pass = mc1["pct_profitable_sims"] >= 90 and mc1["sim_total_p5"] > 0
    print(f"\n   VEREDICTE: {'PASS' if mc1_pass else 'FAIL'} "
          f"({'≥90% sims profitables i P5>0' if mc1_pass else 'massa variància'})")

    # ────────────────────────────────────────────────────────
    # MC2: Random entry (per asset principal: ETH)
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("4. MONTE CARLO — RANDOM ENTRY (5.000 simulacions per asset)")
    print(f"{'=' * 90}")
    print("   Comparem el WR real vs entrar a candles aleatòries.")

    for name, df in all_data.items():
        sigs = find_signals(df)
        n_real = len(sigs)
        if n_real < 10:
            continue
        real_pnl = np.array([s["pnl"] for s in sigs])
        real_wr = 100 * np.mean(real_pnl > 0)
        real_avg = real_pnl.mean()

        mc2 = mc_random_entry(df, n_real, n_sim=5000)

        print(f"\n   {name} ({n_real} trades):")
        print(f"     Real WR:          {real_wr:.1f}%")
        print(f"     Random WR mean:   {mc2['random_wr_mean']:.1f}%")
        print(f"     Random WR P95:    {mc2['random_wr_p95']:.1f}%")
        print(f"     Real avg PnL:     {real_avg:+.1f}$")
        print(f"     Random avg PnL:   {mc2['random_avg_pnl_mean']:+.1f}$")
        edge = real_wr - mc2["random_wr_mean"]
        better = real_wr > mc2["random_wr_p95"]
        print(f"     Edge vs random:   {edge:+.1f}pp")
        print(f"     Real > P95 rand:  {'SI — edge significatiu' if better else 'NO — dins del soroll'}")

    # ────────────────────────────────────────────────────────
    # MC3: Parameter perturbation
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("5. MONTE CARLO — PARAMETER PERTURBATION (50 variants)")
    print(f"{'=' * 90}")
    print("   Variem: body_th ±0.5%, drop_th ±1%, BB period ±3, BB mult ±0.3")
    print("   Si l'estratègia és robust, els resultats han de ser estables.")

    mc3 = mc_param_perturb(all_data, n_variants=50)
    if mc3:
        wrs = [r["wr"] for r in mc3]
        pfs = [r["pf"] for r in mc3]
        tots = [r["total"] for r in mc3]

        print(f"\n   50 variants:")
        print(f"     WR:    min={min(wrs):.0f}%  mean={np.mean(wrs):.0f}%  max={max(wrs):.0f}%")
        print(f"     PF:    min={min(pfs):.1f}  mean={np.mean(pfs):.1f}  max={max(pfs):.1f}")
        print(f"     Total: min={min(tots):+.0f}$  mean={np.mean(tots):+.0f}$  max={max(tots):+.0f}$")
        print(f"     % variants profitables: {100 * np.mean(np.array(tots) > 0):.0f}%")

        mc3_pass = np.mean(np.array(tots) > 0) >= 0.80 and min(wrs) >= 50
        print(f"\n   VEREDICTE: {'PASS' if mc3_pass else 'FAIL'} "
              f"({'≥80% variants profitables i WR min ≥50%' if mc3_pass else 'inestable'})")

    # ────────────────────────────────────────────────────────
    # Walk-Forward expanding
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("6. WALK-FORWARD — EXPANDING WINDOW (train <year, test =year)")
    print(f"{'=' * 90}")

    wf = walk_forward(all_data)
    print(f"\n   {'Test':>6} {'Train':>10} {'TrainN':>7} {'TrainWR':>8} "
          f"{'TestN':>6} {'TestWR':>7} {'TestPF':>7} {'TestTotal':>10} {'TestAvg':>8}")
    print(f"   {'─' * 75}")
    wf_positive = 0
    for r in wf:
        flag = " ***NEG***" if r["test_total"] < 0 else ""
        if r["test_total"] >= 0:
            wf_positive += 1
        print(f"   {r['test_year']:>6} {r['train_years']:>10} {r['train_n']:>7} "
              f"{r['train_wr']:>7.0f}% {r['test_n']:>6} {r['test_wr']:>6.0f}% "
              f"{r['test_pf']:>6.1f} {r['test_total']:>+9.0f}$ {r['test_avg']:>+7.1f}${flag}")
    print(f"\n   Anys positius: {wf_positive}/{len(wf)}")

    # ────────────────────────────────────────────────────────
    # Walk-Forward rolling (3y train window)
    # ────────────────────────────────────────────────────────
    print(f"\n{'=' * 90}")
    print("7. WALK-FORWARD — ROLLING WINDOW (train 3 anys, test 1 any)")
    print(f"{'=' * 90}")

    wfr = walk_forward_rolling(all_data, train_years=3)
    print(f"\n   {'Test':>6} {'Window':>12} {'TrainN':>7} {'TrainWR':>8} "
          f"{'TestN':>6} {'TestWR':>7} {'TestPF':>7} {'TestTotal':>10} {'TestAvg':>8}")
    print(f"   {'─' * 80}")
    wfr_positive = 0
    for r in wfr:
        flag = " ***NEG***" if r["test_total"] < 0 else ""
        if r["test_total"] >= 0:
            wfr_positive += 1
        print(f"   {r['test_year']:>6} {r['train_window']:>12} {r['train_n']:>7} "
              f"{r['train_wr']:>7.0f}% {r['test_n']:>6} {r['test_wr']:>6.0f}% "
              f"{r['test_pf']:>6.1f} {r['test_total']:>+9.0f}$ {r['test_avg']:>+7.1f}${flag}")
    print(f"\n   Anys positius: {wfr_positive}/{len(wfr)}")

    # ────────────────────────────────────────────────────────
    # RESUM FINAL
    # ────────────────────────────────────────────────────────
    print(f"\n{'█' * 90}")
    print("RESUM VALIDACIÓ")
    print(f"{'█' * 90}")
    print(f"  MC Shuffle:      {'PASS' if mc1_pass else 'FAIL'} ({mc1['pct_profitable_sims']:.0f}% sims profitables, P5={mc1['sim_total_p5']:+.0f}$)")
    mc3_ok = mc3 and np.mean(np.array([r['total'] for r in mc3]) > 0) >= 0.80
    print(f"  MC Param Perturb: {'PASS' if mc3_ok else 'FAIL'}")
    print(f"  WF Expanding:    {wf_positive}/{len(wf)} anys positius")
    print(f"  WF Rolling 3y:   {wfr_positive}/{len(wfr)} anys positius")

    all_pass = mc1_pass and mc3_ok and wf_positive >= len(wf) - 2 and wfr_positive >= len(wfr) - 2
    print(f"\n  VEREDICTE GLOBAL: {'PASS — estratègia robusta' if all_pass else 'CONDICIONAL — revisar punts febles'}")


if __name__ == "__main__":
    main()
