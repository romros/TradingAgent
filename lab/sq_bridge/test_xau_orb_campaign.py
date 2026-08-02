import pandas as pd

from pathlib import Path
import pytest

from xau_orb_campaign import run, trades
from tsmom_duka_campaign import campaign


def test_orb_enters_next_bar_and_uses_stop_first_on_ambiguous_bar():
    index = pd.to_datetime([
        "2024-01-02 08:20", "2024-01-02 08:25", "2024-01-02 08:30",
        "2024-01-02 08:35", "2024-01-02 08:40", "2024-01-02 15:45",
    ])
    frame = pd.DataFrame({
        "open": [100, 100, 100, 101, 101, 100],
        "high": [101, 101, 101.2, 102.2, 104, 101],
        "low": [99, 99.5, 100, 100.5, 98, 99],
        "close": [100, 100.5, 101.2, 102, 100, 100],
    }, index=index)
    result = trades(frame, 15)
    assert len(result) == 1
    assert result[0]["entry"] == 101
    assert result[0]["reason"] == "stop"


def test_holdout_requires_exactly_one_frozen_finalist():
    with pytest.raises(ValueError, match="HOLDOUT_REQUIRES_FROZEN_FINALIST"):
        run(Path("/missing"), {"splits": {}}, unseal=True)
    with pytest.raises(ValueError, match="HOLDOUT_REQUIRES_FROZEN_FINALIST"):
        campaign(Path("/missing"), {}, unseal=True)
