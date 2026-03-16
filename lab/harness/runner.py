"""
lab/harness/runner.py — Runner del harness de validació

Pipeline complet: backtest → liquidació → MFE/MAE → MC → WF → classify → artifact

Ús:
  from lab.harness.runner import validate_setup
  result = validate_setup(spec, trades, all_candle_moves, config)

  O com a CLI:
  python3 -m lab.harness.runner --setup capitulation_scalp --cache /tmp/crypto_1h_cache.pkl
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable

import numpy as np

from lab.harness.core import (
    TradeRecord, backtest_baseline, backtest_deployable,
    compute_mfe_mae, compute_liq_rates, mc_shuffle, mc_random_entry,
    walk_forward_expanding, walk_forward_rolling, yearly_breakdown,
    classify_setup,
)
from lab.contracts.models import (
    SetupSpec, SetupValidationResult, SetupStatus,
    LiqRateByLeverage, YearlyBreakdown,
)


@dataclass(slots=True)
class HarnessConfig:
    """Configuració del harness."""
    nominal_baseline: float = 4000.0     # nominal per baseline (sense compounding)
    fee: float = 3.36
    init_capital: float = 250.0
    col_pct: float = 0.20
    col_min: float = 15.0
    col_max: float = 60.0
    leverages_to_test: tuple[int, ...] = (10, 15, 20, 30, 50)
    leverage_deployable: int = 20        # leverage per mètriques deployable
    paper_threshold: int = 2
    mc_n_shuffle: int = 10000
    mc_n_random: int = 5000
    wf_train_window: int = 3
    out_dir: str = "lab/out"


def validate_setup(
    spec: SetupSpec,
    trades: list[TradeRecord],
    all_candle_moves: dict[str, np.ndarray] | None = None,
    config: HarnessConfig | None = None,
) -> tuple[SetupValidationResult, dict]:
    """
    Pipeline complet de validació.

    Args:
        spec: SetupSpec del setup
        trades: llista de TradeRecord generats pel setup
        all_candle_moves: {asset: array de moves de TOTES les candles} per MC random entry
        config: configuració del harness

    Returns:
        (SetupValidationResult, artifact_dict)
    """
    cfg = config or HarnessConfig()
    nom = cfg.nominal_baseline
    fee = cfg.fee

    trades_sorted = sorted(trades, key=lambda t: t.ts)
    n = len(trades_sorted)
    print(f"\n  Validant: {spec.name} ({n} trades)")

    # ── 1. Baseline ──
    print("    [1/7] Backtest baseline...")
    baseline = backtest_baseline(trades_sorted, nom, fee)
    pnls_baseline = np.array([nom * t.move - fee for t in trades_sorted])

    # ── 2. Deployable ──
    print(f"    [2/7] Backtest deployable (lev={cfg.leverage_deployable}x)...")
    deployable = backtest_deployable(
        trades_sorted, cfg.leverage_deployable, fee,
        cfg.col_pct, cfg.col_min, cfg.col_max, cfg.init_capital, cfg.paper_threshold,
    )

    # ── 3. MFE/MAE ──
    print("    [3/7] MFE/MAE...")
    mfe_mae = compute_mfe_mae(trades_sorted)

    # ── 4. Liquidation rates ──
    print(f"    [4/7] Liq rates ({len(cfg.leverages_to_test)} leverages)...")
    liq_rates = compute_liq_rates(trades_sorted, list(cfg.leverages_to_test), fee, cfg.init_capital)

    # ── 5. Monte Carlo ──
    print("    [5/7] Monte Carlo...")
    mc_shuf = mc_shuffle(pnls_baseline, cfg.mc_n_shuffle)

    mc_rand = {"random_wr_mean": 0, "random_wr_p95": 0}
    mc_edge = 0.0
    if all_candle_moves:
        # Combinar tots els assets
        all_moves = np.concatenate(list(all_candle_moves.values()))
        real_wr = baseline["win_rate"]
        mc_rand = mc_random_entry(all_moves, n, nom, fee, cfg.mc_n_random)
        mc_edge = round(real_wr - mc_rand["random_wr_mean"], 1)

    # ── 6. Walk-Forward ──
    print("    [6/7] Walk-forward...")
    wf_exp = walk_forward_expanding(trades_sorted, nom, fee)
    wf_roll = walk_forward_rolling(trades_sorted, nom, fee, cfg.wf_train_window)

    # ── 7. Classify ──
    print("    [7/7] Classificació...")
    status_str, reason = classify_setup(deployable, mc_shuf, mc_rand, wf_exp, wf_roll)

    # ── Yearly ──
    yearly = yearly_breakdown(trades_sorted, nom, fee)

    # ── Build SetupValidationResult ──
    period_start = trades_sorted[0].ts[:10] if trades_sorted else ""
    period_end = trades_sorted[-1].ts[:10] if trades_sorted else ""

    result = SetupValidationResult(
        setup_name=spec.name,
        asset="ALL" if len(spec.assets) > 1 else (spec.assets[0] if spec.assets else ""),
        tf_context=spec.tf_context,
        tf_execution=spec.tf_execution,
        period_start=period_start,
        period_end=period_end,
        sample_size=n,

        win_rate=baseline["win_rate"],
        profit_factor=baseline["profit_factor"],
        ev_per_trade=deployable["ev_per_trade"],
        avg_win=baseline["avg_win"],
        avg_loss=baseline["avg_loss"],
        win_loss_ratio=baseline["win_loss_ratio"],

        mfe_mean=mfe_mae["mfe_mean"],
        mfe_median=mfe_mae["mfe_median"],
        mae_mean=mfe_mae["mae_mean"],
        mae_median=mfe_mae["mae_median"],

        max_dd_pct=deployable["max_dd_pct"],
        max_dd_abs=deployable["max_dd_abs"],

        liq_rates=[
            LiqRateByLeverage(
                leverage=lr["leverage"],
                liq_threshold_pct=lr["liq_threshold_pct"],
                n_trades=lr["n_trades"],
                n_liquidated=lr["n_liquidated"],
                liq_rate_pct=lr["liq_rate_pct"],
                ev_per_trade=lr["ev_per_trade"],
                capital_final=lr["capital_final"],
            ) for lr in liq_rates
        ],

        mc_shuffle_pct_profitable=mc_shuf["pct_profitable"],
        mc_random_edge_pp=mc_edge,
        mc_param_perturb_pct_profitable=0,  # requeriria signal_fn, no disponible aquí

        wf_expanding_positive_years=wf_exp["positive"],
        wf_expanding_total_years=wf_exp["total"],
        wf_rolling_positive_years=wf_roll["positive"],
        wf_rolling_total_years=wf_roll["total"],

        yearly=[
            YearlyBreakdown(
                year=y["year"], n_trades=y["n"], win_rate=y["wr"],
                total_pnl=y["total"], avg_pnl=y["avg"], is_positive=y["positive"],
            ) for y in yearly
        ],

        status=SetupStatus(status_str),
        decision_reason=reason,

        validated_at=datetime.now(timezone.utc).isoformat(),
        script="lab/harness/runner.py",
    )

    # ── Artifact ──
    artifact = {
        "task": "T5_harness_validation",
        "setup_name": spec.name,
        "validated_at": result.validated_at,
        "config": asdict(cfg),
        "baseline": baseline,
        "deployable": deployable,
        "mfe_mae": mfe_mae,
        "liq_rates": liq_rates,
        "mc_shuffle": mc_shuf,
        "mc_random_entry": mc_rand,
        "mc_random_edge_pp": mc_edge,
        "wf_expanding": wf_exp,
        "wf_rolling": wf_roll,
        "yearly": yearly,
        "classification": {"status": status_str, "reason": reason},
    }

    return result, artifact


def save_artifact(artifact: dict, setup_name: str, out_dir: str = "lab/out") -> str:
    """Guarda artifact JSON."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{setup_name}_validation.json")
    with open(path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    return path


def print_summary(result: SetupValidationResult, artifact: dict):
    """Imprimeix resum llegible."""
    bl = artifact["baseline"]
    dp = artifact["deployable"]
    mm = artifact["mfe_mae"]

    print(f"\n{'=' * 80}")
    print(f"  SETUP: {result.setup_name}")
    print(f"  ASSETS: {result.asset}")
    print(f"  PERIOD: {result.period_start} → {result.period_end}")
    print(f"  N: {result.sample_size}")
    print(f"{'=' * 80}")

    print(f"\n  BASELINE (sense liquidació):")
    print(f"    WR={bl['win_rate']}% PF={bl['profit_factor']} EV={bl['ev_per_trade']:+.1f}$/t")
    print(f"    AvgWin={bl['avg_win']:+.0f}$ AvgLoss={bl['avg_loss']:+.0f}$ W/L={bl['win_loss_ratio']}")

    print(f"\n  DEPLOYABLE (lev={dp['leverage']}x, amb liquidació+paper):")
    print(f"    WR={dp['win_rate']}% PF={dp['profit_factor']} EV={dp['ev_per_trade']:+.1f}$/t")
    print(f"    Liquidats: {dp['n_liquidated']} ({dp['liq_rate_pct']}%)")
    print(f"    Capital: {dp['capital_initial']}$ → {dp['capital_final']}$ (x{dp['capital_x']})")
    print(f"    MaxDD: {dp['max_dd_pct']}%")

    print(f"\n  MFE/MAE:")
    print(f"    MFE: mean={mm['mfe_mean']}% med={mm['mfe_median']}%")
    print(f"    MAE: mean={mm['mae_mean']}% med={mm['mae_median']}%")

    print(f"\n  LIQUIDACIÓ PER LEVERAGE:")
    for lr in artifact["liq_rates"]:
        print(f"    {lr['leverage']:>4}x: liq={lr['liq_rate_pct']:>5.1f}% EV={lr['ev_per_trade']:>+6.1f}$/t cap={lr['capital_final']:>6.0f}$")

    print(f"\n  MONTE CARLO:")
    mc = artifact["mc_shuffle"]
    print(f"    Shuffle: {mc['pct_profitable']}% sims profitables, P5={mc['p5']:+.0f}$")
    print(f"    Random entry edge: {artifact['mc_random_edge_pp']:+.1f}pp")

    print(f"\n  WALK-FORWARD:")
    wfe = artifact["wf_expanding"]
    wfr = artifact["wf_rolling"]
    print(f"    Expanding: {wfe['positive']}/{wfe['total']} anys positius")
    print(f"    Rolling {artifact['config']['wf_train_window']}y: {wfr['positive']}/{wfr['total']} anys positius")

    print(f"\n  YEARLY:")
    for y in artifact["yearly"]:
        flag = " ***NEG***" if not y["positive"] else ""
        print(f"    {y['year']}: {y['n']:>3}t WR={y['wr']:>4.0f}% total={y['total']:>+7.0f}${flag}")

    print(f"\n  {'█' * 60}")
    print(f"  STATUS: {result.status.upper()}")
    print(f"  REASON: {result.decision_reason}")
    print(f"  {'█' * 60}")
