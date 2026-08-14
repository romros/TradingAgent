"""Deterministic turn-of-month schedule; independent from prices and broker."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass

@dataclass(frozen=True)
class CalendarAction:
    session: dt.date
    action: str
    cycle: str
    reason: str

def build_schedule(sessions: list[dt.date]) -> list[CalendarAction]:
    ordered=sorted(set(sessions));months={}
    for day in ordered:months.setdefault((day.year,day.month),[]).append(day)
    keys=sorted(months);actions=[]
    for i in range(len(keys)-1):
        current,following=keys[i],keys[i+1]
        if following[0]*12+following[1] != current[0]*12+current[1]+1 or len(months[following])<4:
            continue
        cycle=f"{current[0]:04d}-{current[1]:02d}"
        actions.append(CalendarAction(months[current][-1],"BUY",cycle,"last_session_of_month"))
        actions.append(CalendarAction(months[following][3],"SELL",cycle,"fourth_session_of_next_month"))
    return sorted(actions,key=lambda x:(x.session,0 if x.action=='SELL' else 1,x.cycle))

def action_for(session: dt.date, sessions: list[dt.date], completed_keys: set[str]|None=None):
    completed_keys=completed_keys or set();found=[]
    for action in build_schedule(sessions):
        key=f"turn_of_month:{action.cycle}:{action.action}"
        if action.session==session and key not in completed_keys:found.append((key,action))
    return found

