"""
lab/contracts/models.py — Contracte canònic del LAB per setups

Defineix les 3 estructures centrals:
  - SetupSpec:              descripció completa d'un setup
  - SetupValidationResult:  resultat de validar un setup sobre un asset/tf
  - OpportunityEstimate:    estimació en temps real per alimentar agents de risc/exit

Marc temporal:
  - tf_context:   4H (finestra de context per indicadors i scoring)
  - tf_execution: 1H (finestra d'entrada → sortida del trade)

Cicle de vida d'un setup:
  CANDIDATE → ACCEPTED | WATCHLIST | REJECTED

Ús:
  from lab.contracts.models import SetupSpec, SetupValidationResult, OpportunityEstimate
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ══════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════

class SetupStatus(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    ACCEPTED_D1_ASSET = "accepted_d1_asset"  # D1 per asset: N>=35, EV>=8$, PF>=1.8, liq<=5%, WF>=70%
    WATCHLIST = "watchlist"
    REJECTED = "rejected"


class SetupFamily(StrEnum):
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    CAPITULATION = "capitulation"
    SEASONAL = "seasonal"
    PATTERN = "pattern"


# ══════════════════════════════════════════════════════════════
# SetupSpec — descripció completa d'un setup
# ══════════════════════════════════════════════════════════════

@dataclass(slots=True)
class SetupSpec:
    """Descripció declarativa d'un setup. No conté lògica d'execució."""

    # Identitat
    name: str                          # ex: "capitulation_scalp_1h"
    version: str = "1.0"              # per versionat de regles
    family: SetupFamily = SetupFamily.CAPITULATION

    # Tesi
    thesis: str = ""                   # ex: "Rebot de capitulació: crash extrem → bounce 1H"
    direction: str = "LONG"            # LONG | SHORT | BOTH

    # Assets i timeframes
    assets: tuple[str, ...] = ()       # ex: ("ETHUSDT", "BTCUSDT", "SOLUSDT")
    tf_context: str = "4h"             # finestra de context (indicadors, scoring)
    tf_execution: str = "1h"           # finestra d'execució (entry → exit)

    # Regles d'entrada (text descriptiu + condicions programàtiques)
    entry_conditions: tuple[str, ...] = ()
    # ex: ("body_pct < -3%", "close < BB_lower(20,2)", "drop_3h < -5%",
    #       "hour NOT IN {16,17,18,19}", "vol_rel <= 5")

    # Regla de sortida baseline
    exit_rule_baseline: str = "close_of_execution_candle"
    # ex: "close_of_execution_candle" (hold 1H), "trailing_stop", "fixed_tp_sl"

    # Features/indicadors usats
    features_used: tuple[str, ...] = ()
    # ex: ("BB_lower(20,2)", "RSI(7)", "drop_3h", "vol_rel_20")

    # Restriccions de règim
    regime_constraints: tuple[str, ...] = ()
    # ex: ("no_us_afternoon",) o ("bull_only",) o ()

    # Scoring
    scoring_description: str = ""
    scoring_range: tuple[int, int] = (0, 8)

    # Metadata
    author: str = ""
    created_at: str = ""
    notes: str = ""


# ══════════════════════════════════════════════════════════════
# LiqRateByLeverage — liquidació per leverage
# ══════════════════════════════════════════════════════════════

@dataclass(slots=True, frozen=True)
class LiqRateByLeverage:
    """Liquidation rate per a un leverage donat."""
    leverage: int
    liq_threshold_pct: float     # 1/leverage * 100
    n_trades: int
    n_liquidated: int
    liq_rate_pct: float          # n_liquidated / n_trades * 100
    ev_per_trade: float          # EV amb liquidació simulada
    capital_final: float         # capital final amb compounding


# ══════════════════════════════════════════════════════════════
# YearlyBreakdown — desglosament per any
# ══════════════════════════════════════════════════════════════

@dataclass(slots=True, frozen=True)
class YearlyBreakdown:
    year: int
    n_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    is_positive: bool


# ══════════════════════════════════════════════════════════════
# SetupValidationResult — resultat de validar un setup
# ══════════════════════════════════════════════════════════════

@dataclass(slots=True)
class SetupValidationResult:
    """Resultat de validar un setup sobre un asset/tf amb backtest + MC + WF."""

    # Identificació
    setup_name: str
    asset: str                         # "ETHUSDT" o "ALL" si multi-asset
    tf_context: str = "4h"
    tf_execution: str = "1h"

    # Sample
    period_start: str = ""             # ex: "2017-08-17"
    period_end: str = ""               # ex: "2026-03-15"
    sample_size: int = 0

    # Mètriques core
    win_rate: float = 0.0              # %
    profit_factor: float = 0.0
    ev_per_trade: float = 0.0          # $ (amb fees i liquidació)
    avg_win: float = 0.0               # $
    avg_loss: float = 0.0              # $
    win_loss_ratio: float = 0.0        # avg_win / abs(avg_loss)

    # MFE / MAE
    mfe_mean: float = 0.0             # max favorable excursion (%)
    mfe_median: float = 0.0
    mae_mean: float = 0.0             # max adverse excursion (%)
    mae_median: float = 0.0

    # Drawdown
    max_dd_pct: float = 0.0
    max_dd_abs: float = 0.0

    # Liquidació per leverage
    liq_rates: list[LiqRateByLeverage] = field(default_factory=list)

    # Monte Carlo
    mc_shuffle_pct_profitable: float = 0.0   # % de sims profitables
    mc_random_edge_pp: float = 0.0           # pp d'avantatge vs random entry
    mc_param_perturb_pct_profitable: float = 0.0

    # Walk-Forward
    wf_expanding_positive_years: int = 0
    wf_expanding_total_years: int = 0
    wf_rolling_positive_years: int = 0
    wf_rolling_total_years: int = 0

    # Yearly breakdown
    yearly: list[YearlyBreakdown] = field(default_factory=list)

    # Classificació
    status: SetupStatus = SetupStatus.CANDIDATE
    decision_reason: str = ""

    # Metadata
    validated_at: str = ""
    script: str = ""                   # ex: "lab/studies/mc_walkforward_capitulation.py"
    artifact: str = ""                 # ex: "lab/out/leverage_recalibration.json"
    notes: str = ""


# ══════════════════════════════════════════════════════════════
# OpportunityEstimate — estimació per alimentar agents
# ══════════════════════════════════════════════════════════════

@dataclass(slots=True, frozen=True)
class OpportunityEstimate:
    """
    Estimació en temps real d'una oportunitat detectada.
    Alimenta l'agent de risc (sizing, leverage) i l'agent d'exit (TP/SL dinàmic).

    Es genera quan strategy.evaluate() detecta un setup actiu.
    """

    # Identificació
    setup_name: str
    asset: str
    timestamp: str                     # ISO UTC de la candle trigger

    # Estimacions 4H (distribució esperada)
    expected_mfe_4h: float             # % — fins on pot pujar en 4H
    expected_mae_4h: float             # % — fins on pot baixar en 4H

    # Estimacions 1H (finestra d'execució)
    expected_mfe_1h: float             # % — MFE dins la candle 1H d'execució
    expected_mae_1h: float             # % — MAE dins la candle 1H d'execució

    # Risc de liquidació
    liq_risk_20x: float                # % — probabilitat de liquidació amb 20x
    liq_risk_30x: float                # % — probabilitat de liquidació amb 30x
    liq_risk_50x: float                # % — probabilitat de liquidació amb 50x

    # Qualitat del senyal
    score: int                         # 0-8 (scoring del setup)
    quality_score: float               # 0.0-1.0 (qualitat de dades, confiança)
    confidence: float                  # 0.0-1.0 (confiança basada en N històric)

    # Context
    tier: str = ""                     # "LOW" | "MID" | "HIGH"
    rationale: str = ""                # text lliure explicant per què
    notes: str = ""
