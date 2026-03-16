"""
t6_explore_setups.py — T6: Explorar i validar 6 setups nous amb el harness

3 famílies × 2 hipòtesis = 6 candidates + Capitulation (referència)

Ús:
  python3 lab/studies/t6_explore_setups.py --cache /tmp/crypto_1h_cache.pkl
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
from lab.setups.signal_generators import SETUP_GENERATORS, _all_moves


# ══════════════════════════════════════════════════════════════
# SETUP SPECS
# ══════════════════════════════════════════════════════════════

SPECS = {
    "f1a_bb_squeeze_breakout": SetupSpec(
        name="f1a_bb_squeeze_breakout", family=SetupFamily.BREAKOUT,
        thesis="BB width comprimida (P25) durant 5 candles + close > BB upper → expansió LONG",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("BB width < P25 durant 5 candles", "close > BB upper", "body > 0.5%"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("BB(20,2) width", "BB upper"),
    ),
    "f1b_atr_low_big_candle": SetupSpec(
        name="f1b_atr_low_big_candle", family=SetupFamily.BREAKOUT,
        thesis="ATR(14) baixa (< 0.8x mitjana) + candle body > 2x ATR → impuls d'expansió LONG",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("ATR(14) < 0.8x mean", "body > 2x ATR", "candle verda"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("ATR(14)", "ATR relative"),
    ),
    "f2a_sweep_reclaim": SetupSpec(
        name="f2a_sweep_reclaim", family=SetupFamily.MEAN_REVERSION,
        thesis="Low actual < low(4) però close > low(4) → false breakdown, smart money compra",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("low < rolling_low(4)", "close > rolling_low(4)", "candle verda"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("rolling_low(4)",),
    ),
    "f2b_hammer": SetupSpec(
        name="f2b_hammer", family=SetupFamily.PATTERN,
        thesis="Hammer (wick inf >60% rang, close terç superior) prop BB lower → rebuig mínims",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("lower_wick > 60% range", "close > 67% range", "prop BB lower"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("wick ratio", "BB lower"),
    ),
    "f3a_trend_rsi_dip": SetupSpec(
        name="f3a_trend_rsi_dip", family=SetupFamily.MOMENTUM,
        thesis="Uptrend (EMA20>50>200) + RSI(14)<40 → pullback temporal, rebot en tendència",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("EMA20 > EMA50 > EMA200", "close > EMA50", "RSI(14) < 40"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("EMA(20,50,200)", "RSI(14)"),
    ),
    "f3b_pullback_ema20": SetupSpec(
        name="f3b_pullback_ema20", family=SetupFamily.MOMENTUM,
        thesis="Uptrend (EMA20>EMA50) + preu toca EMA20 + candle verda → continuació",
        direction="LONG", assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
        tf_context="4h", tf_execution="1h",
        entry_conditions=("EMA20 > EMA50", "close prop EMA20 (<0.5%) o low<=EMA20", "candle verda"),
        exit_rule_baseline="close_of_execution_candle",
        features_used=("EMA(20,50)",),
    ),
}


def load_data(cache_path: str) -> dict[str, pd.DataFrame]:
    with open(cache_path, "rb") as f:
        raw = pickle.load(f)
    return {sym.replace("USDT", ""): pd.DataFrame(rows).set_index("ts")
            for sym, rows in raw.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="/tmp/crypto_1h_cache.pkl")
    args = parser.parse_args()

    print("=" * 90)
    print("T6: EXPLORAR NOUS SETUPS — 3 famílies × 2 hipòtesis")
    print("=" * 90)

    all_data = load_data(args.cache)
    config = HarnessConfig(leverage_deployable=20)

    # Pre-compute all candle moves per MC random
    all_candle_moves = {}
    for name, df in all_data.items():
        all_candle_moves[name] = _all_moves(df)

    # ── Run all setups ──
    all_results = []

    for setup_name, gen_fn in SETUP_GENERATORS.items():
        spec = SPECS[setup_name]
        print(f"\n{'─' * 90}")
        print(f"  {setup_name}: {spec.thesis[:70]}...")

        # Generate trades
        trades = []
        for asset_name, df in all_data.items():
            t = gen_fn(df, asset_name)
            trades.extend(t)
            print(f"    {asset_name}: {len(t)} trades")

        if len(trades) < 10:
            print(f"    SKIP: massa pocs trades ({len(trades)})")
            all_results.append({
                "name": setup_name, "family": spec.family.value,
                "n": len(trades), "status": "rejected",
                "reason": f"N={len(trades)} < 10", "result": None,
            })
            continue

        # Run harness
        result, artifact = validate_setup(spec, trades, all_candle_moves, config)
        path = save_artifact(artifact, setup_name)

        # Store
        all_results.append({
            "name": setup_name, "family": spec.family.value,
            "n": result.sample_size,
            "wr_baseline": artifact["baseline"]["win_rate"],
            "pf_baseline": artifact["baseline"]["profit_factor"],
            "ev_baseline": artifact["baseline"]["ev_per_trade"],
            "wr_deploy": artifact["deployable"]["win_rate"],
            "pf_deploy": artifact["deployable"]["profit_factor"],
            "ev_deploy": artifact["deployable"]["ev_per_trade"],
            "liq_pct": artifact["deployable"].get("liq_rate_pct", 0),
            "cap_final": artifact["deployable"].get("capital_final", 0),
            "mc_shuffle": artifact["mc_shuffle"]["pct_profitable"],
            "mc_edge": artifact["mc_random_edge_pp"],
            "wf_exp": f"{artifact['wf_expanding']['positive']}/{artifact['wf_expanding']['total']}",
            "wf_roll": f"{artifact['wf_rolling']['positive']}/{artifact['wf_rolling']['total']}",
            "status": result.status.value,
            "reason": result.decision_reason[:60],
            "result": result,
        })
        print(f"    → {result.status.upper()}: {result.decision_reason[:60]}")

    # ══════════════════════════════════════════════════════════
    # TAULA COMPARATIVA
    # ══════════════════════════════════════════════════════════
    print(f"\n\n{'█' * 90}")
    print("TAULA COMPARATIVA T6 (+ Capitulation referència)")
    print(f"{'█' * 90}")

    print(f"\n{'Setup':<28} {'Fam':<12} {'N':>5} {'WR_b':>5} {'PF_b':>5} {'EV_b':>7} "
          f"{'WR_d':>5} {'PF_d':>5} {'EV_d':>7} {'Liq%':>5} {'MC%':>5} {'Edge':>5} "
          f"{'WF_e':>5} {'WF_r':>5} {'Status':<12}")
    print(f"{'─' * 135}")

    # Add capitulation reference
    print(f"{'capitulation_scalp_1h':<28} {'capitul.':<12} {'361':>5} {'67.9':>5} {'2.94':>5} {'+50.8':>7} "
          f"{'57.2':>5} {'1.3':>5} {'+4.0':>7} {'15.1':>5} {'100':>5} {'+24.6':>5} "
          f"{'8/10':>5} {'5/7':>5} {'WATCHLIST':<12}")

    for r in all_results:
        if r["result"] is None:
            print(f"{r['name']:<28} {r['family']:<12} {r['n']:>5} {'—':>5} {'—':>5} {'—':>7} "
                  f"{'—':>5} {'—':>5} {'—':>7} {'—':>5} {'—':>5} {'—':>5} "
                  f"{'—':>5} {'—':>5} {r['status'].upper():<12}")
        else:
            print(f"{r['name']:<28} {r['family']:<12} {r['n']:>5} "
                  f"{r['wr_baseline']:>5.1f} {r['pf_baseline']:>5.2f} {r['ev_baseline']:>+7.1f} "
                  f"{r['wr_deploy']:>5.1f} {r['pf_deploy']:>5.2f} {r['ev_deploy']:>+7.1f} "
                  f"{r['liq_pct']:>5.1f} {r['mc_shuffle']:>5.0f} {r['mc_edge']:>+5.1f} "
                  f"{r['wf_exp']:>5} {r['wf_roll']:>5} {r['status'].upper():<12}")

    # ── Top candidates ──
    viable = [r for r in all_results if r["result"] is not None and r["status"] != "rejected"]
    viable.sort(key=lambda r: r.get("ev_deploy", 0), reverse=True)

    print(f"\n\n{'=' * 90}")
    print("TOP CANDIDATES PER T7")
    print(f"{'=' * 90}")
    if viable:
        for i, r in enumerate(viable[:3], 1):
            print(f"\n  #{i}: {r['name']} ({r['family']})")
            print(f"      EV deploy={r['ev_deploy']:+.1f}$/t | WR={r['wr_deploy']:.0f}% | PF={r['pf_deploy']:.2f}")
            print(f"      MC={r['mc_shuffle']:.0f}% | Edge={r['mc_edge']:+.1f}pp | WF={r['wf_exp']}")
            print(f"      Status: {r['status'].upper()}")
    else:
        print("\n  Cap candidata ha sobreviscut al harness.")
        print("  Considerar: relaxar condicions, nous indicadors, o altres famílies.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
