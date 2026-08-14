import datetime as dt,importlib.util
from pathlib import Path
P=Path(__file__).parents[1]/'lab/sq_bridge/ucits_gap_fade_screen_v1.py'
def functions():
 ns={'__file__':str(P)};exec(P.read_text().split("ap=argparse.ArgumentParser()")[0],ns);return ns
def test_gap_uses_prior_close_and_same_day_open_close():
 m=functions();a,b=dt.date(2024,1,2),dt.date(2024,1,3);f={a:(100,100),b:(98,99)};assert m['trades'](f,b,b,0)==[(b,99/98-1)]
def test_small_gap_is_ignored():
 m=functions();a,b=dt.date(2024,1,2),dt.date(2024,1,3);assert m['trades']({a:(1,100),b:(99.5,101)},b,b,0)==[]
