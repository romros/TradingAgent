import datetime as dt
from lab.sq_bridge.gold_etc_tsmom_screen_v2 import monthly_rows,metrics
def test_monthly_signal_uses_twelve_prior_month_ends():
 f={}
 for i in range(15):
  y,m=2020+i//12,1+i%12;d=dt.date(y,m,28);f[d]=(100+i,100+i)
 rows=monthly_rows(f,0);assert rows and rows[0][3]==1 and rows[0][0]==dt.date(2021,2,28)
def test_cost_only_on_position_change():
 f={}
 for i in range(16):
  y,m=2020+i//12,1+i%12;d=dt.date(y,m,28);f[d]=(100+i,100+i)
 rows=monthly_rows(f,.01);assert rows[0][4]==1 and rows[1][4]==0
