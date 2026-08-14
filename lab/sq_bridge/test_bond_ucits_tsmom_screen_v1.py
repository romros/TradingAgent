import datetime as dt
from bond_ucits_tsmom_screen_v1 import metrics,corr
def test_metrics_compound():
 rows=[(dt.date(2024,1,1),dt.date(2024,2,1),.1,1,1),(dt.date(2024,2,1),dt.date(2024,3,1),-.1,1,0)]
 assert metrics(rows)['total_return']==pytest.approx(-.01)
def test_correlation():
 a=[(dt.date(2024,1,1),None,.1,1,0),(dt.date(2024,2,1),None,-.1,1,0)]
 assert corr(a,a)['correlation']==pytest.approx(1)
import pytest
