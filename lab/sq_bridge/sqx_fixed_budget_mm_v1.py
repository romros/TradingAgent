#!/usr/bin/env python3
"""Derive an SQX whose native stock MM spends at most a fixed cash budget."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def derive(source:Path,output:Path,budget:float):
    if budget<=0:raise ValueError('budget must be positive')
    with zipfile.ZipFile(source) as z:members={n:z.read(n) for n in z.namelist()}
    root=ET.fromstring(members['strategy_Portfolio.xml']);strategies=root.findall('.//Strategy')
    if len(strategies)!=1:raise ValueError('expected one strategy')
    old=strategies[0].find('./MoneyManagement')
    if old is None:raise ValueError('money management missing')
    mm_type='AlquimiaFixedBudgetFloor';new=ET.Element('MoneyManagement',{'type':mm_type});method=ET.SubElement(new,'Method');params=ET.SubElement(method,'Params')
    for key,value,dtype in [('MaxSize','1000000000','2')]:
        node=ET.SubElement(params,'Param',{'key':key,'dataType':dtype,'value':value,'className':mm_type,'engine':'*'});node.text=value
    ET.SubElement(new,'InitialCapital').text=f'{budget:g}'
    index=list(strategies[0]).index(old);strategies[0].remove(old);strategies[0].insert(index,new);members['strategy_Portfolio.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    if 'lastSettings.xml' in members:
        settings=ET.fromstring(members['lastSettings.xml']);mm=settings.find('.//RiskMoneyManagement/MoneyManagement')
        if mm is None:raise ValueError('lastSettings money management missing')
        for method_node in mm.findall('./Method'):method_node.set('use','false')
        custom=ET.SubElement(mm,'Method',{'type':mm_type,'use':'true'});custom_params=ET.SubElement(custom,'Params');param=ET.SubElement(custom_params,'Param',{'key':'MaxSize','className':mm_type});param.text='1000000000';mm.find('./InitialCapital').text=f'{budget:g}'
        members['lastSettings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
    if 'settings.xml' in members:
        settings=ET.fromstring(members['settings.xml'])
        for node in settings.findall(".//SettingsMap/MoneyManagement.InitialCapital"):node.text=f'{budget:g}'
        members['settings.xml']=ET.tostring(settings,encoding='utf-8',xml_declaration=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in members.items():z.writestr(name,data)
    return {'schema_version':1,'decision':'PASS_FIXED_BUDGET_MM_DERIVATION','source':str(source),'source_sha256':sha(source),'output':str(output),'output_sha256':sha(output),'budget':budget,'use_account_balance':False,'logic_changed':False,'paper_authorized':False,'live_authorized':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--budget',type=float,required=True);a=p.parse_args();print(json.dumps(derive(a.source,a.output,a.budget),indent=2))
if __name__=='__main__':main()
