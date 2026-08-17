"""Frozen JPM Momentum60 month-boundary rule."""
from __future__ import annotations

def entry_on(rows,index:int)->bool:
 """Enter at rows[index] open when it is a new month and prior 60-bar momentum is positive."""
 if index<61 or rows[index]['date'][:7]==rows[index-1]['date'][:7]:return False
 return float(rows[index-1]['close'])>float(rows[index-61]['close'])

def exit_on(rows,index:int,entry_session:str,hold_bars:int=20)->bool:
 dates=[r['date'] for r in rows]
 try:entry=dates.index(entry_session)
 except ValueError:return False
 return index-entry>=hold_bars
