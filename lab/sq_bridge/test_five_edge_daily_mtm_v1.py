from pathlib import Path
from lab.sq_bridge.five_edge_daily_mtm_v1 import evaluate

def test_frozen_synchronized_curve():
    result=evaluate(Path("lab/sq_bridge/five_edge_daily_mtm_v1.json"))
    assert result["daily_observations"] > 700
    assert round(result["net_return_pct"],4) == 19.3155
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
