import pandas as pd

from lab.sq_bridge.gbpusd_m15_v1 import SPLITS, segment


def test_segments_do_not_touch_sealed_holdout():
    frame = pd.DataFrame({"date": pd.to_datetime(["2023-12-31", "2024-01-01"], utc=True)})
    assert len(segment(frame, "oos")) == 1
    assert max(end for _, end in SPLITS.values()) == "2023-12-31"
