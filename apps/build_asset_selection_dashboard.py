#!/usr/bin/env python3
"""Build the read-only asset-selection payload from frozen research artifacts."""
from __future__ import annotations
import csv, datetime as dt, json, sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; LAB=ROOT/'lab/sq_bridge'; sys.path.insert(0,str(LAB))
from three_strategy_portfolio_v1 import load_msft, msft_sleeve
from two_strategy_portfolio_v1 import load_cat, cat_sleeve, sxr8_sleeve
from cat_0168_transfer_screen_v1 import frozen_orders
from turn_of_month_screen_v1 import load as load_sq

SXR8=ROOT/'data/ibkr_sq_v2/preflight/SXR8_DE_ADJUSTED_D1_2012_2024.csv'
CAT=ROOT/'data/ibkr_sq_v2/preflight/CATUSUSD_NYSE_RTH_D1_2024.csv'
MSFT=ROOT/'data/ibkr_sq_v2/preflight/MSFT_ADJUSTED_D1_through_2024.csv'
PORT=ROOT/'data/ibkr_sq_v2/three_strategy_portfolio/sxr8_cat_msft_v1.json'
ANATOMY=ROOT/'lab/out/alquimia/capitulation_anatomy_v1.json'
OUT=ROOT/'data/shadow/asset_selection_dashboard.json'

def monthly_curve(events):
    pnl=defaultdict(float)
    for x in events:pnl[x['date'][:7]]+=x['pnl']
    value=100.; out=[]
    for year in range(2022,2025):
      for number in range(1,13):
        month=f'{year}-{number:02d}';value+=pnl[month]/10.;out.append({'date':month,'value':round(value,4)})
    return out

def asset_curve(path, header):
    closes={}
    with path.open(newline='') as f:
        rows=csv.DictReader(f) if header else csv.reader(f)
        for r in rows:
            date=(r['date'] if header else r[0]).replace('.','-'); close=float(r['close'] if header else r[5])
            if '2022-01-01'<=date<='2024-12-31':closes[date[:7]]=(date,close)
    values=[x[1] for _,x in sorted(closes.items())]; base=values[0]
    return [{'date':m,'value':round(v[1]/base*100,4)} for m,v in sorted(closes.items())]

def exposure_sets(catrows, msftrows):
    start,end=dt.date(2022,1,1),dt.date(2024,12,31)
    sx=load_sq(SXR8); sdays=sorted(d for d in sx if start<=d<=end); months=defaultdict(list)
    for d in sdays:months[(d.year,d.month)].append(d)
    sxactive=set(); keys=sorted(months)
    for i,key in enumerate(keys[:-1]):
      nxt=keys[i+1]
      if nxt[0]*12+nxt[1]==key[0]*12+key[1]+1 and len(months[nxt])>=4:
        a,b=months[key][-1],months[nxt][3];sxactive.update(d for d in sdays if a<=d<=b)
    catdays=[dt.date.fromisoformat(x['date'].replace('.','-')) for x in catrows if '2022.01.01'<=x['date']<='2024.12.31']
    catactive=set()
    for o in frozen_orders(catrows,'2022.01.01','2024.12.31'):
      a,b=o['open_time'].date(),o['close_time'].date();catactive.update(d for d in catdays if a<=d<=b)
    msdays=[x['date'] for x in msft_sleeve(msftrows,1000,'2022.01.01','2024.12.31')]
    msactive={dt.date.fromisoformat(x) for x in msdays}
    calendars={'SXR8':set(sdays),'CAT':set(catdays),'MSFT_CAPITULATION':{x['date'] for x in msftrows if start<=x['date']<=end}}
    return {'SXR8':sxactive,'CAT':catactive,'MSFT_CAPITULATION':msactive},calendars

