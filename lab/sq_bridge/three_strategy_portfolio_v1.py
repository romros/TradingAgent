#!/usr/bin/env python3
"""Frozen SXR8 + CAT 0.168 + MSFT capitulation closed-equity audit."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from two_strategy_portfolio_v1 import load_cat,cat_sleeve,sxr8_sleeve,metrics,monthly_correlation
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_msft(path):
 if '2025' in path.name:raise ValueError('2025 filename sealed for portfolio audit')
 out=[]
 for r in csv.reader(path.open()):
  day=dt.datetime.strptime(r[0],'%Y.%m.%d').date()
  if day.year>=2025:raise ValueError('2025 row sealed')
  out.append({'date':day,'open':float(r[2]),'high':float(r[3]),'low':float(r[4]),'close':float(r[5])})
 return out
def signals(rows):
 closes=[r['close'] for r in rows];out=[]
 for i in range(19,len(rows)-1):
  window=closes[i-19:i+1];mean=sum(window)/20;sd=(sum((x-mean)**2 for x in window)/20)**.5;body=rows[i]['close']/rows[i]['open']-1
  if body<-.02 and rows[i]['close']<mean-2*sd:out.append(i+1)
 return out
def msft_sleeve(rows,capital,start,end):
 a,b=dt.date.fromisoformat(start.replace('.','-')),dt.date.fromisoformat(end.replace('.','-'));equity=capital;out=[]
 for i in signals(rows):
  r=rows[i]
  if not a<=r['date']<=b:continue
  entry=r['open']*1.0015;exit_=r['close']*.9985;shares=math.floor(equity/entry)
  if shares<1:continue
  # 30 bps already includes the USD1/order minima at a USD1000 sleeve.
  pnl=shares*(exit_-entry);equity+=pnl;out.append({'date':r['date'].isoformat(),'pnl':pnl,'equity':equity,'return':pnl/(equity-pnl)})
 return out
def build(sxr8,cat_rows,msft_rows,capital,start,end):
 legs={'SXR8':sxr8_sleeve(sxr8,capital,start,end),'CAT':cat_sleeve(cat_rows,capital,start,end),'MSFT_CAPITULATION':msft_sleeve(msft_rows,capital,start,end)}
 events=[{'date':x['date'],'pnl':x['pnl']} for rows in legs.values() for x in rows];pair={}
 names=list(legs)
 for i,a in enumerate(names):
  for b in names[i+1:]:pair[f'{a}__{b}']=monthly_correlation(legs[a],legs[b])
 return {'strategies':{k:metrics(v,capital) for k,v in legs.items()},'portfolio':metrics(events,capital*3),'pairwise_monthly_correlation':pair}
def build_core_satellite(sxr8,cat_rows,msft_rows,start,end):
 capitals={'SXR8':1000.,'CAT':1000.,'MSFT_CAPITULATION':500.}
 legs={'SXR8':sxr8_sleeve(sxr8,capitals['SXR8'],start,end),'CAT':cat_sleeve(cat_rows,capitals['CAT'],start,end),'MSFT_CAPITULATION':msft_sleeve(msft_rows,capitals['MSFT_CAPITULATION'],start,end)}
 events=[{'date':x['date'],'pnl':x['pnl']} for rows in legs.values() for x in rows]
 return {'allocation_pct':{'SXR8':40,'CAT':40,'MSFT_CAPITULATION':20},'initial_capital':2500.,'strategies':{k:metrics(v,capitals[k]) for k,v in legs.items()},'portfolio':metrics(events,2500.)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--sxr8',type=Path,required=True);ap.add_argument('--cat',type=Path,required=True);ap.add_argument('--msft',type=Path,required=True);ap.add_argument('--capital',type=float,default=1000);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();cat=load_cat([a.cat]);msft=load_msft(a.msft)
 full=build(a.sxr8,cat,msft,a.capital,'2019.01.01','2024.12.31');forward=build(a.sxr8,cat,msft,a.capital,'2022.01.01','2024.12.31');ms=forward['strategies']['MSFT_CAPITULATION'];maxcorr=max(abs(x['correlation_zero_when_inactive']) for k,x in forward['pairwise_monthly_correlation'].items() if k.startswith('MSFT') or k.endswith('MSFT_CAPITULATION'));passed=ms['return_pct']>0 and (ms['profit_factor'] or 0)>1.1 and maxcorr<.5
 core=build_core_satellite(a.sxr8,cat,msft,'2022.01.01','2024.12.31')
 report={'schema_version':1,'classification':'THREE_EDGE_RESEARCH_PORTFOLIO' if passed else 'REJECT_THIRD_EDGE_PORTFOLIO','rule_changed':False,'capital_per_sleeve':a.capital,'costs':'SXR8 and CAT prior stress contracts; MSFT 30bps round-trip','full_2019_2024':full,'forward_2022_2024':forward,'core_satellite_40_40_20_2022_2024':core,'allocation_policy':'Equal sleeves are the neutral audit. 40/40/20 is one preregistered-style operational diagnostic, not a weight optimization grid.','maximum_abs_msft_pairwise_correlation':maxcorr,'inputs_sha256':{str(p):sha(p) for p in (a.sxr8,a.cat,a.msft)},'monitoring_disclosure':'Existing capitulation audit already consumed 2024-2026 monitoring; this is not a fresh holdout claim. Portfolio performance here stops at 2024.','holdout_2025_accessed_by_this_run':False,'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'classification':report['classification'],'MSFT':ms,'equal_portfolio':forward['portfolio'],'core_satellite':core['portfolio'],'maxcorr':maxcorr},indent=2))
if __name__=='__main__':main()
