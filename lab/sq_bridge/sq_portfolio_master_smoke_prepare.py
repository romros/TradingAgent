#!/usr/bin/env python3
"""Prepare a disposable Portfolio Master capability smoke, never research evidence."""
from __future__ import annotations
import hashlib,json,shutil,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('/tmp/portfolio-master.cfx')
OUT=ROOT/'data/ibkr_sq_v2/sq_portfolio_master_smoke'
CAT=Path('/mnt/volume-SQ/user/projects/IBKR_V2_CAT_D1_VAL_0168/databanks/Results/Strategy 0.168.sqx')
CONTROL=Path('/mnt/volume-SQ/user/projects/ALQUIMIA_MSFT_D1_TREND_LONG/databanks/Results/Strategy 0.14.sqx')
NAME='ALQUIMIA_PORTFOLIO_MASTER_CAPABILITY_SMOKE'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if not SOURCE.exists():raise SystemExit('copy /tmp/portfolio-master.cfx first')
 OUT.mkdir(parents=True,exist_ok=True); members={}
 with zipfile.ZipFile(SOURCE) as z:
  for name in z.namelist():members[name]=z.read(name)
 project=ET.fromstring(members['config.xml']);project.set('name',NAME);project.set('version','143.2708')
 task=ET.fromstring(members['AutomaticPortfolioBuilder-Task1.xml']);s=task.find('AutomaticPortfolioBuilder')
 values={'SearchType':'bruteforce','MinStrategies':'2','MaxStrategies':'2','MaxStrategiesDatabank':'4',
         'DateRange':'full','FitnessType':'ReturnDD','CorrMax':'1.0','CorrAllowNegative':'true',
         'FilterOverlappingTrades':'false','MMMethodOptional':'false'}
 for key,value in values.items():s.find(key).text=value
 for c in s.findall('./Conditions/Condition'):c.set('use','false')
 mm=s.find('./MoneyManagement/InitialCapital');mm.text='1000'
 target=OUT/'project.cfx'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('config.xml',ET.tostring(project,encoding='utf-8',xml_declaration=False))
  z.writestr('AutomaticPortfolioBuilder-Task1.xml',ET.tostring(task,encoding='utf-8',xml_declaration=False))
 inp=OUT/'input';inp.mkdir(exist_ok=True)
 for source,name in ((CAT,'CAT_0168_CAPABILITY_INPUT.sqx'),(CONTROL,'MSFT_OLD_CONTROL_NOT_CANDIDATE.sqx')):shutil.copy2(source,inp/name)
 receipt={'schema_version':1,'classification':'DISPOSABLE_CAPABILITY_SMOKE_NOT_RESEARCH',
  'project_name':NAME,'input_count':2,'inputs':{str(CAT):sha(CAT),str(CONTROL):sha(CONTROL)},
  'warning':'The MSFT control is an old rejected/unqualified SQ strategy. No portfolio result from this smoke is evidence.',
  'settings':values,'initial_capital':1000,'cfx_sha256':sha(target),'paper_authorized':False,'live_authorized':False}
 (OUT/'prepare_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
