import pytest
from lab.sq_bridge.nflx_04681_statistical_resilience_v1 import compounded, pct, pf, sha, SPEC, LOCK
import json

def test_metrics_are_deterministic():
    assert compounded([.1, -.05]) == pytest.approx(.045)
    assert pf([.1, -.05, .02]) == pytest.approx(2.4)
    assert pct([0, 10, 20], .5) == 10

def test_preregistration_lock_is_intact():
    assert sha(SPEC) == json.loads(LOCK.read_text())["preregistration_sha256"]
