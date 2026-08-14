import datetime as dt
from gold_weekend_effect_screen_v1 import returns, metrics

def test_requires_literal_friday_to_monday():
    rows=[{"date":dt.date(2024,1,5),"open":100,"close":101},
          {"date":dt.date(2024,1,8),"open":102,"close":103}]
    assert returns(rows,"FRIDAY_CLOSE_TO_MONDAY_OPEN")==[(dt.date(2024,1,8),102/101-1)]

def test_holiday_monday_is_skipped():
    rows=[{"date":dt.date(2024,1,12),"open":100,"close":101},
          {"date":dt.date(2024,1,16),"open":102,"close":103}]
    assert returns(rows,"FRIDAY_CLOSE_TO_MONDAY_OPEN")==[]

def test_cost_reduces_each_trade():
    rows=[(dt.date(2024,1,8),.01),(dt.date(2024,1,15),-.002)]
    assert metrics(rows,70)["mean_return"] < metrics(rows,0)["mean_return"]
