#!/usr/bin/env python3
"""Prepare a four-component common-window SQ Portfolio Master audit."""
from __future__ import annotations
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(template,output,inputs):
 output.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(template) as z:members={n:z.read(n) for n in z.namelist()}
 name='IBKR_FOUR_EDGE_PORTFOLIO_MASTER_2022_2024_V2';config=ET.fromstring(members['config.xml']);config.set('name',name)
 for databank in config.findall('./Databanks/Databank'):
  if databank.get('name')=='Simple strategies':databank.set('name','Input')
 task=ET.fromstring(members['AutomaticPortfolioBuilder-Task1.xml']);s=task.find('AutomaticPortfolioBuilder')
 values={'SearchType':'bruteforce','MinStrategies':'4','MaxStrategies':'4','MaxStrategiesDatabank':'4','DateRange':'full','FitnessType':'ReturnDD','CorrMax':'1.0','CorrAllowNegative':'true','FilterOverlappingTrades':'false','MMMethodOptional':'false'}
 for key,value in values.items():s.find(key).text=value
 for condition in s.findall('./Conditions/Condition'):condition.set('use','false')
 task.find("./Databanks/Databank[@label='Input databank']").set('value','Input')
 s.find('./MoneyManagement/InitialCapital').text='2000'
 target=output/'project.cfx'
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('config.xml',ET.tostring(config,encoding='utf-8'));z.writestr('AutomaticPortfolioBuilder-Task1.xml',ET.tostring(task,encoding='utf-8'))
 dest=output/'input';dest.mkdir(exist_ok=True);copied={}
 for source in inputs:
  target_file=dest/source.name
  if source.resolve()!=target_file.resolve():shutil.copy2(source,target_file)
  copied[str(source)]=sha(source)
 receipt={'schema_version':1,'classification':'COMMON_WINDOW_SQ_PORTFOLIO_AUDIT','project_name':name,'period':'2022-01-01/2024-12-31','input_count':4,'inputs':copied,'settings':values,'initial_capital':2000,'money_management_warning':'Portfolio Master StocksSizeByPrice is not yet proven equal to four fixed 25% compartments; aggregate is SQ-native diagnostic, not small-account parity.','cfx_sha256':sha(target),'paper_authorized':False,'live_authorized':False};(output/'prepare_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
def main():
 p=argparse.ArgumentParser();p.add_argument('--template',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--input',type=Path,action='append',required=True);a=p.parse_args();print(json.dumps(prepare(a.template,a.output,a.input),indent=2))
if __name__=='__main__':main()
