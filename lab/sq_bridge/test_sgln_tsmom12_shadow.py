from packages.strategy.sgln_tsmom12 import desired_long

def test_exact_calendar_month_signal():
 rows=[]
 for year in (2023,2024):
  for month in range(1,13):rows.append({'date':f'{year}-{month:02d}-28','close':100+year-2023+month})
 rows.append({'date':'2025-01-02','close':130})
 assert desired_long(rows,24) is True
 rows[23]['close']=50
 assert desired_long(rows,24) is False

def test_only_first_session_of_month_returns_decision():
 rows=[{'date':'2023-01-31','close':100},{'date':'2024-01-31','close':110},{'date':'2024-02-01','close':111},{'date':'2024-02-02','close':112}]
 assert desired_long(rows,3) is None
