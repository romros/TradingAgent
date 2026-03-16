"""
lab/harness/core.py — Core del harness de validació

Funcions pures de càlcul: backtest, liquidació, MFE/MAE, mètriques.
No depenen de cap setup concret — reben trades ja generats.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TradeRecord:
    """Trade individual generat per un setup."""
    ts: str           # ISO timestamp de la candle trigger
    year: int
    asset: str
    score: int
    move: float       # (close_next - open_next) / open_next
    mae: float        # (open_next - low_next) / open_next
    mfe: float        # (high_next - open_next) / open_next
    green: bool       # close_next > open_next


# ══════════════════════════════════════════════════════════════
# BACKTEST BASELINE (sense liquidació)
# ══════════════════════════════════════════════════════════════

def backtest_baseline(trades: list[TradeRecord], nominal: float, fee: float) -> dict:
    """Backtest sense liquidació — mesura l'edge teòric."""
    pnls = np.array([nominal * t.move - fee for t in trades])
    return _compute_metrics(pnls, trades, "baseline")


# ══════════════════════════════════════════════════════════════
# BACKTEST DEPLOYABLE (amb liquidació)
# ══════════════════════════════════════════════════════════════

def backtest_deployable(trades: list[TradeRecord], leverage: int,
                        fee: float, col_pct: float = 0.20,
                        col_min: float = 15.0, col_max: float = 60.0,
                        init_capital: float = 250.0,
                        paper_threshold: int = 2) -> dict:
    """
    Backtest amb liquidació real + paper mode + compounding.
    Si MAE >= 1/leverage → pnl = -collateral.
    """
    liq_th = 1.0 / leverage
    capital = init_capital
    consec_loss = 0
    paper_mode = False
    result_pnls = []
    n_liquidated = 0
    n_paper_skipped = 0
    trade_results = []

    sorted_trades = sorted(trades, key=lambda t: t.ts)

    for t in sorted_trades:
        if paper_mode:
            # Simular en paper
            if t.mae >= liq_th:
                paper_pnl = -1
            else:
                paper_pnl = t.move
            if paper_pnl > 0:
                paper_mode = False
                consec_loss = 0
            n_paper_skipped += 1
            continue

        col = min(max(capital * col_pct, col_min), col_max)
        if capital < col_min:
            continue

        nominal = col * leverage
        if t.mae >= liq_th:
            pnl = -col
            n_liquidated += 1
        else:
            pnl = nominal * t.move - fee

        capital += pnl
        if capital < 0:
            capital = 0
        result_pnls.append(pnl)
        trade_results.append(TradeRecord(
            ts=t.ts, year=t.year, asset=t.asset, score=t.score,
            move=t.move, mae=t.mae, mfe=t.mfe, green=pnl > 0,
        ))

        if pnl > 0:
            consec_loss = 0
        else:
            consec_loss += 1
            if consec_loss >= paper_threshold:
                paper_mode = True

    pnls = np.array(result_pnls) if result_pnls else np.array([0.0])
    metrics = _compute_metrics(pnls, trade_results, "deployable")
    metrics["leverage"] = leverage
    metrics["liq_threshold_pct"] = round(100 / leverage, 2)
    metrics["n_liquidated"] = n_liquidated
    metrics["liq_rate_pct"] = round(100 * n_liquidated / len(result_pnls), 1) if result_pnls else 0
    metrics["n_paper_skipped"] = n_paper_skipped
    metrics["capital_initial"] = init_capital
    metrics["capital_final"] = round(capital, 0)
    metrics["capital_x"] = round(capital / init_capital, 1) if init_capital > 0 else 0
    return metrics


# ══════════════════════════════════════════════════════════════
# MFE / MAE
# ══════════════════════════════════════════════════════════════

def compute_mfe_mae(trades: list[TradeRecord]) -> dict:
    """Distribució MFE i MAE."""
    maes = np.array([t.mae for t in trades])
    mfes = np.array([t.mfe for t in trades])
    return {
        "mfe_mean": round(float(mfes.mean() * 100), 3),
        "mfe_median": round(float(np.median(mfes) * 100), 3),
        "mfe_p75": round(float(np.percentile(mfes, 75) * 100), 3),
        "mfe_p90": round(float(np.percentile(mfes, 90) * 100), 3),
        "mae_mean": round(float(maes.mean() * 100), 3),
        "mae_median": round(float(np.median(maes) * 100), 3),
        "mae_p75": round(float(np.percentile(maes, 75) * 100), 3),
        "mae_p90": round(float(np.percentile(maes, 90) * 100), 3),
    }


# ══════════════════════════════════════════════════════════════
# LIQUIDATION RATES per leverage
# ══════════════════════════════════════════════════════════════

