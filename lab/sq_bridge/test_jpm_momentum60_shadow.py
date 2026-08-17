from packages.strategy.jpm_momentum60 import entry_on,exit_on

def rows(n=70):
 out=[]
 for i in range(n):
  month='01' if i<61 else '02';out.append({'date':f'2024-{month}-{i%28+1:02d}','close':100+i})
 return out

def test_entry_requires_month_change_and_positive_60_bar_momentum():
 r=rows();assert entry_on(r,61)
 r[60]['close']=1;assert not entry_on(r,61)

def test_exit_after_exactly_twenty_bars():
 r=[{'date':f'2024-01-{i+1:02d}'} for i in range(25)]
 assert not exit_on(r,19,r[0]['date'])
 assert exit_on(r,20,r[0]['date'])
