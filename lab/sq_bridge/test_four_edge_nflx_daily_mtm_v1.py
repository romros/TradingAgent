import csv
from lab.sq_bridge.four_edge_nflx_daily_mtm_v1 import nflx_curve

def test_cash_day_carries_latest_realized_equity(tmp_path):
 orders=tmp_path/'orders.csv';d1=tmp_path/'d1.csv'
 with orders.open('w',newline='') as f:
  w=csv.writer(f,delimiter=';');w.writerow(['Ticket','Symbol','Type','Open time','Open price','Size','Close time','Close price','Profit/Loss','Balance','Sample type','Close type','MAE ($)','MFE ($)','Time in trade','Comment']);w.writerow(['1','X','Buy','2022.01.03 00:00:00','100','1','2022.01.04 00:00:00','110','10','1010','IST','PT','0','10','1d','']);w.writerow(['2','X','Buy','2022.01.06 00:00:00','100','1','2022.01.07 00:00:00','100','0','1010','IST','Exit','0','0','1d',''])
 d1.write_text('\n'.join(f'2022.01.0{i},00:00,100,110,90,{100+i},1' for i in range(3,8))+'\n')
 curve=dict(nflx_curve(orders,d1));assert curve[next(d for d in curve if str(d)=='2022-01-05')]>1000
