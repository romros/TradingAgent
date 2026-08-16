#!/usr/bin/env python3
"""Compare native SQ orders with the frozen Python SMA200/three-down engine."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import load,simulate

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sq_orders(path):
 with path.open(newline='',encoding='utf-8-sig') as stream:rows=list(csv.DictReader(stream,delimiter=';'))
 return [{'entry':row['Open time'][:10].replace('.','-'),'exit':row['Close time'][:10].replace('.','-')} for row in rows if row['Type']=='Buy']
def compare(source:Path,orders:Path,spec:Path,receipt:Path):
 configuration=json.loads(spec.read_text());run=json.loads(receipt.read_text())
 if run['decision']!='PASS_SUPERVISED_RETEST' or run['candidate_id']!='MULTI_ASSET_SMA200_THREE_DOWN_HOLD10_V1' or run['holdout_accessed'] is not False or sha(orders)!=run['orders_csv_sha256']:raise ValueError('invalid native SQ lineage')
 variant={'family':'trend_pullback','sma':200,'down_days':3,'hold_days':10};bars=load(source);python=simulate(bars,variant,configuration['economics']);native=sq_orders(orders)
 comparison_from=bars[201]['date'];early_native=[row for row in native if row['entry']<comparison_from]
 python_pairs=[(row['entry'],row['exit']) for row in python if row['entry']>=comparison_from];native_pairs=[(row['entry'],row['exit']) for row in native if row['entry']>=comparison_from]
 missing=sorted(set(python_pairs)-set(native_pairs));extra=sorted(set(native_pairs)-set(python_pairs))
 return {'schema_version':1,'decision':'PASS_EXACT_SQ_PYTHON_SIGNAL_PARITY' if not missing and not extra and len(python_pairs)==len(native_pairs) else 'FAIL_SQ_PYTHON_SIGNAL_PARITY','source_sha256':sha(source),'orders_sha256':sha(orders),'retest_receipt_sha256':sha(receipt),'comparison_from':comparison_from,'warmup_policy':'research source must accumulate 200 complete sessions; first possible entry is row index 201','native_pre_research_warmup_trades':early_native,'python_trades':len(python_pairs),'sq_trades':len(native_pairs),'missing_in_sq':missing,'extra_in_sq':extra,'entry_exit_pairs_exact':python_pairs==native_pairs,'price_parity_required':False,'price_note':'signal/date parity only; native and adjusted/canonical price levels can differ','paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--orders',type=Path,required=True);p.add_argument('--spec',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=compare(a.source,a.orders,a.spec,a.receipt);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
