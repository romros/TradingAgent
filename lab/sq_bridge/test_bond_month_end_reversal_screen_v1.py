import datetime as dt
from bond_month_end_reversal_screen_v1 import trades
def test_negative_pressure_creates_long_reversal_trade():
 days=[dt.date(2024,1,d) for d in range(10,23) if dt.date(2024,1,d).weekday()<5][:9]
 frame={d:(100.,100.) for d in days};frame[days[-9]]=(100,100);frame[days[-5]]=(99,99);frame[days[-4]]=(99,99);frame[days[-2]]=(101,101)
 result=trades(frame);assert len(result)==1;assert result[0][2]==101/99-1
