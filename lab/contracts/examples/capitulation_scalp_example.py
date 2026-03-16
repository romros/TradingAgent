"""
Exemple complet del contracte canònic per Capitulation Scalp 1H.
Dades reals extretes dels estudis T1/MC/WF.

Ús:
  python3 lab/contracts/examples/capitulation_scalp_example.py
"""
from __future__ import annotations

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from lab.contracts.models import (
    SetupSpec, SetupFamily, SetupStatus,
    SetupValidationResult, LiqRateByLeverage, YearlyBreakdown,
    OpportunityEstimate,
)


# ══════════════════════════════════════════════════════════════
# 1. SetupSpec — descripció del setup
# ══════════════════════════════════════════════════════════════

CAPITULATION_SCALP_SPEC = SetupSpec(
    name="capitulation_scalp_1h",
    version="1.0",
    family=SetupFamily.CAPITULATION,
    thesis=(
        "Rebot de capitulació: quan una candle 1H cau >3%, trenca BB lower "
        "i acumula >5% de caiguda en 3H, el preu rebota a la candle següent "
        "amb WR ~59% i EV positiu. L'edge prové del pànic de venedors (capitulació) "
        "seguit d'absorció de smart money."
    ),
    direction="LONG",
    assets=("ETHUSDT", "BTCUSDT", "SOLUSDT"),
    tf_context="4h",
    tf_execution="1h",
    entry_conditions=(
        "body_pct < -3% (candle 1H de crash)",
        "close < BB_lower(20, 2.0) (fora de 2 desviacions)",
        "drop_3h < -5% (caiguda acumulada 3 candles)",
        "hour UTC NOT IN {16, 17, 18, 19} (evitar US afternoon)",
        "vol_rel <= 5 (no pànic extrem / falsos senyals)",
    ),
    exit_rule_baseline="close_of_execution_candle (hold exactament 1H)",
    features_used=(
        "BB_lower(20, 2.0)",
        "RSI_Wilder(7)",
        "drop_acumulat_3h",
        "vol_relatiu_20",
        "body_pct",
    ),
    regime_constraints=("no_us_afternoon (16-19 UTC)",),
    scoring_description=(
        "Score 0-8 basat en: body severity (+1/+2), "
        "drop severity (+1/+2), RSI(7) oversold (+1/+2), "
        "volum alt (+1), hora favorable 20-21 UTC (+1)"
    ),
    scoring_range=(0, 8),
    author="Claude + Roman",
    created_at="2026-03-16",
    notes="Validat amb MC (3/3 PASS) i WF (7/9). Leverage recalibrat a 20x (T1).",
)


# ══════════════════════════════════════════════════════════════
# 2. SetupValidationResult — resultat de validació
# ══════════════════════════════════════════════════════════════

