from pathlib import Path
from sgln_tsmom12_sq_parity_v1 import run
ROOT=Path(__file__).resolve().parents[2]
def test_real_native_retest_matches_python_exactly():
 r=run(ROOT/'data/ibkr_sq_v2/preflight/SGLN_L_ADJUSTED_D1_through_2024.csv',Path('/mnt/volume-SQ/user/projects/IBKR_SGLN_TSMOM12_PREHOLDOUT_V1/orders-pre-holdout-f957a3e8812794d4.csv'))
 assert r['decision']=='PASS_EXACT_SIGNAL_AND_TRADE_PARITY'
 assert r['python_trades']==r['sq_trades']==3
