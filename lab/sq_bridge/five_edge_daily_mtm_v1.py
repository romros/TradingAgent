#!/usr/bin/env python3
"""Synchronize the frozen four-edge and multi-asset daily equity curves."""
from __future__ import annotations

import argparse
import json
import zipfile
from bisect import bisect_right
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.four_edge_net_mtm_audit_v1 import (
    ACCEPTED, CAPITAL, END, EXPECTED_FX, EXPECTED_SQX, SLEEVE, START,
    asof, load_fx, sha,
)
from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import ROOT, load
from lab.sq_bridge.multi_asset_shared_capital_v1 import run
from lab.sq_bridge.sq_portfolio_daily_equity_v1 import decode


def legacy_stress_curve(sqx: Path, fx_path: Path) -> list[tuple[date, float]]:
    if sha(sqx) != EXPECTED_SQX or sha(fx_path) != EXPECTED_FX:
        raise ValueError("frozen legacy input hash mismatch")
    fx_days, fx_values = load_fx(fx_path)
    with zipfile.ZipFile(sqx) as archive:
        members = {n: decode(archive.read(n)) for n in archive.namelist() if n.endswith("dailyEquity.bin")}
        log = ET.fromstring(archive.read("settings.xml")).find(".//PortfolioComposerLog").text or ""
    portfolio = {d: pnl for d, pnl in members["Results/Portfolio/dailyEquity.bin"] if START <= d <= END}
    gold_name = next(n for n in members if "SGLN_" in n)
    gold = sorted((d, pnl) for d, pnl in members[gold_name] if d <= END)
    gold_days, gold_pnls = [x[0] for x in gold], [x[1] for x in gold]
    lines = list(dict.fromkeys(line for line in log.splitlines() if "Order ACCEPTED" in line))
    orders = []
    for line in lines:
        match = ACCEPTED.search(line)
        if not match: raise ValueError("accepted-order parse mismatch")
        year, month, day = map(int, match.group(2).split("."))
        orders.append({"strategy":match.group(1),"date":date(year,month,day),"price":float(match.group(3)),"size":float(match.group(4))})
    gold_order = next(o for o in orders if o["strategy"].startswith("SGLN_"))
    entry_fx = asof(fx_days, fx_values, gold_order["date"])
    actual_gold_size = int(SLEEVE / (gold_order["price"] * entry_fx))
    # Frozen stress costs from sq_portfolio_ibkr_cost_fx_v1.
    from lab.sq_bridge.sq_portfolio_ibkr_cost_fx_v1 import SCENARIOS
    cost = SCENARIOS["stress"]
    dated_costs = {}
    for order in orders:
        if order is gold_order:
            notional=actual_gold_size*order["price"]*entry_fx
            full=2*cost["uk_order_gbp"]*entry_fx+2*notional*(cost["uk_bps_side"]+cost["fx_bps_side"])/10000
        else:
            notional=order["price"]*order["size"]
            full=2*cost["us_order"]+2*notional*cost["us_bps_side"]/10000
        dated_costs[order["date"]]=dated_costs.get(order["date"],0)+full
    rows=[]; accrued=0.0; events=sorted(dated_costs.items()); event_i=0
    for day in sorted(portfolio):
        while event_i<len(events) and events[event_i][0]<=day:
            accrued+=events[event_i][1]; event_i+=1
        gi=bisect_right(gold_days,day)-1; sq_gold=gold_pnls[gi] if gi>=0 else 0.0
        corrected=0.0 if day<gold_order["date"] else actual_gold_size*((gold_order["price"]+sq_gold/gold_order["size"])*asof(fx_days,fx_values,day)-gold_order["price"]*entry_fx)
        rows.append((day,CAPITAL+portfolio[day]-sq_gold+corrected-accrued))
    return rows


def drawdown(rows):
    peak=rows[0][1]; peak_day=rows[0][0]; maximum=0.0; pair=(peak_day,peak_day)
    for day,equity in rows:
        if equity>peak: peak,peak_day=equity,day
        value=(peak-equity)/peak*100
        if value>maximum: maximum,pair=value,(peak_day,day)
    return maximum,pair


def evaluate(spec_path: Path) -> dict:
    spec=json.loads(spec_path.read_text()); base=spec_path.parents[2]
    legacy=legacy_stress_curve(base/spec["inputs"]["legacy_sqx"],base/spec["inputs"]["legacy_fx"])
    strategy=json.loads((base/spec["inputs"]["strategy_spec"]).read_text())
    capital=json.loads((base/spec["inputs"]["capital_spec"]).read_text())
    data={asset:load(ROOT/path) for asset,path in strategy["assets"].items()}
    new=run(data,1000,"2022-01-01","2024-12-31",capital,include_daily_equity=True)
    new_map={date.fromisoformat(x["date"]):x["equity_usd"] for x in new.pop("daily_equity")}
    new_days=sorted(new_map); combined=[]
    for day,old_equity in legacy:
        ni=bisect_right(new_days,day)-1
        new_equity=1000.0 if ni<0 else new_map[new_days[ni]]
        combined.append((day,old_equity+new_equity))
    maximum,pair=drawdown(combined)
    return {"schema_version":1,"decision":"PASS_SYNCHRONIZED_DAILY_MTM" if combined[-1][1]>3000 and maximum<=15 else "FAIL_SYNCHRONIZED_DAILY_MTM","period":"2022-01-01/2024-12-31","initial_capital_usd":3000,"final_equity_usd":combined[-1][1],"net_return_pct":(combined[-1][1]/3000-1)*100,"daily_mtm_max_drawdown_pct":maximum,"drawdown_peak_date":str(pair[0]),"drawdown_trough_date":str(pair[1]),"daily_observations":len(combined),"accounting":"two fixed sleeves; no transfers; four-edge SQ daily MTM plus as-of multi-asset daily MTM","checks":{"positive_return":combined[-1][1]>3000,"drawdown_at_most_15_pct":maximum<=15},"paper_authorized":False,"live_authorized":False}


def main():
    p=argparse.ArgumentParser();p.add_argument("--spec",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();r=evaluate(a.spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r,indent=2))
if __name__=="__main__":main()
