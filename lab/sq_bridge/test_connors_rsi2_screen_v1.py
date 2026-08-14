import datetime as dt,importlib.util,math
from pathlib import Path
P=Path(__file__).with_name('connors_rsi2_screen_v1.py');S=importlib.util.spec_from_file_location('r',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_rsi_decline_is_oversold():
 r=M.rsi_wilder([10,9,8,7]);assert r[-1]==0
def test_period_does_not_leak_exit():
 x={'entry':dt.date(2023,12,29),'exit':dt.date(2024,1,2),'return':.1};assert M.in_period([x],dt.date(2024,1,1),dt.date(2024,12,31))==[]
def test_metrics():
 m=M.metrics([{'return':.1},{'return':-.05}]);assert m['trades']==2 and math.isclose(m['profit_factor'],2)
