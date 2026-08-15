#!/usr/bin/env python3
"""Build USD per GBP from official ECB GBP/EUR and USD/EUR CSV series."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

def load(path:Path):
    with path.open(newline='') as stream:return {r['TIME_PERIOD']:float(r['OBS_VALUE']) for r in csv.DictReader(stream)}
def build(gbp:Path,usd:Path,output:Path):
    g,u=load(gbp),load(usd);days=sorted(set(g)&set(u));output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['date','usd_per_gbp'])
        writer.writerows((day,f'{u[day]/g[day]:.10f}') for day in days)
    return {'rows':len(days),'first':days[0],'last':days[-1],'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--gbp-eur',type=Path,required=True);p.add_argument('--usd-eur',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.gbp_eur,a.usd_eur,a.output),indent=2))
if __name__=='__main__':main()
