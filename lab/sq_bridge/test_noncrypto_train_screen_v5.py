import numpy as np
import pandas as pd

from lab.sq_bridge.noncrypto_train_screen_v5 import backtest


def frame(count=25):
    index = pd.date_range("2020-01-01", periods=count, freq="D", tz="UTC")
    return pd.DataFrame({"open":100.0,"high":100.2,"low":99.8,"close":100.0}, index=index)


def test_time_exit_does_not_inspect_exit_bar_intrabar():
    f=frame(); a=pd.Series(1.0,index=f.index); s=pd.Series(0,index=f.index)
    s.iloc[15]=1
    # Entry is bar 16, bars 16 and 17 are held, exit is bar 18 open.  A low on
    # bar 18 must not be treated as a stop hit because we already exited.
    f.iloc[18,f.columns.get_loc("low")]=90
    exit_semantics={"stop":{"kind":"ATR","multiple":1.0},
                    "target":{"kind":"R","multiple":2.0},"max_bars":2,
                    "manager":{"kind":"NONE"}}
    result=backtest(f,a,s,exit_semantics,"test",{},cost=0)
    assert result["trades"]==1
    assert result["net_return"]==0


def test_stop_first_when_stop_and_target_collide():
    f=frame(); a=pd.Series(1.0,index=f.index); s=pd.Series(0,index=f.index); s.iloc[15]=1
    f.iloc[16,f.columns.get_loc("low")]=98
    f.iloc[16,f.columns.get_loc("high")]=103
    exit_semantics={"stop":{"kind":"ATR","multiple":1.0},
                    "target":{"kind":"R","multiple":2.0},"max_bars":2,
                    "manager":{"kind":"NONE"}}
    result=backtest(f,a,s,exit_semantics,"test",{},cost=0)
    assert result["net_return"]<0
