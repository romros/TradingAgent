"""
smoke_capitulation.py — Smoke test: validar Capitulation Scalp 1H amb el harness

Ús:
  python3 lab/harness/smoke_capitulation.py --cache /tmp/crypto_1h_cache.pkl
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lab.contracts.models import SetupSpec, SetupFamily
from lab.harness.core import TradeRecord
from lab.harness.runner import HarnessConfig, validate_setup, save_artifact, print_summary


# ══════════════════════════════════════════════════════════════
# DATA + SIGNALS (same logic as studies)
# ══════════════════════════════════════════════════════════════

BAD_HOURS = {16, 17, 18, 19}


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


def generate_signals(df: pd.DataFrame, asset: str) -> tuple[list[TradeRecord], np.ndarray]:
    """Genera trades + all_moves per MC random entry."""
    C = df["C"].values; O = df["O"].values; H = df["H"].values; L = df["L"].values
    V = df["V"].values; N = len(df)
    body_pct = (C - O) / np.maximum(O, 1e-9)
    bb_lo = calc_bb_lower(C); rsi7 = calc_rsi(C); drop3 = calc_drop(C)
    vol_ma = pd.Series(V).rolling(20).mean().values
    vol_rel = V / np.maximum(vol_ma, 1)

    trades = []
    all_moves = []

    for i in range(200, N - 1):
        # All moves per MC random
        all_moves.append((C[i + 1] - O[i + 1]) / O[i + 1])

        # Setup conditions
        if body_pct[i] >= -0.03: continue
        if np.isnan(bb_lo[i]) or C[i] >= bb_lo[i]: continue
        if drop3[i] >= -0.05: continue
        hour = df.index[i].hour
        if hour in BAD_HOURS or vol_rel[i] > 5: continue

        # Score
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

        trades.append(TradeRecord(
            ts=df.index[i].isoformat(),
            year=df.index[i].year,
            asset=asset,
            score=sc,
            move=move,
            mae=mae,
            mfe=mfe,
            green=c1 > o1,
        ))

    return trades, np.array(all_moves)


# ══════════════════════════════════════════════════════════════
# SPEC
# ══════════════════════════════════════════════════════════════

SPEC = SetupSpec(
    name="capitulation_scalp_1h",
    version="1.0",
    family=SetupFamily.CAPITULATION,
    thesis="Rebot de capitulació: crash extrem 1H → bounce",
    direction="LONG",
    assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
    tf_context="4h",
    tf_execution="1h",
    entry_conditions=(
        "body_pct < -3%",
        "close < BB_lower(20, 2.0)",
        "drop_3h < -5%",
        "hour NOT IN {16,17,18,19}",
        "vol_rel <= 5",
    ),
    exit_rule_baseline="close_of_execution_candle",
    features_used=("BB_lower(20,2)", "RSI(7)", "drop_3h", "vol_rel_20"),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="/tmp/crypto_1h_cache.pkl")
    args = parser.parse_args()

    print("=" * 80)
    print("T5 SMOKE TEST: Capitulation Scalp 1H via harness")
    print("=" * 80)

    all_data = load_data(args.cache)
    all_trades = []
    all_candle_moves = {}

    for name, df in all_data.items():
        trades, moves = generate_signals(df, name)
        all_trades.extend(trades)
        all_candle_moves[name] = moves
        print(f"  {name}: {len(trades)} trades, {len(moves)} candles totals")

    print(f"  TOTAL: {len(all_trades)} trades")

    # Run harness
    config = HarnessConfig(leverage_deployable=20)
    result, artifact = validate_setup(SPEC, all_trades, all_candle_moves, config)

    # Print
    print_summary(result, artifact)

    # Save
    path = save_artifact(artifact, SPEC.name)
    print(f"\n  Artifact guardat: {path}")

    # ── Coherence checks ──
    print(f"\n  COHERENCE CHECKS:")
    ok = True

    # Check 1: status should be watchlist (matching T4 catalog)
    if result.status.value != "watchlist":
        print(f"    WARN: status={result.status}, esperat watchlist")
    else:
        print(f"    OK: status=watchlist (coherent amb catàleg T4)")

    # Check 2: MC shuffle should be ~100%
    if result.mc_shuffle_pct_profitable >= 90:
        print(f"    OK: mc_shuffle={result.mc_shuffle_pct_profitable}% >= 90%")
    else:
        print(f"    FAIL: mc_shuffle={result.mc_shuffle_pct_profitable}% < 90%")
        ok = False

    # Check 3: WF expanding should be >= 60%
    wf_pct = result.wf_expanding_positive_years / max(result.wf_expanding_total_years, 1)
    if wf_pct >= 0.60:
        print(f"    OK: wf_expanding={result.wf_expanding_positive_years}/{result.wf_expanding_total_years} >= 60%")
    else:
        print(f"    WARN: wf_expanding={result.wf_expanding_positive_years}/{result.wf_expanding_total_years} < 60%")

    # Check 4: sample size > 300 (matching known ~361)
    if result.sample_size >= 300:
        print(f"    OK: N={result.sample_size} >= 300")
    else:
        print(f"    WARN: N={result.sample_size} < 300")

    # Check 5: baseline EV > 0
    if artifact["baseline"]["ev_per_trade"] > 0:
        print(f"    OK: baseline EV={artifact['baseline']['ev_per_trade']:+.1f}$/t > 0")
    else:
        print(f"    FAIL: baseline EV={artifact['baseline']['ev_per_trade']:+.1f}$/t <= 0")
        ok = False

    print(f"\n  SMOKE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