CAPITULATION_SCALP_VALIDATION = SetupValidationResult(
    setup_name="capitulation_scalp_1h",
    asset="ALL",  # ETH+BTC+SOL combinats
    tf_context="4h",
    tf_execution="1h",
    period_start="2017-08-17",
    period_end="2026-03-15",
    sample_size=361,

    # Mètriques core (sense liquidació)
    win_rate=68.0,
    profit_factor=2.5,
    ev_per_trade=50.8,
    avg_win=88.4,
    avg_loss=-82.1,
    win_loss_ratio=1.08,

    # MFE / MAE
    mfe_mean=3.07,
    mfe_median=2.26,
    mae_mean=2.61,
    mae_median=1.50,

    # Drawdown
    max_dd_pct=37.0,
    max_dd_abs=1215.0,

    # Liquidació per leverage (T1)
    liq_rates=[
        LiqRateByLeverage(10, 10.0, 154, 8, 5.2, 2.0, 560),
        LiqRateByLeverage(15, 6.7, 157, 14, 8.9, 4.3, 924),
        LiqRateByLeverage(20, 5.0, 155, 22, 14.2, 5.6, 1114),
        LiqRateByLeverage(30, 3.3, 147, 36, 24.5, 9.2, 1596),
        LiqRateByLeverage(50, 2.0, 129, 49, 38.0, 16.4, 2369),
    ],

    # Monte Carlo
    mc_shuffle_pct_profitable=100.0,
    mc_random_edge_pp=26.8,  # ETH: +26.8pp, BTC: +34.8pp, SOL: +14.8pp
    mc_param_perturb_pct_profitable=100.0,

    # Walk-Forward
    wf_expanding_positive_years=7,
    wf_expanding_total_years=9,
    wf_rolling_positive_years=5,
    wf_rolling_total_years=7,

    # Yearly (amb liquidació 20x)
    yearly=[
        YearlyBreakdown(2017, 23, 78.0, 591, 25.7, True),
        YearlyBreakdown(2018, 22, 45.0, -146, -6.6, False),
        YearlyBreakdown(2019, 4, 50.0, -11, -2.8, False),
        YearlyBreakdown(2020, 22, 64.0, 37, 1.7, True),
        YearlyBreakdown(2021, 37, 54.0, 234, 6.3, True),
        YearlyBreakdown(2022, 26, 62.0, 347, 13.3, True),
        YearlyBreakdown(2023, 6, 67.0, -2, -0.3, False),
        YearlyBreakdown(2024, 4, 25.0, -135, -33.8, False),
        YearlyBreakdown(2025, 10, 50.0, -66, -6.6, False),
        YearlyBreakdown(2026, 1, 100.0, 14, 14.0, True),
    ],

    # Classificació
    status=SetupStatus.WATCHLIST,
    decision_reason=(
        "Edge real (MC PASS 3/3), però EV amb liquidació 20x modest (+5.6$/trade). "
        "5 anys positius / 5 negatius. Potencialment útil dins d'un portfolio "
        "combinat o amb capital més gran. No justifica BUILD sol."
    ),

    validated_at="2026-03-16",
    script="lab/studies/mc_walkforward_capitulation.py, lab/studies/leverage_recalibration.py",
    artifact="lab/out/leverage_recalibration.json",
)


# ══════════════════════════════════════════════════════════════
# 3. OpportunityEstimate — exemple d'estimació real-time
# ══════════════════════════════════════════════════════════════

CAPITULATION_SCALP_OPPORTUNITY_EXAMPLE = OpportunityEstimate(
    setup_name="capitulation_scalp_1h",
    asset="ETHUSDT",
    timestamp="2026-02-05T04:00:00Z",  # exemple real del backtest

    expected_mfe_4h=5.24,   # HIGH tier MFE
    expected_mae_4h=4.27,   # HIGH tier MAE
    expected_mfe_1h=2.88,   # MID tier MFE 1H
    expected_mae_1h=2.21,   # MID tier MAE 1H

    liq_risk_20x=14.2,
    liq_risk_30x=24.5,
    liq_risk_50x=38.0,

    score=5,
    quality_score=0.9,
    confidence=0.7,   # N=36 per HIGH tier, moderat

    tier="HIGH",
    rationale="ETH -4.2% 1H, BB lower trencat, drop 3H -8.3%, RSI(7)=12, 04:00 UTC (Asia)",
)


# ══════════════════════════════════════════════════════════════
# MAIN — mostra l'exemple i valida serialització
# ══════════════════════════════════════════════════════════════

