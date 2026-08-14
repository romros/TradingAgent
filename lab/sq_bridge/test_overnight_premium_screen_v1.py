import datetime as dt, importlib.util, math
from pathlib import Path
P=Path(__file__).with_name('overnight_premium_screen_v1.py');S=importlib.util.spec_from_file_location('ov',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_returns_do_not_use_future_close():
 d1,d2=dt.date(2024,1,2),dt.date(2024,1,3);f={d1:(90,100),d2:(110,999)}
 got=M.returns(f,d2,d2,'overnight');assert got[0][0]==d2 and math.isclose(got[0][1],.1)
def test_intraday_same_session():
 d=dt.date(2024,1,3);p=dt.date(2024,1,2);f={p:(1,100),d:(110,121)}
 got=M.returns(f,d,d,'intraday');assert got[0][0]==d and math.isclose(got[0][1],.1)
def test_sealed_filename(tmp_path):
 p=tmp_path/'x2025.csv';p.write_text('')
 try:M.load(p)
 except ValueError:return
 assert False
