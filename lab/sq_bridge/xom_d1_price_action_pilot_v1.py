#!/usr/bin/env python3
"""Compile the frozen XOM D1 price-action discovery campaign."""
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path
from lab.sq_bridge.alquimia_project import build

ROOT=Path(__file__).resolve().parents[2]
SPEC=Path(__file__).with_suffix('.json')
SCAFFOLD=Path('/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx')
def epoch(value):return str(int(datetime.combine(date.fromisoformat(value),datetime.min.time(),tzinfo=timezone.utc).timestamp()*1000))
def compile_pilot(output_dir:Path):
 s=json.loads(SPEC.read_text());p=s['periods']
 if s['performance_accessed_before_freeze'] or s['promotion_allowed'] or s['volume_rules_allowed']:raise ValueError('campaign must remain blind, price-only and non-promotable')
 source=json.loads((ROOT/s['source_receipt']).read_text())
 if source['ticker']!='XOM' or source['end_exclusive']!='2025-01-01' or source['holdout_2025_accessed']:raise ValueError('source boundary mismatch')
 output_dir.mkdir(parents=True,exist_ok=True)
 registry={'markets':{'XOM':{'research_eligible':True,'sq_symbol':s['sq_symbol'],'discovery_timeframe':'D1','discovery_slippage':0,'discovery_commission_per_order':0,'sq_resource_clone_from':'BTCUSD_ALQ_H4','sq_prune_resources':True,'sq_resource_remove_attributes':['cloneFrom','sourceTimezone'],'sq_resource_attributes':{'source':'1','barType':'1','precision':'D1','timezone':'America/New_York','dateFrom':epoch(p['train_from']),'dateTo':epoch(p['sealed_oos_to']),'uSymbol':'XOM_IBKR_V1','uSymbolName':'XOM_IBKR_V1','removeWeekends':'false','broker':'-1'},'sq_instrument_attributes':{'instrument':'XOM_IBKR_V1','description':'XOM adjusted D1 gross research','tickSize':'0.000001','tickStep':'0.000001','minDistance':'0','tickValueInMoney':'0','dateFrom':'0','dateTo':'0','rows':'0','totalDays':'0','defaultSpread':'0','defaultSlippage':'0','decimals':'6','commissions':'','pointValue':'1','dataType':'1','recognizedFromOrders':'false','exchange':'NYSE','country':'US','sector':'Energy','swap':'','orderSizeMultiplier':'1','orderSizeStep':'1','broker':'-1'},'exit_at_end_of_day':False,'eod_exit_seconds':None,'signal_time_range_seconds':None,'exit_at_end_of_range':False,'maximum_trades_per_day':1,'venue_max_leverage':1}}}
 rp=output_dir/'frozen_market_registry.json';rp.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 method=json.loads((ROOT/'lab/sq_bridge/methodology_ibkr_sq_v1.json').read_text());method['methodology_id']=s['campaign_id'];method['capital_usdc']=1000;method['small_account']['canonical_capital_usdc']=1000
 for key in ('hypothesis_screen','discovery'):
  if key in method:method[key]['minimum_trades_train']=s['discovery']['minimum_train_trades'];method[key]['minimum_profit_factor_train']=s['discovery']['minimum_profit_factor_train']
 mp=output_dir/'frozen_methodology.json';mp.write_text(json.dumps(method,indent=2,sort_keys=True)+'\n')
 periods={'train_from':p['train_from'],'train_to':p['train_to'],'validation_from':p['validation_from'],'validation_to':p['validation_to'],'oos_from':p['sealed_oos_from'],'oos_to':p['sealed_oos_to'],'holdout_from':p['untouched_future_from'],'holdout_to':p['untouched_future_to']}
 cfx=output_dir/'project.cfx';d=s['discovery'];m=build(SCAFFOLD,cfx,'IBKR_XOM_D1_PRICE_ACTION_V1','XOM',rp,mp,date.fromisoformat(p['train_from']),date.fromisoformat(p['untouched_future_to']),d['accepted_limit'],d['search_profile'],d['generation'],d['attempt_budget'],d['wall_time_budget_minutes'],None,d['direction'],periods_override=periods)
 r={'decision':'PASS_THEORETICAL_DISCOVERY_READY','project':str(cfx),'manifest':str(cfx.with_suffix('.manifest.json')),'project_sha256':m['output_sha256'],'source_performance_accessed':False,'sqcli_started':False,'promotion_allowed':False,'paper_authorized':False,'live_authorized':False};(output_dir/'compile_receipt.json').write_text(json.dumps(r,indent=2)+'\n');return r
if __name__=='__main__':print(json.dumps(compile_pilot(ROOT/'data/ibkr_sq_v2/xom_d1_price_action_pilot'),indent=2))
