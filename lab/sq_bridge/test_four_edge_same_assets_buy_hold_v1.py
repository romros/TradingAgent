from pathlib import Path
from four_edge_same_assets_buy_hold_v1 import run

ROOT=Path(__file__).resolve().parents[2]
def test_frozen_same_asset_benchmarks():
 p=ROOT/'data/ibkr_sq_v2'
 result=run({
  'cat':p/'portfolio_benchmark_v1/CAT_ADJUSTED_2022_2024.csv',
  'msft':p/'portfolio_benchmark_v1/MSFT_ADJUSTED_2022_2024.csv',
  'jpm':p/'portfolio_benchmark_v1/JPM_ADJUSTED_2022_2024.csv',
  'sgln':p/'preflight/SGLN_L_ADJUSTED_D1_through_2024.csv'},
  p/'four_edge_portfolio_composer_v1/ecb_gbpusd_2021_2024.csv')
 assert result['decision']=='PASS_UNLEVERED_AND_RISK_FAIL_MAX_RETURN_MATCHED_EXPOSURE'
 assert result['same_assets_buy_hold_unlevered']['return_pct']==44.361374
 assert result['same_assets_buy_hold_exposure_matched']['return_pct']==80.76557
 assert result['comparison_unlevered']['return_pass']
 assert result['comparison_unlevered']['drawdown_pass']
 assert not result['comparison_exposure_matched']['return_pass']
 assert result['comparison_exposure_matched']['drawdown_pass']
