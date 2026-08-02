#!/usr/bin/env python3
"""Copia exactament els SQX aprovats per un gate a l'etapa seguent."""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

def stage(gate_path: Path, source: Path, destination: Path) -> dict:
    gate=json.loads(gate_path.read_text()); names=gate["survivors"]
    if len(names)!=len(set(names)) or len(names)!=gate["survivor_count"]: raise ValueError("Gate inconsistent")
    available={path.stem:path for path in source.glob("*.sqx")}; missing=sorted(set(names)-set(available))
    if missing: raise ValueError("SQX absents: "+", ".join(missing))
    destination.mkdir(parents=True,exist_ok=True)
    if list(destination.glob("*.sqx")): raise ValueError(f"Destinacio no buida: {destination}")
    for name in names: shutil.copy2(available[name],destination/f"{name}.sqx")
    copied=sorted(path.stem for path in destination.glob("*.sqx"))
    if copied!=sorted(names): raise ValueError("Verificacio post-copia fallida")
    return {"source_count":len(available),"selected_count":len(names),"copied":copied}

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate",type=Path,required=True); parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path,required=True); args=parser.parse_args()
    print(json.dumps(stage(args.gate,args.source,args.destination),indent=2))

if __name__=="__main__": main()
