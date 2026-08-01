"""Cross-asset portfolio families for the small-investor campaign."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from lab.studies.small_investor_campaign import (DEV_END, VAL_END, FINANCING_ANNUAL,
    LEVERAGES, ROUND_TRIP_COST, download, metrics, segment)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "lab" / "out" / "small_investor_campaign"

def market(data):
    opens = pd.concat({s: d.O for s, d in data.items()}, axis=1).dropna()
    closes = pd.concat({s: d.C for s, d in data.items()}, axis=1).reindex(opens.index).dropna()
    opens = opens.reindex(closes.index)
    return closes, (opens.shift(-1) / opens - 1).fillna(0.0)

def weights(closes, family, lookback):
    mom = closes.pct_change(lookback)
    trend = closes > closes.rolling(200).mean()
    periods = pd.Series(closes.index.to_period("M"), index=closes.index)
    rebalance = periods.ne(periods.shift(1))
    target = pd.DataFrame(np.nan, index=closes.index, columns=closes.columns)
    if family == "relative_momentum":
        eligible = mom.where(mom > 0)
        pick = eligible.fillna(-np.inf).idxmax(axis=1).where(eligible.notna().any(axis=1))
        target.loc[rebalance] = 0.0
        for symbol in closes:
            target.loc[rebalance & pick.eq(symbol), symbol] = 1.0
    elif family == "diversified_trend":
        raw = trend.astype(float)
        raw = raw.div(raw.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
        target.loc[rebalance] = raw.loc[rebalance]
    else:
        eligible = mom[["GLD", "TLT"]].where(lambda x: x > 0)
        defensive = eligible.fillna(-np.inf).idxmax(axis=1).where(eligible.notna().any(axis=1))
        target.loc[rebalance] = 0.0
        target.loc[rebalance & trend.SPY, "SPY"] = 1.0
        for symbol in ("GLD", "TLT"):
            target.loc[rebalance & ~trend.SPY & defensive.eq(symbol), symbol] = 1.0
    return target.ffill().fillna(0.0)

def strategy_returns(w, open_ret, leverage=1.0, cost_mult=1.0):
    w = w.shift(1).fillna(0.0)
    turnover = w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1))
    exposure = w.abs().sum(axis=1)
    gross = (w * open_ret).sum(axis=1) * leverage
    costs = turnover * ROUND_TRIP_COST * .5 * leverage * cost_mult
    financing = exposure * max(leverage - 1, 0) * FINANCING_ANNUAL / 252
    return gross - costs - financing

def select(data):
    closes, open_ret = market(data)
    output = []
    for family in ("relative_momentum", "diversified_trend", "defensive_rotation"):
        variants = []
        for lookback in (126, 189, 252):
            w = weights(closes, family, lookback)
            ret = strategy_returns(w, open_ret)
            dev = metrics(segment(ret, "dev"))
            score = dev["sharpe"] + .5 * dev["cagr"] - 1.5 * dev["max_dd"]
            variants.append((score, lookback, w, ret, dev))
        _, lookback, w, ret, dev = max(variants, key=lambda x: x[0])
        output.append({"family": family, "params": (lookback,), "weights": w,
            "open_ret": open_ret, "dev": dev,
            "validation": metrics(segment(ret, "validation")),
            "test": metrics(segment(ret, "test")),
            "robust": float(np.mean([metrics(segment(v[3], "validation"))["total"] > 0 for v in variants]))})
    return output

def leverage_gate(item):
    rows, chosen = [], None
    for lev in LEVERAGES:
        ret = strategy_returns(item["weights"], item["open_ret"], lev)
        stress = strategy_returns(item["weights"], item["open_ret"], lev, 2)
        val, test = metrics(segment(ret, "validation")), metrics(segment(ret, "test"))
        sv, st = metrics(segment(stress, "validation")), metrics(segment(stress, "test"))
        selection_pass = (val["max_dd"] <= .20 and val["pf"] >= 1.20
            and val["months_p5"] >= -.10 and sv["total"] > 0)
        test_pass = (test["max_dd"] <= .25 and test["pf"] >= 1.20
            and test["months_p5"] >= -.10 and st["total"] > 0)
        rows.append({"leverage": lev, "selection_pass": selection_pass, "test_pass": test_pass,
            "validation": val, "test": test, "stress_validation": sv, "stress_test": st})
        if selection_pass: chosen = lev
    return chosen, rows

def main():
    results = []
    for item in select(download()):
        lev, sweep = leverage_gate(item)
        selected_row = next((row for row in sweep if row["leverage"] == lev), None)
        accepted = (item["validation"]["pf"] >= 1.25 and item["test"]["pf"] >= 1.25
            and item["validation"]["total"] > 0 and item["test"]["total"] > 0
            and item["robust"] >= .70 and lev is not None
            and selected_row is not None and selected_row["test_pass"])
        results.append({"family": item["family"], "asset": "PORTFOLIO", "params": item["params"],
            "dev": item["dev"], "validation": item["validation"], "test": item["test"],
            "neighbour_positive_validation": item["robust"], "selected_leverage": lev,
            "accepted": accepted, "leverage_sweep": sweep})
    (OUT / "portfolio_results.json").write_text(json.dumps({"results": results}, indent=2, default=str))
    lines = ["# Cross-asset portfolio campaign", "", "| Family | Params | Val PF | Test PF | Test CAGR | Test DD | Lev | Gate |",
        "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in results:
        lines.append(f"| {r['family']} | `{r['params']}` | {r['validation']['pf']:.2f} | {r['test']['pf']:.2f} | "
            f"{r['test']['cagr']:.1%} | {r['test']['max_dd']:.1%} | {r['selected_leverage'] or '-'} | "
            f"{'ACCEPTED' if r['accepted'] else 'REJECTED'} |")
    (OUT / "PORTFOLIOS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__": main()
