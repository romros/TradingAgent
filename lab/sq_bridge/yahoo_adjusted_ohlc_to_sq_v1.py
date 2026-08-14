#!/usr/bin/env python3
import argparse,csv,datetime as dt
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
rows=[]
with a.input.open() as f:
 r=csv.reader(f)
 for x in r:
  try:d=dt.date.fromisoformat(x[0])
  except (ValueError,IndexError):continue
  if d.year>=2025:raise ValueError('sealed row')
  adj,close,high,low,open_,vol=map(float,x[1:7]);factor=adj/close
  rows.append([d.strftime('%Y.%m.%d'),'00:00',open_*factor,high*factor,low*factor,adj,vol])
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('w',newline='') as f:csv.writer(f,lineterminator='\n').writerows(rows)
print({'rows':len(rows),'first':rows[0][0],'last':rows[-1][0]})
