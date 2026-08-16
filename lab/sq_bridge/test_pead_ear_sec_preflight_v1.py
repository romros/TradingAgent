from datetime import date

from lab.sq_bridge.pead_ear_sec_preflight_v1 import first_session_after_acceptance


def test_old_filing_cannot_map_to_first_available_session():
    sessions = [date(2017, 1, 3), date(2017, 1, 4)]
    assert first_session_after_acceptance(date(2016, 12, 1), sessions) is None
