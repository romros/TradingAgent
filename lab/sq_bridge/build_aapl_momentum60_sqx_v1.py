#!/usr/bin/env python3
"""Build the frozen AAPL month-end 60-session momentum SQX."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def item(key,**attrs): return ET.Element('Item',{'key':key,**attrs})
def param(parent,key,value,**attrs): ET.SubElement(parent,'Param',{'key':key,**attrs}).text=str(value)
def block(parent,key,child): b=ET.SubElement(parent,'Block',{'key':key});b.append(child)
def series(key,shift):
 x=item(key,returnType='price' if key=='Close' else 'number');param(x,'#Chart#',0);param(x,'#Shift#',shift);return x
def compare(key,left,right): x=item(key,returnType='boolean');block(x,'#Left#',left);block(x,'#Right#',right);return x
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(template:Path,output:Path,strategy_name:str='AAPL_MOMENTUM60_MONTH_END_V1')->dict:
 with zipfile.ZipFile(template) as z:members={n:z.read(n) for n in z.namelist()}
 root=ET.fromstring(members['strategy_Portfolio.xml']);strategy=root.find('.//Strategy');strategy.set('name',strategy_name)
 signal=root.find(".//Rule[@type='Signal']/signals/signal[@variable='33333333-1111-1111-3333-333333333333']");signal.clear();signal.set('variable','33333333-1111-1111-3333-333333333333')
 gate=item('AND',returnType='boolean')
 for condition in (compare('IsLower',series('BarDayOfMonth',0),series('BarDayOfMonth',1)),compare('IsGreater',series('Close',1),series('Close',61))): b=ET.SubElement(gate,'Block');b.append(condition)
 signal.append(gate);action=root.find(".//Rule[@name='Long entry']/Then/Item")
 action.find("./Param[@key='#ExitAfterBars.ExitAfterBars#']").text='20'
 for key in ('#StopLoss.StopLoss#','#ProfitTarget.ProfitTarget#'):
  p=action.find(f"./Param[@key='{key}']");p.clear();p.set('key',key);p.set('isFormula','true');ET.SubElement(p,'Formula',{'key':'SQ.Formulas.SLPT.None'})
 members['strategy_Portfolio.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
 settings=ET.fromstring(members['settings.xml']);name=settings.find('.//StrategyName')
 if name is not None:name.text=strategy_name
 settings.set('ResultName',strategy_name);members['settings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
 retained={k:v for k,v in members.items() if not k.startswith('Results/') and k not in {'orders.bin','lastSettings.xml'}};output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in retained.items():
   info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 result={'schema_version':1,'strategy':strategy_name,'rule':'DayOfMonth[0] < DayOfMonth[1] AND Close[1] > Close[61]; enter market; exit after 20 bars','template_sha256':sha(template),'output_sha256':sha(output),'performance_accessed':False,'paper_authorized':False,'live_authorized':False};output.with_suffix('.receipt.json').write_text(json.dumps(result,indent=2)+'\n');return result
def main():
 a=argparse.ArgumentParser();a.add_argument('--template',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--strategy-name',default='AAPL_MOMENTUM60_MONTH_END_V1');z=a.parse_args();print(json.dumps(build(z.template,z.output,z.strategy_name),indent=2))
if __name__=='__main__':main()
