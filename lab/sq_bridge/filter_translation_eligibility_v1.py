#!/usr/bin/env python3
"""Filter a frozen SQ selection only by deterministic implementation support."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from lab.sq_bridge.sqx_extract import extract

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selection',type=Path,required=True);p.add_argument('--sqx-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=json.loads(a.selection.read_text());eligible=[];rejected=[]
 for row in source['representatives']:
  contract=extract(a.sqx_root/(row['candidate_id']+'.sqx'))
  target=eligible if contract['translation_status']=='SUPPORTED_SUBSET' else rejected
  target.append({**row,'translation_status':contract['translation_status'],'unsupported_nodes_or_formulas':contract['unsupported_nodes_or_formulas']})
 result={**source,'stage':'train_structural_selection_translation_eligible','selection_uses_validation':False,'selection_uses_oos':False,'representatives':eligible,'translation_rejected':rejected}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'eligible':[x['candidate_id'] for x in eligible],'rejected':[x['candidate_id'] for x in rejected]},indent=2))
if __name__=='__main__':main()
