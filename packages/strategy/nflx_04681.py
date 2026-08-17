"""Frozen NFLX 0.4681 D1 stop-entry mechanics for forward shadow use."""
from __future__ import annotations

def atr(rows:list[dict],period:int)->list[float]:
 out=[]
 for i,row in enumerate(rows):
  h,l=float(row['high']),float(row['low'])
  tr=h-l if i==0 else max(h-l,abs(h-float(rows[i-1]['close'])),abs(l-float(rows[i-1]['close'])))
  out.append(tr if i==0 else ((min(i+1,period)-1)*out[-1]+tr)/min(i+1,period))
 return out

def new_pending(rows:list[dict],index:int)->dict|None:
 if index<104 or not float(rows[index-3]['low'])<float(rows[index-1]['high']):return None
 a104=atr(rows[:index+1],104);a15=atr(rows[:index+1],15)
 price=round(max(float(x['high']) for x in rows[index-10:index])+.30*a104[index-3],3)
 return {'price':price,'atr15':a15[index-1],'created_session':rows[index]['date'],'bars_valid':80,'age':0}

def pending_for_next(rows:list[dict])->dict|None:
 i=len(rows)
 if i<104 or not float(rows[i-3]['low'])<float(rows[i-1]['high']):return None
 a104=atr(rows,104);a15=atr(rows,15)
 return {'price':round(max(float(x['high']) for x in rows[i-10:i])+.30*a104[i-3],3),
         'atr15':a15[i-1],'created_session':rows[-1]['date'],'bars_valid':80,'age':0}

def bracket(base:float,distance:float)->tuple[float,float]:
 d=round(distance,6);return round(base-2.5*d,3),round(base+2.8*d,3)

def exit_on_bar(row:dict,stop:float,target:float)->tuple[str,float,bool]|None:
 o,h,l=(float(row[k]) for k in ('open','high','low'))
 if o<=stop:return 'SL_GAP',o,True
 if o>=target:return 'PT_GAP',o,True
 if l<=stop:return 'SL',stop,False
 if h>=target:return 'PT',target,False
 return None
