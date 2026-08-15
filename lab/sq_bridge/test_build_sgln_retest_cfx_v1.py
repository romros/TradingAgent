from pathlib import Path
from build_sgln_retest_cfx_v1 import build
ROOT=Path(__file__).resolve().parents[2]
def test_build_verified_retest(tmp_path):
    result=build(ROOT/'data/ibkr_sq_v2/jpm_momentum60_v1/native_oos/project.cfx',ROOT/'data/ibkr_sq_v2/gold_tsmom_confirmation_v1/SGLN_TSMOM12_MONTHLY_NATIVE_V1.sqx',tmp_path/'p.cfx')
    assert result['stage']=='pre_holdout' and result['symbol']=='SGLN_GBP_ALQ_D1'
    assert result['candidate_translation_status']=='SUPPORTED_SUBSET'
