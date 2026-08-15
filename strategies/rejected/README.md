# Estratègies i famílies rebutjades

Aquest directori evita repetir recerques mortes. Un rebuig no s'ha de
"rescatar" canviant paràmetres després de veure l'OOS/holdout; una nova idea ha
de tenir un mecanisme i una preregistració nous.

| Família/candidata | Motiu principal | Evidència |
|---|---|---|
| AAPL four-rise | Holdout recent negatiu després de costos | [Fitxa](aapl_four_rise.md) |
| AAPL H1 ROC 4-1-174 | OOS stress −17,19%, PF 0,731 | `data/ibkr_sq_v2/aapl_h1_roc_reversion_genetic/oos/4_1_174/small_account_audit.json` |
| JNJ defensive D1 | Candidats fallen costos o tenen exits D1 ambigus | `data/ibkr_sq_v2/jnj_d1_defensive_pilot/validation_summary_v1.json` |
| SPY Turnaround Tuesday | Validació −21,42%, PF 0,390 | `data/ibkr_sq_v2/turnaround_tuesday/screen_v1.json` |
| SPY gap-down recovery | Validació −7,27%, PF 0,735 | `data/ibkr_sq_v2/spy_gap_down_recovery/screen_v1.json` |
| Multi-asset dual momentum | Validació −28,08%, PF 0,247 | `data/ibkr_sq_v2/multi_asset_dual_momentum/screen_v1.json` |
| IBS daily reversion | Cap actiu transferible positiu | `data/ibkr_sq_v2/ibs_reversion/screen_v1.json` |
| Confirmed capitulation cross-asset | Només 1/36 variants passa; regió fràgil | `data/ibkr_sq_v2/confirmed_capitulation_cross_asset_v1/screen.json` |
| SPY D1 short reversal | Dues famílies sense regió estable després de costos | [Fitxa](spy_d1_short_reversal_families.md) |
| GLD D1 breakout | Zero trades completats al 2024 OOS | [Fitxa](gld_d1_breakout_v1.md) |
| SPY turn-of-the-month | Efecte positiu però t-stat 1,410 < 1,645; OOS 2024 segellat | [Fitxa](spy_turn_of_month_v1.md) |
| SPY Halloween standalone | 9 temporades +60,56%, però t-stat 1,493 < 1,645 | `data/ibkr_sq_v2/halloween_equity/recent_holdout_v1.json` |
| AAPL open→close diari | Brut +11,2 bps, però a 1.000 USD −11,47% net i PF 0,960 | `data/ibkr_sq_v2/aapl_intraday_confirmation_v1/screen_v1.json` |
| Futurs TSMOM diversificats proxy | Positiu als tres trams, però Sharpe combinat 0,553 < 0,65 | `data/ibkr_sq_v2/diversified_futures_tsmom_v1/screen_v1.json` |

Les watchlists i resultats condicionals no s'inclouen aquí fins que hi hagi una
decisió formal de rebuig.
