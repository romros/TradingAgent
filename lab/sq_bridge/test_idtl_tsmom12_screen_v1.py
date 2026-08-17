from pathlib import Path
from lab.sq_bridge.idtl_tsmom12_screen_v1 import run

ROOT=Path(__file__).resolve().parents[2]
def test_idtl_duration_trend_is_rejected():
 r=run(ROOT/'data/ibkr_sq_v2/preflight/IDTL_L_ADJUSTED_D1_through_2024.csv')
 assert r['decision']=='REJECT_IDTL_TSMOM12'
 assert r['periods']['validation']['total_return']<0
 assert r['periods']['oos']['total_return']<0
 assert r['periods']['combined']['invested_months']==5
