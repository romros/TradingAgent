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

Les watchlists i resultats condicionals no s'inclouen aquí fins que hi hagi una
decisió formal de rebuig.

