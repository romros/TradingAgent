import datetime as dt
from packages.strategy.turn_of_month import action_for,build_schedule
def test_schedule_uses_exchange_sessions_not_weekdays():
 s=[dt.date(2024,1,30),dt.date(2024,1,31),dt.date(2024,2,1),dt.date(2024,2,2),dt.date(2024,2,5),dt.date(2024,2,6)]
 a=build_schedule(s);assert [(x.session,x.action) for x in a]==[(dt.date(2024,1,31),'BUY'),(dt.date(2024,2,6),'SELL')]
def test_idempotency_suppresses_completed_action():
 s=[dt.date(2024,1,31),dt.date(2024,2,1),dt.date(2024,2,2),dt.date(2024,2,5),dt.date(2024,2,6)]
 assert action_for(dt.date(2024,1,31),s,{'turn_of_month:2024-01:BUY'})==[]
def test_gap_between_calendar_months_is_rejected():
 s=[dt.date(2024,1,31),dt.date(2024,3,1),dt.date(2024,3,4),dt.date(2024,3,5),dt.date(2024,3,6)];assert build_schedule(s)==[]