def compute_liq_rates(trades: list[TradeRecord], leverages: list[int],
                      fee: float, init_capital: float = 250.0) -> list[dict]:
    """Liquidation rate per a cada leverage."""
    results = []
    for lev in leverages:
        dep = backtest_deployable(trades, lev, fee, init_capital=init_capital)
        results.append({
            "leverage": lev,
            "liq_threshold_pct": dep["liq_threshold_pct"],
            "n_trades": dep["sample_size"],
            "n_liquidated": dep["n_liquidated"],
            "liq_rate_pct": dep["liq_rate_pct"],
            "ev_per_trade": dep["ev_per_trade"],
            "capital_final": dep["capital_final"],
        })
    return results


# ══════════════════════════════════════════════════════════════
# MONTE CARLO
# ══════════════════════════════════════════════════════════════

def mc_shuffle(pnls: np.ndarray, n_sim: int = 10000, seed: int = 42) -> dict:
    """MC1: barrejar ordre dels trades."""
    rng = np.random.default_rng(seed)
    sim_totals = np.array([rng.permutation(pnls).sum() for _ in range(n_sim)])
    return {
        "pct_profitable": round(float(100 * np.mean(sim_totals > 0)), 1),
        "p5": round(float(np.percentile(sim_totals, 5)), 0),
        "p50": round(float(np.percentile(sim_totals, 50)), 0),
        "p95": round(float(np.percentile(sim_totals, 95)), 0),
    }


def mc_random_entry(all_moves: np.ndarray, n_real: int, nominal: float,
                    fee: float, n_sim: int = 5000, seed: int = 42) -> dict:
    """MC2: comparar amb entrades aleatòries."""
    rng = np.random.default_rng(seed)
    sim_wrs = np.zeros(n_sim)
    for s in range(n_sim):
        chosen = rng.choice(len(all_moves), size=min(n_real, len(all_moves)), replace=False)
        sim_pnls = nominal * all_moves[chosen] - fee
        sim_wrs[s] = 100 * np.mean(sim_pnls > 0)
    return {
        "random_wr_mean": round(float(sim_wrs.mean()), 1),
        "random_wr_p95": round(float(np.percentile(sim_wrs, 95)), 1),
    }


# ══════════════════════════════════════════════════════════════
# WALK-FORWARD
# ══════════════════════════════════════════════════════════════

def walk_forward_expanding(trades: list[TradeRecord], nominal: float, fee: float) -> dict:
    """WF expanding: train <year, test =year."""
    by_year = {}
    for t in trades:
        by_year.setdefault(t.year, []).append(t)
    years = sorted(by_year.keys())
    results = []
    for i, yr in enumerate(years):
        test_pnls = np.array([nominal * t.move - fee for t in by_year[yr]])
        n = len(test_pnls)
        wr = round(float(100 * np.mean(test_pnls > 0)), 0) if n > 0 else 0
        total = round(float(test_pnls.sum()), 0)
        results.append({"year": yr, "n": n, "wr": wr, "total": total, "positive": total >= 0})
    pos = sum(1 for r in results if r["positive"])
    return {"years": results, "positive": pos, "total": len(results)}


def walk_forward_rolling(trades: list[TradeRecord], nominal: float, fee: float,
                         train_window: int = 3) -> dict:
    """WF rolling: train window fix, test 1 any."""
    by_year = {}
    for t in trades:
        by_year.setdefault(t.year, []).append(t)
    years = sorted(by_year.keys())
    results = []
    for yr in years:
        if yr - train_window < min(years):
            continue
        test_trades = by_year.get(yr, [])
        if not test_trades:
            continue
        test_pnls = np.array([nominal * t.move - fee for t in test_trades])
        n = len(test_pnls)
        wr = round(float(100 * np.mean(test_pnls > 0)), 0) if n > 0 else 0
        total = round(float(test_pnls.sum()), 0)
        results.append({"year": yr, "window": f"{yr - train_window}-{yr - 1}",
                        "n": n, "wr": wr, "total": total, "positive": total >= 0})
    pos = sum(1 for r in results if r["positive"])
    return {"years": results, "positive": pos, "total": len(results)}


# ══════════════════════════════════════════════════════════════
# YEARLY BREAKDOWN
# ══════════════════════════════════════════════════════════════

def yearly_breakdown(trades: list[TradeRecord], nominal: float, fee: float) -> list[dict]:
    by_year = {}
    for t in trades:
        by_year.setdefault(t.year, []).append(t)
    results = []
    for yr in sorted(by_year.keys()):
        pnls = np.array([nominal * t.move - fee for t in by_year[yr]])
        n = len(pnls)
        wr = round(float(100 * np.mean(pnls > 0)), 0) if n > 0 else 0
        total = round(float(pnls.sum()), 0)
        avg = round(float(pnls.mean()), 1) if n > 0 else 0
        results.append({"year": yr, "n": n, "wr": wr, "total": total, "avg": avg,
                        "positive": total >= 0})
    return results


