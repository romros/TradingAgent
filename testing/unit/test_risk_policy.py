import math

import pytest

from packages.portfolio.risk_policy import parse_risk_glidepath, risk_pct_for_capital


def test_glidepath_reduces_risk_at_boundaries():
    tiers = parse_risk_glidepath("400:.015,1000:.0125,2500:.01,5000:.0075,inf:.005")
    assert risk_pct_for_capital(200, tiers, .01) == .015
    assert risk_pct_for_capital(399.99, tiers, .01) == .015
    assert risk_pct_for_capital(400, tiers, .01) == .0125
    assert risk_pct_for_capital(1000, tiers, .01) == .01
    assert risk_pct_for_capital(5000, tiers, .01) == .005
    assert math.isinf(tiers[-1].capital_below)


@pytest.mark.parametrize("raw", [
    "400:.01,1000:.02,inf:.005",
    "1000:.01,400:.005,inf:.002",
    "400:.01,1000:.005",
    "400:.10,inf:.01",
])
def test_invalid_glidepaths_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_risk_glidepath(raw)