def main():
    portfolio=json.loads(PORT.read_text()); forward=portfolio['forward_2022_2024']['strategies']
    anatomy=next(x for x in json.loads(ANATOMY.read_text())['assets'] if x['asset']=='MSFT')
    catrows=load_cat([CAT]); msftrows=load_msft(MSFT)
    events={'SXR8':sxr8_sleeve(SXR8,1000,'2022.01.01','2024.12.31'),
            'CAT':cat_sleeve(catrows,1000,'2022.01.01','2024.12.31'),
            'MSFT_CAPITULATION':msft_sleeve(msftrows,1000,'2022.01.01','2024.12.31')}
    active,calendars=exposure_sets(catrows,msftrows);weights={'SXR8':40,'CAT':40,'MSFT_CAPITULATION':20}
    curves={'SXR8':asset_curve(SXR8,False),'CAT':asset_curve(CAT,True),'MSFT_CAPITULATION':asset_curve(MSFT,False)}
    config={
      'SXR8':('SXR8','ETF UCITS S&P 500','40%','Efecte calendari diferent dels senyals tècnics; nucli diversificat i negociable a Europa.'),
      'CAT':('CAT','Caterpillar','40%','Tendència amb disminució de pressió venedora; edge més rendible però també més drawdown.'),
      'MSFT_CAPITULATION':('MSFT','Microsoft','20%','Reversió oportunista després d’una caiguda extrema; baixa correlació i drawdown petit.')}
    assets=[]
    for key,(symbol,kind,weight,reason) in config.items():
      item={'key':key,'symbol':symbol,'kind':kind,'allocation':weight,'reason':reason,
            'comparison_period':'2022–2024','metrics':forward[key],
            'chart':{'strategy':monthly_curve(events[key]),'asset':curves[key],
                     'note':'Índex 100. Estratègia amb costos vs comprar i mantenir l’actiu; escales comparables, no euros absoluts.'}}
      sessions=len(calendars[key]); exposed=len(active[key]); item['exposure']={
        'sessions':sessions,'exposed_sessions':exposed,'time_in_market_pct':round(100*exposed/sessions,2),
        'return_per_exposure_fraction_pct':round(forward[key]['return_pct']/(exposed/sessions),2)}
      if key=='MSFT_CAPITULATION':
        item['long_history']={'period':f"{anatomy['first_signal']} → {anatomy['last_signal']}",
          **anatomy['canonical_1d']['stress'],'empirical_p':anatomy['random_year_matched_empirical_p'],
          'bootstrap_ev_95_bps':anatomy['canonical_expectancy_bootstrap_95_ci_bps']}
      assets.append(item)
    all_days=sorted(set().union(*calendars.values()));used=[];overlap=0
    for day in all_days:
      deployed=sum(weights[k] for k in weights if day in active[k]);used.append(deployed);overlap+=sum(day in active[k] for k in weights)>=2
    payload={'schema_version':1,'classification':'READ_ONLY_RESEARCH_EXPLANATION','allocation':'40/40/20 diagnostic, no optimitzada',
      'assets':assets,'correlations':portfolio['forward_2022_2024']['pairwise_monthly_correlation'],
      'shared_account':{'policy':'Pesos màxims fixos 40/40/20; efectiu quan no hi ha senyal; sense reutilització retrospectiva',
        'average_capital_deployed_pct':round(sum(used)/len(used),2),'maximum_capital_deployed_pct':max(used),
        'sessions_with_two_or_more_strategies':overlap,'calendar_sessions':len(all_days),
        'return_pct':portfolio['core_satellite_40_40_20_2022_2024']['portfolio']['return_pct'],
        'max_drawdown_pct':portfolio['core_satellite_40_40_20_2022_2024']['portfolio']['max_drawdown_pct_closed_equity']},
      'warning':'Backtest històric, no promesa. 2024–2026 de MSFT ja és monitoratge consumit; no és holdout verge.'}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'output':str(OUT),'assets':len(assets)},indent=2))
if __name__=='__main__':main()
