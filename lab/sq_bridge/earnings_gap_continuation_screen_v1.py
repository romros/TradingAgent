#!/usr/bin/env python3
"""Frozen short-horizon earnings-gap continuation screen."""
from __future__ import annotations

import argparse, csv, hashlib, json, math
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "earnings_gap_continuation_preregistration_v1.json"
LOCK = HERE / "earnings_gap_continuation_preregistration_v1.lock.json"
PREFLIGHT = ROOT / "data/ibkr_sq_v2/pead_ear_v1/sec_calendar_preflight_v1.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prices(path: Path) -> dict[date, dict[str, float]]:
    result = {}
    with path.open(newline="") as stream:
        first = stream.readline(); stream.seek(0)
        if first.lower().startswith("date,"):
            for row in csv.DictReader(stream):
                result[date.fromisoformat(row["date"])] = {k: float(row[k]) for k in ("open", "high", "low", "close")}
        else:
            for raw in stream:
                if not raw.strip(): continue
                f = raw.split(",")
                result[date.fromisoformat(f[0].replace(".", "-"))] = dict(open=float(f[2]), high=float(f[3]), low=float(f[4]), close=float(f[5]))
    return result

def metrics(items: list[dict]) -> dict:
    values = [x["net_return"] for x in sorted(items, key=lambda x: (x["exit"], x["asset"]))]
    if not values: return {"trades": 0}
    n=len(values); mean=sum(values)/n
    variance=sum((x-mean)**2 for x in values)/(n-1) if n>1 else 0
    gp=sum(x for x in values if x>0); gl=-sum(x for x in values if x<0)
    equity=peak=1.0; dd=0.0
    for x in values:
        equity*=1+x; peak=max(peak,equity); dd=max(dd,1-equity/peak)
    return {"trades":n,"wins":sum(x>0 for x in values),"mean_net_return":mean,
            "compounded_net_return":equity-1,"profit_factor":gp/gl if gl else None,
            "t_stat":mean/math.sqrt(variance/n) if variance else None,"maximum_drawdown":dd}

def screen() -> dict:
    spec=json.loads(SPEC.read_text()); lock=json.loads(LOCK.read_text()); pre=json.loads(PREFLIGHT.read_text())
    if sha(SPEC)!=lock["preregistration_sha256"] or sha(PREFLIGHT)!=spec["upstream_preflight_sha256"]:
        raise ValueError("frozen input hash mismatch")
    frames={a:prices(ROOT/d["market_path"]) for a,d in pre["assets"].items()}
    econ=spec["economics"]; params=spec["parameters"]; notional=float(econ["reference_notional_usd_per_event"])
    observations=[]; rejected=[]
    for event in pre["events"]:
        asset=event["asset"]; frame=frames[asset]; days=sorted(frame); pos={d:i for i,d in enumerate(days)}
        reaction=date.fromisoformat(event["reaction_session"])
        if reaction not in pos or pos[reaction]==0 or pos[reaction]+1+params["holding_sessions"]>=len(days):
            rejected.append({"asset":asset,"accession":event["accession"],"reason":"window unavailable"}); continue
        i=pos[reaction]; bar=frame[reaction]; prior=frame[days[i-1]]
        gap=bar["open"]/prior["close"]-1; span=bar["high"]-bar["low"]
        clv=(bar["close"]-bar["low"])/span if span>0 else -1
        if gap < params["minimum_gap_pct"]/100 or bar["close"]<=bar["open"] or clv<params["minimum_close_location_value"]: continue
        entry=days[i+1]; exit_day=days[i+1+params["holding_sessions"]]
        ep=frame[entry]["open"]; xp=frame[exit_day]["open"]; shares=math.floor(notional/ep)
        if shares<1: continue
        friction=2*econ["minimum_per_order_usd"]+shares*(ep+xp)*econ["bps_per_side"]/10000
        observations.append({"asset":asset,"accession":event["accession"],"reaction":reaction,
            "entry":entry,"exit":exit_day,"gap":gap,"clv":clv,"shares":shares,
            "net_return":((xp-ep)*shares-friction)/(ep*shares)})
    period_items={n:[x for x in observations if date.fromisoformat(b[0])<=x["reaction"]<=date.fromisoformat(b[1])]
                  for n,b in spec["periods"].items()}
    periods={n:metrics(v) for n,v in period_items.items()}; combined_items=period_items["validation"]+period_items["oos_2024"]
    combined=metrics(combined_items)
    years={str(y):metrics([x for x in combined_items if x["reaction"].year==y]) for y in range(2022,2025)}
    by_asset={a:metrics([x for x in combined_items if x["asset"]==a]) for a in spec["universe"]}
    positive_years=sum(x.get("mean_net_return",0)>0 for x in years.values())
    positive_assets=sum(x.get("mean_net_return",0)>0 for x in by_asset.values())
    g=spec["gates"]
    passed=(periods["train"].get("mean_net_return",-1)>g["train_net_mean_strictly_above"] and
        periods["validation"].get("mean_net_return",-1)>g["validation_net_mean_strictly_above"] and
        combined["trades"]>=g["combined_validation_oos_minimum_trades"] and
        (combined.get("profit_factor") or 0)>=g["combined_validation_oos_profit_factor_at_least"] and
        (combined.get("t_stat") or -999)>=g["combined_validation_oos_one_sided_t_stat_at_least"] and
        positive_years>=g["minimum_positive_years_2022_2024"] and positive_assets>=g["minimum_positive_assets_validation_oos"] and
        combined.get("maximum_drawdown",1)<=g["maximum_combined_validation_oos_drawdown_pct"]/100)
    return {"schema_version":1,"decision":"PASS_EXPLORATORY_EDGE_GATE" if passed else "REJECT_EXPLORATORY_EDGE_GATE",
        "preregistration_sha256":sha(SPEC),"optimized":False,"holdout_pristine":False,"periods":periods,
        "combined_validation_oos":combined,"years_2022_2024":years,"by_asset_validation_oos":by_asset,
        "positive_years":positive_years,"positive_assets":positive_assets,"signals_executed":len(observations),
        "observations":observations,"skipped":rejected,"paper_authorized":False,"live_authorized":False}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output",required=True,type=Path); args=parser.parse_args()
    result=screen(); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,default=str)+"\n")
    print(json.dumps({k:result[k] for k in ("decision","periods","combined_validation_oos","positive_years","positive_assets","signals_executed")},indent=2))
if __name__=="__main__": main()
