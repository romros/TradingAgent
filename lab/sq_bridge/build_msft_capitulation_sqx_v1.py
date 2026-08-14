#!/usr/bin/env python3
"""Build a native SQX expression of the frozen MSFT capitulation rule."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def item(key,**attrs):return ET.Element('Item',{'key':key,**attrs})
def param(parent,key,value,**attrs):ET.SubElement(parent,'Param',{'key':key,**attrs}).text=str(value)
def price(key,shift=1):
 x=item(key,returnType='price');param(x,'#Chart#',0);param(x,'#Shift#',shift);return x
def number(value):x=item('Number',returnType='number');param(x,'#Number#',value);return x
def block(parent,key,child):b=ET.SubElement(parent,'Block',{'key':key});b.append(child)
def lower(left,right):x=item('IsLower',returnType='boolean');block(x,'#Left#',left);block(x,'#Right#',right);return x
def multiply(left,right):x=item('Multiplication',returnType='pricenumber');block(x,'#Left#',left);block(x,'#Right#',right);return x
def bollinger():
 x=item('BollingerBands',returnType='price');param(x,'#Chart#',0);param(x,'#ComputedFrom#',0);param(x,'#Period#',20);param(x,'#Deviation#',2.0);param(x,'#Shift#',1);param(x,'#Line#',1);return x
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--template',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 with zipfile.ZipFile(a.template) as z:members={n:z.read(n) for n in z.namelist()}
 root=ET.fromstring(members['strategy_Portfolio.xml']);signal=root.find(".//Rule[@type='Signal']/signals/signal[@variable='33333333-1111-1111-3333-333333333333']")
 root.find('.//Strategy').set('name','MSFT_CAPITULATION_D1_NATIVE_V1')
 signal.clear();signal.set('variable','33333333-1111-1111-3333-333333333333');gate=item('AND')
 for condition in (lower(price('Close'),multiply(price('Open'),number(.98))),lower(price('Close'),bollinger())):
  b=ET.SubElement(gate,'Block');b.append(condition)
 signal.append(gate)
 long=root.find(".//Rule[@name='Long entry']");action=long.find('./Then/Item')
 action.find("./Param[@key='#ExitAfterBars.ExitAfterBars#']").text='1'
 for key in ('#StopLoss.StopLoss#','#ProfitTarget.ProfitTarget#'):
  p=action.find(f"./Param[@key='{key}']");p.clear();p.set('key',key);p.set('isFormula','true');ET.SubElement(p,'Formula',{'key':'SQ.Formulas.SLPT.None'})
 # The template supplies verified MSFT D1 settings; strip all old result payloads.
 members['strategy_Portfolio.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
 settings=ET.fromstring(members['settings.xml']);name=settings.find(".//StrategyName")
 if name is None:raise ValueError('template lacks StrategyName')
 name.text='MSFT_CAPITULATION_D1_NATIVE_V1';settings.set('ResultName','MSFT_CAPITULATION_D1_NATIVE_V1')
 members['settings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
 retained={k:v for k,v in members.items() if not k.startswith('Results/') and k not in {'orders.bin','lastSettings.xml'}}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in retained.items():z.writestr(name,data)
 receipt={'schema_version':1,'classification':'NATIVE_SQX_PARITY_REQUIRED','rule':'close[1] < open[1]*0.98 AND close[1] < BBLower(20,2)[1]; enter market; exit after 1 bar','template_sha256':sha(a.template),'output_sha256':sha(a.output),'performance_accessed':False,'paper_authorized':False,'live_authorized':False}
 a.output.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
