#!/usr/bin/env python3
"""Apply explicit indicative IBKR costs and GBPUSD FX to an SQ Composer run."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from sq_portfolio_daily_equity_v1 import decode

ACCEPTED=re.compile(r"Order ACCEPTED '([^/]+)/.*?OpenTime=([0-9.]+) [^|]+\|OpenPrice=\$([0-9.]+).*?\]=([0-9.]+)")
SCENARIOS={
 'tiered_indicative':{'us_order':.35,'us_bps_side':2,'uk_order_gbp':1.25,'uk_bps_side':5,'fx_bps_side':2},
 'fixed_indicative':{'us_order':1.0,'us_bps_side':5,'uk_order_gbp':3.0,'uk_bps_side':7.5,'fx_bps_side':5},
 'stress':{'us_order':1.0,'us_bps_side':10,'uk_order_gbp':3.0,'uk_bps_side':10,'fx_bps_side':10},
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fx(path):
    with path.open(newline='') as s:return {r['date']:float(r['usd_per_gbp']) for r in csv.DictReader(s)}
def asof(series,day):
    keys=[k for k in series if k<=day]
    if not keys:raise ValueError(f'no FX on/before {day}')
    return series[max(keys)]
def audit(sqx:Path,fx_path:Path,capital=2000):
    with zipfile.ZipFile(sqx) as z:
        root=ET.fromstring(z.read('settings.xml'));log=root.find('.//PortfolioComposerLog').text
        pnl={n:decode(z.read(n))[-1][1] for n in z.namelist() if n.endswith('dailyEquity.bin')}
    accepted_lines=list(dict.fromkeys(line for line in log.splitlines() if 'Order ACCEPTED' in line))
    orders=[]
    for line in accepted_lines:
        m=ACCEPTED.search(line)
        if m:
            year,month,day=m.group(2).split('.')
            orders.append({'strategy':m.group(1),'date':f'{year}-{month}-{day}','price':float(m.group(3)),'size_sq':float(m.group(4))})
    if len(orders)!=len(accepted_lines):raise ValueError('accepted-order parse mismatch')
    gold=[o for o in orders if o['strategy'].startswith('SGLN_')]
    if len(gold)!=1:raise ValueError('expected one SGLN position')
    series=fx(fx_path);g=gold[0];entry_fx=asof(series,g['date']);end_fx=asof(series,'2024-12-31')
    gold_member=next(k for k in pnl if 'SGLN_' in k);sq_gold_pnl=pnl[gold_member]
    end_gbp=g['price']+sq_gold_pnl/g['size_sq'];actual_size=int(500/(g['price']*entry_fx))
    gold_gross_usd=actual_size*(end_gbp*end_fx-g['price']*entry_fx)
    portfolio_member=next(k for k in pnl if k=='Results/Portfolio/dailyEquity.bin');sq_gross=pnl[portfolio_member]
    corrected_gross=sq_gross-sq_gold_pnl+gold_gross_usd
    us=[o for o in orders if o not in gold];us_entry_notional=sum(o['price']*o['size_sq'] for o in us)
    results={}
    for name,c in SCENARIOS.items():
        us_cost=2*len(us)*c['us_order']+2*us_entry_notional*c['us_bps_side']/10000
        gold_entry_usd=actual_size*g['price']*entry_fx;gold_exit_usd=actual_size*end_gbp*end_fx
        gold_cost=(2*c['uk_order_gbp']*entry_fx+(gold_entry_usd+gold_exit_usd)*(c['uk_bps_side']+c['fx_bps_side'])/10000)
        net=corrected_gross-us_cost-gold_cost
        results[name]={'gross_pnl_fx_corrected':round(corrected_gross,6),'estimated_cost':round(us_cost+gold_cost,6),'net_pnl':round(net,6),'net_return_pct':round(net/capital*100,6)}
    return {'schema_version':1,'decision':'PASS_INDICATIVE_PRE_ACCOUNT_GATE','period':'2022-01-01/2024-12-31','capital':capital,'sqx_sha256':sha(sqx),'fx_sha256':sha(fx_path),'fx_source_urls':['https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A','https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A'],'commission_source_url':'https://www.interactivebrokers.com/en/pricing/commissions-stocks-europe.php?re=europe','accepted_positions':len(orders),'us_positions':len(us),'sgln_positions':1,'sgln_sq_size_wrong_currency':g['size_sq'],'sgln_fx_corrected_size':actual_size,'sgln_entry_usd_per_gbp':entry_fx,'sgln_end_usd_per_gbp':end_fx,'sgln_end_price_gbp_derived':end_gbp,'sq_neutral_gross_return_pct':sq_gross/capital*100,'fx_corrected_neutral_gross_return_pct':corrected_gross/capital*100,'scenarios':results,'limitations':['Commission schedules are indicative public models; the actual account plan and venue fees require an IBKR account statement.','Costs conservatively charge a round trip for every accepted position, including positions marked at EndTest.','Closed-equity costs are deducted from final PnL; a net daily mark-to-market drawdown is not claimed.','No paper or live trading is authorized.'],'paper_authorized':False,'live_authorized':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('sqx',type=Path);p.add_argument('--fx',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.sqx,a.fx);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
