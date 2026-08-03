import pandas as pd

from lab.sq_bridge.xau_h1_displacement_preflight import prepare, simulate


def _frame(rows):
    start=1_600_002_000//3600*3600
    f=pd.DataFrame([{"ts":start+i*3600,"open":o,"high":h,"low":l,"close":c,
                     "volume":1,"minute_count":60} for i,(o,h,l,c) in enumerate(rows)])
    f.index=pd.to_datetime(f.ts,unit="s",utc=True); return f


def test_continuation_enters_next_open_and_time_exits():
    bars=[(100,101,99,100)]*5+[(100,110,100,109),(109,111,108,110),(110,112,109,111)]
    trades=simulate(prepare(_frame(bars),2),"continuation","long",1.0,2,10)
    assert len(trades)==1
    assert trades[0]["entry"]==109
    assert trades[0]["exit"]==111
    assert trades[0]["direction"]==1


def test_reversal_flips_event_direction_and_side_filter():
    bars=[(100,101,99,100)]*5+[(100,110,100,109),(109,110,107,108)]
    prepared=prepare(_frame(bars),2)
    assert simulate(prepared,"reversal","long",1.0,1,10)==[]
    trades=simulate(prepared,"reversal","short",1.0,1,10)
    assert trades and trades[0]["direction"]==-1
