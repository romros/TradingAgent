from types import SimpleNamespace
from lab.sq_bridge.three_edge_vs_weighted_buy_hold_v1 import dd

def test_drawdown():
 from datetime import date
 value,pair=dd([(date(2022,1,1),100),(date(2022,1,2),120),(date(2022,1,3),90)])
 assert round(value,6)==25
 assert pair==(date(2022,1,2),date(2022,1,3))
