from datetime import date

import pytest

from lab.sq_bridge.xauusd_cftc_release_ledger_v33 import exclusion_for


EXCLUSIONS = [{"start": "2023-01-31", "end": "2023-03-14", "reason": "ION", "source": "CFTC"}]


def test_exclusion_boundaries_are_inclusive():
    assert exclusion_for(date(2023, 1, 31), EXCLUSIONS)["reason"] == "ION"
    assert exclusion_for(date(2023, 3, 14), EXCLUSIONS)["reason"] == "ION"
    assert exclusion_for(date(2023, 3, 21), EXCLUSIONS) is None


def test_overlapping_exclusions_fail_closed():
    with pytest.raises(ValueError, match="overlapping"):
        exclusion_for(date(2023, 2, 7), EXCLUSIONS * 2)
