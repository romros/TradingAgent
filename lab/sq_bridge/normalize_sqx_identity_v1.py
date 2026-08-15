#!/usr/bin/env python3
"""Rename only SQX identity fields while stripping inherited results."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def normalize(source,output,name):
 with zipfile.ZipFile(source) as z:members={x:z.read(x) for x in z.namelist()}
 strategy=ET.fromstring(members['strategy_Portfolio.xml']);strategy.find('.//Strategy').set('name',name);members['strategy_Portfolio.xml']=ET.tostring(strategy,encoding='utf-8',xml_declaration=True)
 settings=ET.fromstring(members['settings.xml']);node=settings.find('.//StrategyName')
 if node is None:raise ValueError('StrategyName missing')
 node.text=name;settings.set('ResultName',name);members['settings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
 clean={k:v for k,v in members.items() if not k.startswith('Results/') and k not in {'orders.bin','lastSettings.xml'}};output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for key,value in clean.items():info=zipfile.ZipInfo(key,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,value)
 result={'schema_version':1,'identity':name,'source_sha256':sha(source),'output_sha256':sha(output),'logic_changed':False,'performance_accessed':False,'paper_authorized':False,'live_authorized':False};output.with_suffix('.receipt.json').write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--name',required=True);a=p.parse_args();print(json.dumps(normalize(a.source,a.output,a.name),indent=2))
if __name__=='__main__':main()
