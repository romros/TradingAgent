#!/usr/bin/env python3
"""Converteix el Pareto descriptiu d'un inventari en un gate explícit d'etapa."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory",type=Path); parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--limit",type=int)
    args=parser.parse_args(); data=json.loads(args.inventory.read_text())
    survivors=data["pareto_candidates"]
    if args.limit is not None:
        if args.limit < 1: raise ValueError("limit ha de ser positiu")
        survivors=survivors[:args.limit]
    result={"schema_version":1,"gate":"IS_PARETO_STRUCTURAL_STAGING_ONLY",
            "source_inventory_sha256":data["source_inventory_sha256"],
            "survivor_count":len(survivors),"survivors":survivors,
            "warning":"Pareto IS is not validation and confers no promotion."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
