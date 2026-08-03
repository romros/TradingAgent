#!/usr/bin/env python3
"""Reject SQ contracts that do not implement the preregistered hypothesis shape."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def ops(node): return {node['op']}|set().union(*(ops(x) for x in node.get('children',[])))
def comparator(signal,op,left,right):
 for node in signal.get('children',[]):
  if node.get('op')==op and len(node.get('children',[]))==2:
   a,b=node['children']
   if a.get('op')==left and b.get('op')==right:return a,b
   if a.get('op')==right and b.get('op')==left:return b,a
 return None

def prior_extreme(node,computed_from):
 params=node.get('params',{})
 return params.get('#Shift#')==2 and params.get('#ComputedFrom#')==computed_from and isinstance(params.get('#Period#'),int) and params['#Period#']>1

def closed_signal_bar(node): return node.get('params',{}).get('#Shift#')==1

def sweep_reclaim(contract):
 reasons=[]
 if not contract.get('supported'): reasons.append('TRANSLATION_UNSUPPORTED')
 entries=contract.get('entries',{})
 for direction,extreme,range_op,computed_from,break_op,reclaim_op in (
  ('long','Low','Lowest',3,'IsLower','IsGreater'),('short','High','Highest',2,'IsGreater','IsLower')):
  entry=entries.get(direction)
  if not entry: reasons.append(f'{direction.upper()}_ENTRY_MISSING'); continue
  signal=entry['signal']; shape=ops(signal)
  required={'AND',extreme,'Close',range_op,break_op,reclaim_op}
  if not required.issubset(shape): reasons.append(f'{direction.upper()}_OPS_MISMATCH')
  if signal.get('op')!='AND' or len(signal.get('children',[]))!=2: reasons.append(f'{direction.upper()}_NOT_EXACTLY_TWO_CONDITIONS')
  break_pair=comparator(signal,break_op,extreme,range_op)
  reclaim_pair=comparator(signal,reclaim_op,'Close',range_op)
  if break_pair is None: reasons.append(f'{direction.upper()}_BREAK_SHAPE')
  if reclaim_pair is None: reasons.append(f'{direction.upper()}_RECLAIM_SHAPE')
  if break_pair is not None and not closed_signal_bar(break_pair[0]): reasons.append(f'{direction.upper()}_BREAK_NOT_CLOSED_SIGNAL_BAR')
  if reclaim_pair is not None and not closed_signal_bar(reclaim_pair[0]): reasons.append(f'{direction.upper()}_RECLAIM_NOT_CLOSED_SIGNAL_BAR')
  if break_pair is not None and reclaim_pair is not None and break_pair[1]!=reclaim_pair[1]: reasons.append(f'{direction.upper()}_RANGE_MISMATCH')
  if break_pair is not None and not prior_extreme(break_pair[1],computed_from): reasons.append(f'{direction.upper()}_RANGE_NOT_PRIOR_EXTREME')
 return {'strategy':contract.get('strategy_name'),'hypothesis':'xau-h4-sweep-reclaim-v4',
  'passed':not reasons,'reasons':reasons,'translation_status':contract.get('translation_status')}

def main():
 p=argparse.ArgumentParser();p.add_argument('contract',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();result=sweep_reclaim(json.loads(a.contract.read_text())); rendered=json.dumps(result,indent=2)+'\n'
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(rendered)
 print(rendered,end='');raise SystemExit(0 if result['passed'] else 2)
if __name__=='__main__':main()
