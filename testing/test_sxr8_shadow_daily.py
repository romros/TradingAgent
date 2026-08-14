import datetime as dt,importlib.util,json
from pathlib import Path
P=Path(__file__).parents[1]/'apps/sxr8_shadow_daily.py';S=importlib.util.spec_from_file_location('daily',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
def test_non_action_day_needs_no_price_provider(tmp_path):
 p=tmp_path/'c.json';p.write_text(json.dumps({'actions':[{'date':'2026-08-31'}]}));assert not M.scheduled(p,dt.date(2026,8,14))
def test_action_day_detected(tmp_path):
 p=tmp_path/'c.json';p.write_text(json.dumps({'actions':[{'date':'2026-08-31'}]}));assert M.scheduled(p,dt.date(2026,8,31))
