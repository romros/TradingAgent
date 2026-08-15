#!/usr/bin/env python3
"""Build an uncensored SGLN 2019-2024 Retest CFX from the proven JPM scaffold."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from sqx_extract import extract
from alquimia_retest import _write_reproducible_cfx, verify_retest_project

NAME="IBKR_SGLN_TSMOM12_PREHOLDOUT_V1"; SYMBOL="SGLN_GBP_ALQ_D1"; CANDIDATE="SGLN_TSMOM12_MONTHLY_NATIVE_V1"
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def build(source:Path,candidate:Path,output:Path)->dict:
    with zipfile.ZipFile(source) as archive:
        config=ET.fromstring(archive.read('config.xml')); task=ET.fromstring(archive.read('Retest-Task1.xml'))
    config.set('name',NAME); task_ref=config.find('./Tasks/Task'); task_ref.set('name','pre-holdout retest')
    banks=config.find('./Databanks'); banks.clear()
    ET.SubElement(banks,'Databank',{'name':'Results','view':'Default - Main data','syncType':'Auto-sync never','position':'0'})
    ET.SubElement(banks,'Databank',{'name':'PreHoldout','view':'Default - Main data','syncType':'Auto-sync never','position':'1'})
    setup=task.find('./Data/Setups/Setup'); setup.set('dateFrom','2019.01.01'); setup.set('dateTo','2024.12.31'); setup.set('testPrecision','4'); setup.set('slippage','0')
    chart=setup.find('Chart'); chart.set('symbol',SYMBOL); chart.set('timeframe','D1'); chart.set('spread','0')
    output_bank=task.find("./Databanks/Databank[@name='Output']"); output_bank.set('value','PreHoldout')
    symbols=task.find('./Resources/Symbols'); symbols.clear()
    symbol=ET.SubElement(symbols,'Symbol',{'name':SYMBOL,'source':'1','barType':'1','precision':'D1','timezone':'Etc/UTC','dateFrom':'1325548800000','dateTo':'1735603200000','uSymbol':'SGLN_GBP_ALQ','uSymbolName':'SGLN physical gold ETC adjusted GBP','removeWeekends':'false','broker':'-1'})
    ET.SubElement(symbol,'InstrumentInfo',{'instrument':'SGLN_GBP_ALQ','description':'SGLN physical gold ETC GBP signal research','tickSize':'0.0001','tickStep':'0.0001','minDistance':'0','tickValueInMoney':'0','dateFrom':'0','dateTo':'0','rows':'0','totalDays':'0','defaultSpread':'0.0','defaultSlippage':'0.0','decimals':'4','commissions':'<Method type="None" use="true"><Params /></Method>','pointValue':'1','dataType':'1','recognizedFromOrders':'false','exchange':'LSE','country':'GB','sector':'Commodities','swap':'<Swap use="false" type="money" long="0.0" short="0.0" tripleSwapOn="WEDNESDAY" rolloutHour="23:00" />','orderSizeMultiplier':'1','orderSizeStep':'1','broker':'-1'})
    members={'config.xml':ET.tostring(config,encoding='utf-8',xml_declaration=True),'Retest-Task1.xml':ET.tostring(task,encoding='utf-8',xml_declaration=True)}
    output.parent.mkdir(parents=True,exist_ok=True); _write_reproducible_cfx(output,members)
    contract=extract(candidate)
    manifest={'schema_version':2,'project_name':NAME,'stage':'pre_holdout','input_databank':'Results','output_databank':'PreHoldout','date_from':'2019-01-01','date_to':'2024-12-31','symbol':SYMBOL,'timeframe':'D1','source_task_file':'Retest-Task1.xml','money_management':'FixedSize','fixed_size':1.0,'source_cfx_sha256':sha(source),'setup_slippage':0,'test_precision':4,'keep_failed':True,'performance_filters_applied_in_sq':False,'all_input_strategies_selected':True,'holdout_accessed':False,'holdout_locked':True,'build_reproducible':True,'source_role':'xml_format_scaffold_only','candidate_id':CANDIDATE,'candidate_sqx_path':str(candidate.resolve()),'candidate_sqx_sha256':sha(candidate),'candidate_strategy_xml_sha256':contract['strategy_xml_sha256'],'candidate_translation_status':contract['translation_status'],'cfx_sha256':sha(output)}
    manifest_path=output.with_suffix('.manifest.json'); manifest_path.write_text(json.dumps(manifest,indent=2)+'\n'); verify_retest_project(output,manifest)
    return manifest
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.source,a.candidate,a.output),indent=2))
if __name__=='__main__':main()
