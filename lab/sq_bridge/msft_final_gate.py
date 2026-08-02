#!/usr/bin/env python3
"""Cost, bootstrap Monte Carlo i sizing de risc dels finalistes MSFT."""
from __future__ import annotations
import argparse, hashlib, json, math, random
from pathlib import Path


def metrics(returns):
    curve=peak=1.0; maxdd=0.0; win=loss=0.0
    for value in returns:
        curve*=1+value; peak=max(peak,curve); maxdd=max(maxdd,1-curve/peak)
        if value>0: win+=value
        else: loss-=value
    return {"return_pct":round((curve-1)*100,6),"profit_factor":round(win/loss,6) if loss else None,"max_drawdown_pct":round(maxdd*100,6)}


def percentile(values,q):
    values=sorted(values); return values[min(len(values)-1,math.ceil(len(values)*q)-1)]


def evaluate(source: Path, runs: int=10000):
    data=json.loads(source.read_text()); rows=[]
    for candidate in data["candidates"]:
        trades=[t for p in ("validation","oos","holdout") for t in candidate["results"][p]["trades_detail"]]
        scenarios={}; adjusted={}
        for name,bps in (("base",12),("conservative",24),("stress",36)):
            values=[t["return"]-bps/10000 for t in trades]; adjusted[name]=values; scenarios[name]=metrics(values)
        seed=int(hashlib.sha256((candidate["project"]+candidate["strategy"]).encode()).hexdigest()[:16],16)
        rng=random.Random(seed); stress=adjusted["stress"]; mc=[]
        for _ in range(runs): mc.append(metrics([rng.choice(stress) for _ in stress]))
        stops=sorted(t["stop_distance_pct"] for t in trades if math.isfinite(t["stop_distance_pct"]))
        p95_stop=percentile(stops,.95); cost_pct=.36; liq_buffer=2.0
        liquidation_cap=math.floor(100/(p95_stop*liq_buffer+cost_pct))
        # 1% de 200 USDC; notional constant independentment del leverage.
        risk_notional=2.0/((p95_stop+cost_pct)/100)
        venue_cap=100; preliminary_leverage=max(1,min(venue_cap,liquidation_cap))
        margin=risk_notional/preliminary_leverage
        hold=candidate["results"]["holdout"]
        hold_stress=metrics([t["return"]-.0036 for t in hold["trades_detail"]])
        reasons=[]
        if hold["trades"]<25: reasons.append("HOLDOUT_TRADES_LT_25")
        if (hold_stress["profit_factor"] or 0)<1.1: reasons.append("HOLDOUT_STRESS_PF_LT_1_10")
        if sum(x["return_pct"]>0 for x in mc)/runs<.7: reasons.append("MC_PROFITABLE_LT_70_PERCENT")
        reasons.append("OSTIUM_OHLC_EXECUTION_PARITY_NOT_CERTIFIED")
        reasons.append("GAP_LIQUIDATION_PROBABILITY_NOT_MEASURED")
        rows.append({"project":candidate["project"],"strategy":candidate["strategy"],"trade_count":len(trades),
          "scenarios":scenarios,"holdout_stress":hold_stress,
          "monte_carlo":{"runs":runs,"profitable_ratio":round(sum(x["return_pct"]>0 for x in mc)/runs,6),
            "return_pct_p05":percentile([x["return_pct"] for x in mc],.05),"max_drawdown_pct_p95":percentile([x["max_drawdown_pct"] for x in mc],.95)},
          "small_account_200":{"risk_budget_usdc":2.0,"stop_distance_pct_p95":p95_stop,"stress_cost_pct":cost_pct,
            "risk_limited_notional_usdc":round(risk_notional,2),"preliminary_max_leverage":preliminary_leverage,
            "required_margin_usdc":round(margin,2),"warning":"not live-approved; leverage does not increase risk-limited notional"},
          "verdict":"PAPER_RESEARCH_CANDIDATE" if not reasons else "LIVE_NOT_READY","reasons":reasons})
    return {"schema_version":1,"source":str(source),"costs_roundtrip_bps":{"base":12,"conservative":24,"stress":36},"candidates":rows,
      "portfolio_verdict":"LIVE_NOT_READY","note":"No strategy may be promoted until native Ostium execution parity and gap/liquidation risk are measured."}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--source",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--runs",type=int,default=10000); a=p.parse_args()
    result=evaluate(a.source,a.runs); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"portfolio_verdict":result["portfolio_verdict"],"candidates":[{"strategy":x["strategy"],"project":x["project"],"holdout_stress":x["holdout_stress"],"mc":x["monte_carlo"],"leverage":x["small_account_200"]} for x in result["candidates"]]},indent=2))
if __name__=="__main__": main()
