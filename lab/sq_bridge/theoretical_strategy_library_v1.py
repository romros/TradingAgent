#!/usr/bin/env python3
"""Verify evidence lineage and publish the theoretical strategy library status."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=Path(__file__).with_suffix('.json')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build(spec_path=SPEC):
    spec=json.loads(Path(spec_path).read_text());rows=spec['strategies'];ids=[r['id'] for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError('duplicate strategy id')
    for row in rows:
        path=ROOT/row['evidence_path']
        if not path.is_file() or sha(path)!=row['evidence_sha256']: raise ValueError(f"evidence mismatch: {row['id']}")
        if 'portfolio_evidence_path' in row:
            p=ROOT/row['portfolio_evidence_path']
            if not p.is_file() or sha(p)!=row['portfolio_evidence_sha256']: raise ValueError(f"portfolio evidence mismatch: {row['id']}")
    admitted_statuses={'ADMITTED_RESEARCH_EDGE','ADMITTED_RESEARCH_EDGE_AND_INCREMENTAL_PORTFOLIO_COMPONENT','ADMITTED_CAPPED_PORTFOLIO_COMPONENT'}
    admitted=[r for r in rows if r['status'] in admitted_statuses];capped=[r for r in rows if r['status']=='ADMITTED_CAPPED_PORTFOLIO_COMPONENT'];conditional=[r for r in rows if r['status'].startswith('CONDITIONAL_EDGE')];research_only=[r for r in rows if r['status']=='ADMITTED_RESEARCH_EDGE_NOT_ADMITTED_TO_PORTFOLIO'];rejected=[r for r in rows if r['status'].startswith('REJECTED')];watch=[r for r in rows if r['status'].startswith('WATCHLIST')]
    eligible=admitted+conditional;distinct=len({r['mechanism'] for r in eligible})
    ready=len(eligible)>=spec['minimum_portfolio_strategies'] and distinct>=spec['minimum_portfolio_strategies']
    return {'schema_version':1,'decision':'PORTFOLIO_LIBRARY_READY' if ready else 'BUILDING_LIBRARY','admitted_strategy_ids':[r['id'] for r in admitted],'capped_portfolio_component_ids':[r['id'] for r in capped],'conditional_strategy_ids':[r['id'] for r in conditional],'research_only_strategy_ids':[r['id'] for r in research_only],'watchlist_strategy_ids':[r['id'] for r in watch],'rejected_strategy_ids':[r['id'] for r in rejected],'admitted_count':len(admitted),'conditional_count':len(conditional),'eligible_portfolio_count':len(eligible),'distinct_eligible_mechanisms':distinct,'minimum_required':spec['minimum_portfolio_strategies'],'portfolio_ready':ready,'evidence_verified':True,'paper_authorized':False,'live_authorized':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();r=build();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
