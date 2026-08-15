#!/usr/bin/env python3
"""Audit Portfolio Composer orders without trusting headline statistics."""
from __future__ import annotations
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ORDER_RE=re.compile(r"Order ACCEPTED '([^/]+)/.*?OpenPrice=\$([0-9.]+).*?\]=([0-9.]+).*?Margin=\$([0-9.]+)")

def audit(path:Path,budget:float=500):
    with zipfile.ZipFile(path) as z:node=ET.fromstring(z.read('settings.xml')).find('.//PortfolioComposerLog')
    if node is None or not node.text:raise ValueError('PortfolioComposerLog missing')
    log=node.text;orders=[]
    accepted_lines=[line for line in log.splitlines() if 'Order ACCEPTED' in line]
    unique_lines=list(dict.fromkeys(accepted_lines))
    for line in unique_lines:
        match=ORDER_RE.search(line)
        if match:orders.append({'strategy':match.group(1),'open_price':float(match.group(2)),'size':float(match.group(3)),'notional':float(match.group(4))})
    raw_accepted=len(accepted_lines);accepted=len(unique_lines);rejected=log.count('Order REJECTED')
    if len(orders)!=accepted:raise ValueError(f'parsed {len(orders)} of {accepted} unique accepted orders')
    violations=[order for order in orders if order['notional']>budget+0.01 or order['size']!=int(order['size']) or order['size']<1]
    return {'schema_version':1,'decision':'PASS_FIXED_BUDGET_ORDER_AUDIT' if not violations and rejected==0 else 'FAIL_FIXED_BUDGET_ORDER_AUDIT','sqx_path':str(path),'sqx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'budget_per_strategy':budget,'raw_accepted_log_lines':raw_accepted,'duplicate_accepted_log_lines':raw_accepted-accepted,'accepted_unique_orders':accepted,'rejected_orders':rejected,'parsed_orders':len(orders),'maximum_notional':max((o['notional'] for o in orders),default=0),'violations':violations,'sizes_by_strategy':{s:sorted({o['size'] for o in orders if o['strategy']==s}) for s in sorted({o['strategy'] for o in orders})},'paper_authorized':False,'live_authorized':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('sqx',type=Path);parser.add_argument('--budget',type=float,default=500);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit(args.sqx,args.budget);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if result['decision'].startswith('FAIL'):raise SystemExit(1)
if __name__=='__main__':main()
