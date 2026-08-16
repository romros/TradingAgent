#!/usr/bin/env python3
"""Freeze up to five structurally distinct NFLX representatives using train only."""
import argparse,json
from pathlib import Path
def select(inventory):
 pareto=set(inventory['pareto_candidates']);eligible=[r for r in inventory['candidates'] if r['strategy'] in pareto and r['trades']>=35 and r['profit']>0 and r['drawdown']>0]
 eligible.sort(key=lambda r:(-r['profit_drawdown_ratio'],-r['fitness'],-r['profit'],r['complexity'],r['strategy']))
 chosen=[];families=set();entries=set()
 for r in eligible:
  if r['structural_family_sha256'] in families or r['entry_indicator_archetype_sha256'] in entries:continue
  chosen.append({k:r[k] for k in ('strategy','file','sqx_sha256','structural_family_sha256','entry_indicator_archetype_sha256','trades','profit','drawdown','profit_drawdown_ratio','fitness','complexity','entry_indicator_types')});families.add(r['structural_family_sha256']);entries.add(r['entry_indicator_archetype_sha256'])
  if len(chosen)==5:break
 return {'schema_version':1,'decision':'PASS_FREEZE_NFLX_TRAIN_REPRESENTATIVES' if chosen else 'REJECT_NO_NFLX_TRAIN_REPRESENTATIVE','selection_rule':'Pareto only; >=35 trades; positive profit; rank profit/DD, fitness, profit, complexity, name; unique structural and entry-indicator archetypes','inventory_sha256':inventory['source_inventory_sha256'],'selected_count':len(chosen),'selected':chosen,'validation_accessed':False,'oos_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=select(json.loads(a.inventory.read_text()));a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
