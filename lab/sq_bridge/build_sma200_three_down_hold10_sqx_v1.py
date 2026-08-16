#!/usr/bin/env python3
"""Build the native SQX expression of SMA200 + three down closes + hold 10."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NAME='MULTI_ASSET_SMA200_THREE_DOWN_HOLD10_V1'
def item(key,**attrs):return ET.Element('Item',{'key':key,**attrs})
def param(parent,key,value):ET.SubElement(parent,'Param',{'key':key}).text=str(value)
def block(parent,key,child):node=ET.SubElement(parent,'Block',{'key':key});node.append(child)
def close(shift):node=item('Close',returnType='price');param(node,'#Chart#',0);param(node,'#Shift#',shift);return node
def sma(period,shift):
 node=item('SMA',returnType='price');param(node,'#Chart#',0);param(node,'#ComputedFrom#',0);param(node,'#Period#',period);param(node,'#Shift#',shift);return node
def compare(key,left,right):node=item(key,returnType='boolean');block(node,'#Left#',left);block(node,'#Right#',right);return node
def conjunction(conditions):
 conditions=list(conditions);node=conditions[0]
 for condition in conditions[1:]:
  parent=item('AND',returnType='boolean');block(parent,'#Left#',node);block(parent,'#Right#',condition);node=parent
 return node
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(template:Path,output:Path):
 with zipfile.ZipFile(template) as archive:members={name:archive.read(name) for name in archive.namelist()}
 root=ET.fromstring(members['strategy_Portfolio.xml']);root.find('.//Strategy').set('name',NAME)
 signal=root.find(".//Rule[@type='Signal']/signals/signal[@variable='33333333-1111-1111-3333-333333333333']")
 signal.clear();signal.set('variable','33333333-1111-1111-3333-333333333333')
 signal.append(conjunction([compare('IsGreater',close(1),sma(200,1)),compare('IsLower',close(1),close(2)),compare('IsLower',close(2),close(3)),compare('IsLower',close(3),close(4))]))
 action=root.find(".//Rule[@name='Long entry']/Then/Item");action.find("./Param[@key='#ExitAfterBars.ExitAfterBars#']").text='10'
 for key in ('#StopLoss.StopLoss#','#ProfitTarget.ProfitTarget#'):
  node=action.find(f"./Param[@key='{key}']");node.clear();node.set('key',key);node.set('isFormula','true');ET.SubElement(node,'Formula',{'key':'SQ.Formulas.SLPT.None'})
 members['strategy_Portfolio.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
 settings=ET.fromstring(members['settings.xml']);strategy_name=settings.find('.//StrategyName')
 if strategy_name is not None:strategy_name.text=NAME
 settings.set('ResultName',NAME);members['settings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
 retained={name:data for name,data in members.items() if not name.startswith('Results/') and name not in {'orders.bin','lastSettings.xml'}};output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
  for name,data in retained.items():
   info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,data)
 receipt={'schema_version':1,'strategy':NAME,'rule':'Close[1]>SMA(200)[1] AND Close[1]<Close[2]<Close[3]<Close[4]; enter market; exit after 10 bars','template_sha256':sha(template),'output_sha256':sha(output),'performance_accessed':False,'paper_authorized':False,'live_authorized':False};output.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--template',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(json.dumps(build(args.template,args.output),indent=2))
if __name__=='__main__':main()
