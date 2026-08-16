#!/usr/bin/env python3
"""Semantic verifier for frozen random-generation SQ discovery projects."""
from __future__ import annotations
import json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
from lab.sq_bridge.alquimia_project import SEARCH_PROFILES

def verify(path:Path,manifest:dict)->dict:
 with zipfile.ZipFile(path) as z:
  config=ET.fromstring(z.read('config.xml'));tasks=config.findall('./Tasks/Task')
  if len(tasks)!=1 or tasks[0].get('type')!='Build':raise ValueError('ONE_BUILD_TASK_REQUIRED')
  root=ET.fromstring(z.read(tasks[0].get('taskXMLFile')))
 mode=root.find('./WhatToBuild/BuildMode');setup=root.find('./Data/Setups/Setup');chart=setup.find('./Chart') if setup is not None else None
 if mode is None or mode.get('generationType')!='random-generation':raise ValueError('NOT_RANDOM_GENERATION')
 active=[b.get('key') for b in root.findall('.//Block') if b.get('use')=='true'];expected=SEARCH_PROFILES[manifest['search_profile']]
 conditions={}
 for condition in root.findall('./Rankings/Conditions/Condition'):
  column=condition.find('./Left-Side/Column-Value')
  comparator=condition.find('./Comparator')
  value=condition.find('./Right-Side/Numeric-Value')
  if column is None or comparator is None or value is None or comparator.get('value')!='>':
   raise ValueError('UNSUPPORTED_RANKING_CONDITION')
  conditions[column.get('column')]=value.get('value')
 methods=[m for m in setup.findall('./Commissions/Method') if m.get('use')=='true']
 fixed=[m for m in root.findall('./RiskMoneyManagement/MoneyManagement/Method') if m.get('use')=='true']
 sides=root.find('./WhatToBuild/MarketSides');stop=root.find('./Rankings/StopCondition')
 shape={'generation_type':mode.get('generationType'),'project_name':manifest['project_name'],'symbol':chart.get('symbol'),'timeframe':chart.get('timeframe'),'train_from':setup.get('dateFrom'),'train_to':setup.get('dateTo'),'market_side':sides.get('type'),'active_blocks':sorted(active),'minimum_trades':conditions.get('NumberOfTrades'),'minimum_profit_factor':conditions.get('ProfitFactor'),'accepted_limit':int(root.findtext('./Rankings/MaxStrategies')),'wall_hours':int(stop.get('hours')),'wall_minutes':int(stop.get('minutes'))}
 if (chart.get('symbol')!=manifest['sq_symbol'] or chart.get('timeframe')!=manifest['timeframe'] or chart.get('spread')!='0' or setup.get('slippage')!='0' or setup.get('dateFrom')!=manifest['periods']['train_from'].replace('-','.') or setup.get('dateTo')!=manifest['periods']['train_to'].replace('-','.') or set(active)!=expected or sides.get('type')!=manifest['market_side'] or set(conditions)!={'NumberOfTrades','ProfitFactor'} or len(methods)!=1 or methods[0].get('type')!='None' or len(fixed)!=1 or fixed[0].get('type')!='FixedSize' or fixed[0].findtext("./Params/Param[@key='Size']")!='1' or root.findtext('./RiskMoneyManagement/MoneyManagement/InitialCapital')!=str(manifest['discovery_initial_capital']) or root.findtext('./WhatToBuild/SLPTOptions/SLRequired')!='true' or shape['accepted_limit']!=manifest['accepted_limit']):raise ValueError('RANDOM_PROJECT_CONTRACT_MISMATCH')
 return shape
def main():
 import argparse;p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);a=p.parse_args();print(json.dumps(verify(a.project,json.loads(a.manifest.read_text())),indent=2))
if __name__=='__main__':main()
