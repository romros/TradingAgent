from datetime import datetime, timezone

from lab.sq_bridge.ibkr_us_equity_data_preflight_v2 import NY


def test_nyse_rth_utc_hour_tracks_dst():
    winter = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc).astimezone(NY)
    summer = datetime(2024, 7, 2, 13, 30, tzinfo=timezone.utc).astimezone(NY)
    assert (winter.hour, winter.minute) == (9, 30)
    assert (summer.hour, summer.minute) == (9, 30)
