import datetime as dt
from lab.sq_bridge.gold_etc_sma200_screen_v1 import rows
def test_signal_executes_next_month_open():
 f={};d=dt.date(2020,1,1)
 for i in range(450):
  day=d+dt.timedelta(days=i)
  if day.weekday()<5:f[day]=(100+i,100+i)
 z=rows(f,0);assert z and z[0][3]==1 and z[0][0].day<=3
