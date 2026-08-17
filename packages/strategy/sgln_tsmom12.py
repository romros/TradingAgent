"""Frozen exact-calendar-month SGLN twelve-month time-series momentum."""
from __future__ import annotations
def desired_long(rows,index:int)->bool|None:
 if index<1 or rows[index]['date'][:7]==rows[index-1]['date'][:7]:return None
 prior=rows[index-1];year,month=map(int,prior['date'][:7].split('-'));target=f'{year-1:04d}-{month:02d}';matches=[r for r in rows[:index] if r['date'].startswith(target)]
 if not matches:return None
 return float(prior['close'])>float(matches[-1]['close'])
