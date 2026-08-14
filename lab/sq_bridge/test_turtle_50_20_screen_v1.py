import datetime as dt,importlib.util
from pathlib import Path
P=Path(__file__).with_name('turtle_50_20_screen_v1.py');S=importlib.util.spec_from_file_location('t',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_period_boundary():
 x={'entry':dt.date(2023,12,29),'exit':dt.date(2024,1,2),'return':1};assert not M.period([x],dt.date(2024,1,1),dt.date(2024,12,31))
def test_breakout_executes_next_open_and_exit_next_open():
 ds=[dt.date(2020,1,1)+dt.timedelta(days=i) for i in range(74)];z=[(d,float(i+1),float(i+1)) for i,d in enumerate(ds)];z[70]=(ds[70],71,40);z[71]=(ds[71],39,39);z[72]=(ds[72],38,38)
 ts=M.trades(z);assert ts and ts[0]['entry']==ds[51]
