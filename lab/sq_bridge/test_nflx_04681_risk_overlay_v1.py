import json
import pytest
from lab.sq_bridge.nflx_04681_risk_overlay_v1 import commission, sha, SPEC, LOCK

def test_ibkr_fixed_commission_floor():
    assert commission(1) == 1.0
    assert commission(1000) == 5.0

def test_risk_overlay_preregistration_is_locked():
    assert sha(SPEC) == json.loads(LOCK.read_text())["preregistration_sha256"]
