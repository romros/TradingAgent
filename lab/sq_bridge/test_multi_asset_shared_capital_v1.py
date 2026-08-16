from lab.sq_bridge.multi_asset_shared_capital_v1 import run

def test_shared_capital_never_buys_unaffordable_whole_share():
    rows=[]
    for index in range(205):
        close=1000-index if index<3 else 1000+index
        rows.append({'date':f'2024-{index//28+1:02d}-{index%28+1:02d}',
                     'open':close,'high':close,'low':close,'close':close})
    # The synthetic calendar is intentionally not used for a signal assertion;
    # this checks the zero-trade/cash-preservation invariant at small capital.
    result=run({'EXPENSIVE':rows},100,'2024-01-01','2024-12-31',{
        'allocation':{'maximum_concurrent_positions':3},
        'costs':{'commission_usd_per_order':1,'slippage_bps_per_side':10}})
    assert result['trades']==0
    assert result['return_pct']==0
