#!/usr/bin/env python3
"""Frozen multi-asset monthly dual-momentum screen with gated 2024 OOS."""
from __future__ import annotations

import argparse, csv, hashlib, json, math, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "multi_asset_dual_momentum_preregistration_v1.json"
LOCK = HERE / "multi_asset_dual_momentum_preregistration_v1.lock.json"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_spec():
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if spec["status"] != "FROZEN_BEFORE_PERFORMANCE" or sha(SPEC) != lock["preregistration_sha256"] or lock["oos_2024_accessed"] is not False:
        raise ValueError("preregistration lock mismatch")
    return spec

def monthly(path, allow_oos):
    if "2025" in Path(path).name: raise ValueError("2025 filename refused")
    values = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.reader(handle):
            if not raw or raw[0].lower() == "date": continue
            day = raw[0].replace(".", "-")
            if day > ("2024-12-31" if allow_oos else "2023-12-31"): continue
            offset = 2 if len(raw) >= 7 and ":" in raw[1] else 1
            values[day[:7]] = (day, float(raw[offset + 3]))
    return {month: close for month, (_, close) in values.items()}

def returns(series, spec):
    common = sorted(set.intersection(*(set(value) for value in series.values())))
    lookback, previous = spec["rule"]["formation_months"], "CASH"
    result = []
    for index in range(lookback, len(common) - 1):
        signal_month, held_month = common[index], common[index + 1]
        scores = {asset: values[signal_month] / values[common[index-lookback]] - 1 for asset, values in series.items()}
        chosen = max(scores, key=scores.get)
        if scores[chosen] <= 0: chosen = "CASH"
        gross = 0.0 if chosen == "CASH" else series[chosen][held_month] / series[chosen][signal_month] - 1
        cost = (spec["rule"]["switch_cost_bps"] / 10_000) if chosen != previous else 0.0
        equal = sum(values[held_month] / values[signal_month] - 1 for values in series.values()) / len(series)
        result.append({"month": held_month, "asset": chosen, "return": gross-cost,
                       "benchmark_return": equal, "score": scores.get(chosen)})
        previous = chosen
    return result

def metrics(rows, key):
    equity = peak = 1.0; dd = wins = losses = 0.0; years = {}; values = []
    for row in rows:
        value=row[key]; values.append(value); equity*=1+value; peak=max(peak,equity); dd=max(dd,1-equity/peak)
        years[row["month"][:4]]=years.get(row["month"][:4],1.0)*(1+value)
        wins+=max(value,0); losses+=max(-value,0)
    mean=statistics.mean(values) if values else 0; std=statistics.stdev(values) if len(values)>1 else 0
    return {"months":len(rows),"net_return":equity-1,"annualized_sharpe":mean/std*math.sqrt(12) if std else None,
            "profit_factor":wins/losses if losses else None,"maximum_drawdown":dd,
            "calendar_year_returns":{k:v-1 for k,v in sorted(years.items())},
            "positive_calendar_years":sum(v>1 for v in years.values())}

def evaluate(rows,bounds):
    selected=[r for r in rows if bounds[0]<=r["month"]<=bounds[1]]
    strategy, benchmark=metrics(selected,"return"),metrics(selected,"benchmark_return")
    strategy["sharpe_improvement_vs_equal_weight"]=strategy["annualized_sharpe"]-benchmark["annualized_sharpe"]
    strategy["selection_counts"]={asset:sum(r["asset"]==asset for r in selected) for asset in ["SPY","PHAU","IDTL","CASH"]}
    return {"strategy":strategy,"equal_weight_benchmark":benchmark}

def passes(value,gate):
    s=value["strategy"]
    return bool(s["months"]>=gate["minimum_months"] and s["net_return"]>gate["minimum_net_return"] and
      s["profit_factor"] is not None and s["profit_factor"]>=gate["minimum_profit_factor"] and
      s["sharpe_improvement_vs_equal_weight"]>=gate["minimum_sharpe_improvement_vs_equal_weight"] and
      s["positive_calendar_years"]>=gate["positive_calendar_years_required"] and s["maximum_drawdown"]<=gate["maximum_drawdown"])

def screen(paths):
    spec=load_spec(); pre={asset:monthly(paths[asset],False) for asset in spec["assets"]}; rows=returns(pre,spec)
    train=evaluate(rows,spec["periods"]["train"]); validation=evaluate(rows,spec["periods"]["validation"]); passed=passes(validation,spec["validation_gate"])
    result={"schema_version":1,"campaign_id":spec["campaign_id"],"preregistration_sha256":sha(SPEC),
      "source_sha256":{a:sha(p) for a,p in paths.items()},"train":train,"validation":validation,
      "validation_gate_passed":passed,"decision":"PASS_VALIDATION_OPEN_OOS" if passed else "REJECT_VALIDATION",
      "oos_2024_accessed":False,"holdout_2025_accessed":False,"optimized":False,"paper_authorized":False,"live_authorized":False}
    if passed:
        complete={asset:monthly(paths[asset],True) for asset in spec["assets"]}
        result["oos"]=evaluate(returns(complete,spec),spec["periods"]["oos"]); result["oos_2024_accessed"]=True
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--asset",action="append",required=True); ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
    paths=dict(item.split("=",1) for item in args.asset); result=screen(paths); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
