#!/usr/bin/env python3
"""Fixed equal-sleeve admission diagnostic for confirmed gold TSMOM edge."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cat_msft_jpm_portfolio_v1 import load_cat,load_jpm,jpm_sleeve
from three_strategy_portfolio_v1 import load_msft,msft_sleeve
from two_strategy_portfolio_v1 import cat_sleeve,metrics,monthly_correlation
from gold_tsmom_confirmation_screen_v1 import load as load_gold,monthly as gold_monthly
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def gold_sleeve(path,capital,start,end):
 lo,hi=map(dt.date.fromisoformat,(start.replace('.','-'),end.replace('.','-')));equity=float(capital);out=[]
 for day,value,_,_ in gold_monthly(load_gold(path),.00175):
  if not lo<=day<=hi:continue
  pnl=equity*value;equity+=pnl;out.append({'date':day.isoformat(),'pnl':pnl,'equity':equity,'return':value})
 return out
def evaluate(cat,msft,jpm,gold,capital,start,end):
 legs={'CAT_0168':cat_sleeve(cat,capital,start,end),'MSFT_CAPITULATION':msft_sleeve(msft,capital,start,end),'JPM_MOMENTUM60':jpm_sleeve(jpm,capital,start,end),'SGLN_TSMOM12':gold_sleeve(gold,capital,start,end)};names=list(legs);pairs={}
 for i,left in enumerate(names):
  for right in names[i+1:]:pairs[f'{left}__{right}']=monthly_correlation(legs[left],legs[right])
 events=[{'date':x['date'],'pnl':x['pnl']} for rows in legs.values() for x in rows]
 return {'strategies':{k:metrics(v,capital) for k,v in legs.items()},'portfolio':metrics(events,capital*4),'pairwise_monthly_correlation':pairs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--cat',type=Path,required=True);p.add_argument('--msft',type=Path,required=True);p.add_argument('--jpm',type=Path,required=True);p.add_argument('--gold',type=Path,required=True);p.add_argument('--core',type=Path,required=True);p.add_argument('--capital',type=float,default=1000);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cat=load_cat(a.cat);msft=load_msft(a.msft);jpm=load_jpm(a.jpm);full=evaluate(cat,msft,jpm,a.gold,a.capital,'2019.01.01','2024.12.31');forward=evaluate(cat,msft,jpm,a.gold,a.capital,'2022.01.01','2024.12.31');core=json.loads(a.core.read_text())['forward_2022_2024'];gold_corr=[abs(v['correlation_zero_when_inactive']) for k,v in forward['pairwise_monthly_correlation'].items() if 'SGLN' in k and v['correlation_zero_when_inactive'] is not None];positive=all(x['return_pct']>0 for x in forward['strategies'].values());passed=positive and max(gold_corr,default=1)<.5 and forward['portfolio']['max_drawdown_pct_closed_equity']<=core['portfolio']['max_drawdown_pct_closed_equity'] and forward['portfolio']['profit_factor']>=core['portfolio']['profit_factor']
 result={'schema_version':1,'classification':'PASS_EDGE_AS_CAPPED_PORTFOLIO_SLEEVE' if passed else 'REJECT_GOLD_PORTFOLIO_ADMISSION','allocation':'four equal sleeves (25% each), fixed before this diagnostic; no weight search','standalone_recent_evidence':'data/ibkr_sq_v2/gold_tsmom_confirmation_v1/screen_v1.json','standalone_recent_disclosure':'signal edge confirmed but standalone 100% DD gate failed at 25.82%; this test cannot erase that result','full_2019_2024':full,'forward_2022_2024':forward,'core_forward_2022_2024':core,'maximum_abs_gold_pairwise_correlation':max(gold_corr,default=None),'inputs_sha256':{str(x):sha(x) for x in (a.cat,a.msft,a.jpm,a.gold,a.core)},'historical_portfolio_diagnostic_only':True,'paper_authorized':False,'live_authorized':False};a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'classification':result['classification'],'forward_strategies':forward['strategies'],'forward_portfolio':forward['portfolio'],'core_portfolio':core['portfolio'],'max_gold_correlation':result['maximum_abs_gold_pairwise_correlation']},indent=2))
if __name__=='__main__':main()
