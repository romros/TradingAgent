from pathlib import Path
from lab.sq_bridge.five_edge_residual_margin_v1 import evaluate

ROOT=Path(__file__).resolve().parents[2];D=ROOT/'data/ibkr_sq_v2/four_edge_position_leverage_v1'
def test_frozen_residual_margin_policy_fails_drawdown_gate():
 r=evaluate(D/'Portfolio-1786963273774.sqx',ROOT/'data/ibkr_sq_v2/four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv',
  {k:D/f'orders-{k}-floor1000.csv' for k in ('cat','msft','jpm','sgln')},ROOT/'lab/sq_bridge/multi_asset_known_edge_funnel_v1.json')
 assert r['decision']=='FAIL_FIFTH_EDGE_RESIDUAL_MARGIN'
 assert r['cagr_pct']==17.700316
 assert r['daily_mtm_max_drawdown_pct']==21.009867
 assert r['candidate']['closed_trades']==130
 assert r['candidate']['skipped_margin']==0
