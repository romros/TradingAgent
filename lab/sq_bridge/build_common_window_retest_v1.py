#!/usr/bin/env python3
"""Normalize a proven Retest CFX to the common 2022-2024 portfolio window."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from alquimia_retest import _write_reproducible_cfx,verify_retest_project
from sqx_extract import extract
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(source,candidate,output,name,candidate_id):
 with zipfile.ZipFile(source) as z:
  task_file=next(x for x in z.namelist() if x.startswith('Retest') and x.endswith('.xml'));config=ET.fromstring(z.read('config.xml'));task=ET.fromstring(z.read(task_file))
 config.set('name',name);ref=config.find('./Tasks/Task');ref.set('name','common 2022-2024 retest');ref.set('taskXMLFile','Retest-Task1.xml')
 banks=config.find('./Databanks');banks.clear();ET.SubElement(banks,'Databank',{'name':'Results','view':'Default - Main data','syncType':'Auto-sync never','position':'0'});ET.SubElement(banks,'Databank',{'name':'PreHoldout','view':'Default - Main data','syncType':'Auto-sync never','position':'1'})
 setup=task.find('./Data/Setups/Setup');setup.set('dateFrom','2022.01.01');setup.set('dateTo','2024.12.31');setup.set('testPrecision','4');setup.set('slippage','0');chart=setup.find('Chart');symbol=chart.get('symbol');timeframe=chart.get('timeframe');chart.set('spread','0')
 task.find("./Databanks/Databank[@name='Output']").set('value','PreHoldout');task.find("./Databanks/Databank[@name='Input']").set('value','Results');task.find('./Databanks').set('retestSelected','false');task.find('./Rankings/DeleteFailedStrategies').text='false';task.find('./Rankings/Conditions').clear();task.find('./CrossChecks').set('use','false')
 members={'config.xml':ET.tostring(config,encoding='utf-8',xml_declaration=True),'Retest-Task1.xml':ET.tostring(task,encoding='utf-8',xml_declaration=True)};output.parent.mkdir(parents=True,exist_ok=True);_write_reproducible_cfx(output,members);contract=extract(candidate)
 manifest={'schema_version':2,'project_name':name,'stage':'pre_holdout','input_databank':'Results','output_databank':'PreHoldout','date_from':'2022-01-01','date_to':'2024-12-31','symbol':symbol,'timeframe':timeframe,'source_task_file':task_file,'money_management':'FixedSize','fixed_size':1.0,'source_cfx_sha256':sha(source),'setup_slippage':0,'test_precision':4,'keep_failed':True,'performance_filters_applied_in_sq':False,'all_input_strategies_selected':True,'holdout_accessed':False,'holdout_locked':True,'build_reproducible':True,'source_role':'xml_format_scaffold_only','candidate_id':candidate_id,'candidate_sqx_path':str(candidate.resolve()),'candidate_sqx_sha256':sha(candidate),'candidate_strategy_xml_sha256':contract['strategy_xml_sha256'],'candidate_translation_status':contract['translation_status'],'cfx_sha256':sha(output)};mp=output.with_suffix('.manifest.json');mp.write_text(json.dumps(manifest,indent=2)+'\n');verify_retest_project(output,manifest);return manifest
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--name',required=True);p.add_argument('--candidate-id',required=True);a=p.parse_args();print(json.dumps(build(a.source,a.candidate,a.output,a.name,a.candidate_id),indent=2))
if __name__=='__main__':main()
