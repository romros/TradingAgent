#!/usr/bin/env python3
"""Aggregate frozen endpoints and a conservative drawdown budget for five edges."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def evaluate(spec_path):
 spec=json.loads(spec_path.read_text());legacy_path=ROOT/spec['inputs']['legacy'];new_path=ROOT/spec['inputs']['new'];legacy=json.loads(legacy_path.read_text());new=json.loads(new_path.read_text());allocation=spec['allocation'];legacy_cap=allocation['legacy_four_edge_portfolio_usd'];new_cap=allocation['multi_asset_trend_pullback_usd'];total=legacy_cap+new_cap
 if legacy['initial_capital_usd']!=legacy_cap or legacy['period']!=spec['period']:raise ValueError('legacy portfolio contract mismatch')
 new_result=new['results'][str(new_cap)]['common_2022_2024'];legacy_stress=legacy['scenarios']['stress'];pnl=(legacy_stress['final_equity_usd']-legacy_cap)+new_result['net_pnl_usd'];net_return=pnl/total*100
 # This is a sizing/risk budget, not an observed combined-equity drawdown.
 dd_budget=(legacy_cap/total*legacy_stress['daily_mtm_max_drawdown_pct']+new_cap/total*new_result['maximum_mark_to_market_drawdown_pct'])
 checks={'positive_return':net_return>spec['gate']['minimum_net_return_pct'],'drawdown_budget':dd_budget<=spec['gate']['maximum_drawdown_budget_pct']}
 return {'schema_version':1,'decision':'PASS_FIVE_EDGE_THEORETICAL_PORTFOLIO' if all(checks.values()) else 'FAIL_FIVE_EDGE_THEORETICAL_PORTFOLIO','period':spec['period'],'initial_capital_usd':total,'allocation':allocation,'legacy_four_edge_stress_net_pnl_usd':legacy_stress['final_equity_usd']-legacy_cap,'new_edge_stress_net_pnl_usd':new_result['net_pnl_usd'],'combined_net_pnl_usd':pnl,'combined_net_return_pct':net_return,'weighted_individual_drawdown_budget_pct':dd_budget,'drawdown_budget_is_not_observed_portfolio_drawdown':True,'legacy_input_sha256':sha(legacy_path),'new_input_sha256':sha(new_path),'checks':checks,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=evaluate(a.spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