def _run_tests() -> bool:
    ok = True

    # Test 1: SetupSpec camps obligatoris
    spec = CAPITULATION_SCALP_SPEC
    for field_name in ("name", "family", "thesis", "assets", "tf_context",
                       "tf_execution", "entry_conditions", "exit_rule_baseline",
                       "features_used"):
        val = getattr(spec, field_name)
        if not val:
            print(f"  FAIL: SetupSpec.{field_name} buit")
            ok = False

    # Test 2: SetupValidationResult mètriques clau
    val = CAPITULATION_SCALP_VALIDATION
    for field_name in ("sample_size", "win_rate", "profit_factor", "ev_per_trade",
                       "mfe_mean", "mae_mean", "liq_rates",
                       "mc_shuffle_pct_profitable", "mc_random_edge_pp"):
        v = getattr(val, field_name)
        if not v and v != 0:
            print(f"  FAIL: ValidationResult.{field_name} buit/zero")
            ok = False

    if len(val.liq_rates) < 3:
        print(f"  FAIL: liq_rates ha de tenir mínim 3 leverages, té {len(val.liq_rates)}")
        ok = False

    # Test 3: OpportunityEstimate exigeix MFE/MAE
    opp = CAPITULATION_SCALP_OPPORTUNITY_EXAMPLE
    if opp.expected_mfe_4h <= 0 or opp.expected_mae_4h <= 0:
        print("  FAIL: OpportunityEstimate necessita MFE/MAE > 0")
        ok = False
    if opp.expected_mfe_1h <= 0 or opp.expected_mae_1h <= 0:
        print("  FAIL: OpportunityEstimate necessita MFE/MAE 1H > 0")
        ok = False

    # Test 4: Status és vàlid
    if val.status not in SetupStatus:
        print(f"  FAIL: status {val.status} no és vàlid")
        ok = False

    # Test 5: Serialització JSON (dataclass → dict)
    from dataclasses import asdict
    try:
        d = asdict(spec)
        json.dumps(d, default=str)
        d = asdict(val)
        json.dumps(d, default=str)
        d = asdict(opp)
        json.dumps(d, default=str)
    except Exception as e:
        print(f"  FAIL: serialització JSON: {e}")
        ok = False

    return ok


if __name__ == "__main__":
    print("=" * 70)
    print("Exemple Capitulation Scalp 1H — Contracte canònic")
    print("=" * 70)

    print(f"\n  SetupSpec:")
    print(f"    name:      {CAPITULATION_SCALP_SPEC.name}")
    print(f"    family:    {CAPITULATION_SCALP_SPEC.family}")
    print(f"    direction: {CAPITULATION_SCALP_SPEC.direction}")
    print(f"    assets:    {CAPITULATION_SCALP_SPEC.assets}")
    print(f"    tf:        {CAPITULATION_SCALP_SPEC.tf_context} context / {CAPITULATION_SCALP_SPEC.tf_execution} exec")
    print(f"    entries:   {len(CAPITULATION_SCALP_SPEC.entry_conditions)} condicions")
    print(f"    features:  {len(CAPITULATION_SCALP_SPEC.features_used)} indicadors")

    print(f"\n  ValidationResult:")
    v = CAPITULATION_SCALP_VALIDATION
    print(f"    N={v.sample_size} WR={v.win_rate}% PF={v.profit_factor} EV={v.ev_per_trade:+.1f}$/t")
    print(f"    MFE: mean={v.mfe_mean}% med={v.mfe_median}%")
    print(f"    MAE: mean={v.mae_mean}% med={v.mae_median}%")
    print(f"    MC: shuffle={v.mc_shuffle_pct_profitable}% edge={v.mc_random_edge_pp:+.1f}pp perturb={v.mc_param_perturb_pct_profitable}%")
    print(f"    WF: {v.wf_expanding_positive_years}/{v.wf_expanding_total_years} exp, {v.wf_rolling_positive_years}/{v.wf_rolling_total_years} roll")
    print(f"    Liq rates: {', '.join(f'{l.leverage}x={l.liq_rate_pct:.0f}%' for l in v.liq_rates)}")
    print(f"    Status: {v.status}")
    print(f"    Reason: {v.decision_reason[:80]}...")

    print(f"\n  OpportunityEstimate (exemple):")
    o = CAPITULATION_SCALP_OPPORTUNITY_EXAMPLE
    print(f"    asset={o.asset} ts={o.timestamp}")
    print(f"    MFE 4H={o.expected_mfe_4h}% MAE 4H={o.expected_mae_4h}%")
    print(f"    MFE 1H={o.expected_mfe_1h}% MAE 1H={o.expected_mae_1h}%")
    print(f"    score={o.score} tier={o.tier} conf={o.confidence}")

    print(f"\n  Tests:")
    ok = _run_tests()
    n_tests = 5
    print(f"    {n_tests}/{n_tests} PASS" if ok else f"    FAIL")

    sys.exit(0 if ok else 1)
