import json
import pytest
from lab.sq_bridge.nflx_04681_daily_mtm_v1 import dd,sha,S,L

def test_drawdown_tracks_peak_and_trough():
    value,episode=dd([{'date':'a','equity':100},{'date':'b','equity':120},{'date':'c','equity':90}])
    assert value == pytest.approx(25)
    assert episode['peak_date']=='b' and episode['trough_date']=='c'

def test_lock_is_intact():
    assert sha(S)==json.loads(L.read_text())['preregistration_sha256']