# ══════════════════════════════════════════════════════════════
# CLASSIFICATION
# ══════════════════════════════════════════════════════════════

def classify_setup(metrics_deployable: dict, mc_result: dict, mc_random: dict,
                   wf_exp: dict, wf_roll: dict) -> tuple[str, str]:
    """
    Retorna (status, reason) basant-se en els criteris de SETUPS_CONTRACTE.md.
    """
    reasons = []

    # MC checks
    if mc_result["pct_profitable"] < 90:
        reasons.append(f"mc_shuffle {mc_result['pct_profitable']}% < 90%")
    if mc_random.get("random_wr_p95", 100) <= 0:
        reasons.append("mc_random no disponible")

    # WF checks
    if wf_exp["total"] > 0:
        wf_exp_pct = wf_exp["positive"] / wf_exp["total"]
        if wf_exp_pct < 0.50:
            reasons.append(f"wf_expanding {wf_exp['positive']}/{wf_exp['total']} < 50%")
    if wf_roll["total"] > 0:
        wf_roll_pct = wf_roll["positive"] / wf_roll["total"]
        if wf_roll_pct < 0.50:
            reasons.append(f"wf_rolling {wf_roll['positive']}/{wf_roll['total']} < 50%")

    if reasons:
        return "rejected", "Fails: " + "; ".join(reasons)

    # ACCEPTED vs WATCHLIST
    ev = metrics_deployable.get("ev_per_trade", 0)
    pf = metrics_deployable.get("profit_factor", 0)
    liq = metrics_deployable.get("liq_rate_pct", 100)
    wr = metrics_deployable.get("win_rate", 0)
    sample = metrics_deployable.get("sample_size", 0)
    trades_yr = sample / max(metrics_deployable.get("n_years", 1), 1)

    accepted_checks = [
        sample >= 80,
        trades_yr >= 12,
        pf >= 1.30,
        ev >= 8.0,
        liq <= 15,
        wr >= 55,
    ]

    if all(accepted_checks):
        return "accepted", f"All criteria met: N={sample}, PF={pf}, EV={ev:+.1f}, liq={liq}%"

    watchlist_reasons = []
    if ev < 8.0:
        watchlist_reasons.append(f"EV {ev:+.1f}$ < 8$")
    if pf < 1.30:
        watchlist_reasons.append(f"PF {pf:.2f} < 1.30")
    if liq > 15:
        watchlist_reasons.append(f"liq {liq}% > 15%")
    if sample < 80:
        watchlist_reasons.append(f"N={sample} < 80")
    if trades_yr < 12:
        watchlist_reasons.append(f"trades/yr={trades_yr:.0f} < 12")

    return "watchlist", "Edge real, però: " + "; ".join(watchlist_reasons)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _compute_metrics(pnls: np.ndarray, trades: list[TradeRecord], layer: str) -> dict:
    n = len(pnls)
    if n == 0:
        return {"layer": layer, "sample_size": 0}

    wr = round(float(100 * np.mean(pnls > 0)), 1)
    w = pnls[pnls > 0]
    l = pnls[pnls <= 0]
    pf = round(float(abs(w.sum() / l.sum())), 2) if len(l) > 0 and l.sum() != 0 else 99.0
    avg_w = round(float(w.mean()), 1) if len(w) > 0 else 0
    avg_l = round(float(l.mean()), 1) if len(l) > 0 else 0
    wl = round(abs(avg_w / avg_l), 2) if avg_l != 0 else 99.0

    # Max drawdown
    eq = np.cumsum(pnls)
    peak = np.maximum.accumulate(eq)
    dd = peak - eq
    max_dd = float(dd.max()) if len(dd) > 0 else 0
    max_dd_pct = round(float(max_dd / (peak[np.argmax(dd)] + 250) * 100), 1) if max_dd > 0 else 0

    # Years
    years = set(t.year for t in trades)
    n_years = max(len(years), 1)

    return {
        "layer": layer,
        "sample_size": n,
        "n_years": n_years,
        "trades_per_year": round(n / n_years, 1),
        "win_rate": wr,
        "profit_factor": pf,
        "ev_per_trade": round(float(pnls.mean()), 1),
        "total_pnl": round(float(pnls.sum()), 0),
        "avg_win": avg_w,
        "avg_loss": avg_l,
        "win_loss_ratio": wl,
        "max_dd_pct": max_dd_pct,
        "max_dd_abs": round(max_dd, 0),
    }
