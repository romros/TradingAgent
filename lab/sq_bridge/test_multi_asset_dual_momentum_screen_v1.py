import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location("dual",HERE/"multi_asset_dual_momentum_screen_v1.py"); dual=importlib.util.module_from_spec(S); S.loader.exec_module(dual)

def test_lock_and_holdout():
    spec=dual.load_spec(); assert spec["single_variant"] and spec["holdout_2025"]=="SEALED_NOT_LOADED"

def test_gate_rejects_weak_profit_factor():
    gate={"minimum_months":24,"minimum_net_return":0,"minimum_profit_factor":1.1,"minimum_sharpe_improvement_vs_equal_weight":0,"positive_calendar_years_required":2,"maximum_drawdown":.2}
    value={"strategy":{"months":24,"net_return":.1,"profit_factor":1.05,"sharpe_improvement_vs_equal_weight":.2,"positive_calendar_years":2,"maximum_drawdown":.1}}
    assert not dual.passes(value,gate)
