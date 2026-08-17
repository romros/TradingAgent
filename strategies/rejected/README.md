# Estratègies i famílies rebutjades

- [Campanya ETF i tech transfer 2026-08-15](etf_and_tech_transfer_campaign_20260815.md):
  IWM reversal, momentum/rotació ETF, transfer Momentum60 tech i QQQ
  turn-of-month rebutjats amb els gates congelats; inclou motius i via següent.

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
| XOM momentum mensual 6/12 mesos | 2024 OOS aproximadament −9% i train negatiu | `data/ibkr_sq_v2/xom_d1_edge_v1/screen_v1.json` |
| GOOG/XOM price-action SQ D1 | GOOG sense supervivent; XOM finalista −1,42%, PF 0,947 a OOS estrès | [Fitxa](goog_xom_sq_price_action_20260816.md) |
| SPY turn-of-month recent | 2025–05/2026 tiered −0,73%, PF 0,961 | `data/ibkr_sq_v2/turn_of_month/spy_recent_holdout_v1.json` |
| Turtle 50/20 ampliada | Nous actius PF 1,33, però t combinat només 1,22 i DD 36,8% | `data/ibkr_sq_v2/turtle_50_20/new_asset_transfer_v1.json` |
| AAPL H1 Strategy 0.14113 | OOS tiered PF 1,004 i stress −10,98% | `data/ibkr_sq_v2/aapl_h1_shock_reversion_tiered_pilot/oos/0_14113/small_account_audit.json` |
| AAPL H1 Strategy 0.24306 | Edge OOS aparent, però falla Monte Carlo paramètric natiu ±10% | [Fitxa](aapl_h1_roc_cross_024306.md) |
| Connors RSI(2) recent | Passa brut, però a 2.000 USD l'estrès és −1,06%, PF 0,740 | [Fitxa](connors_rsi2_and_spy_pre_fomc_20260816.md) |
| SPY pre-FOMC MOC i M1 | MOC negatiu; finestra M1 canvia de règim i falla train/OOS | [Fitxa](connors_rsi2_and_spy_pre_fomc_20260816.md) |
| PEAD-EAR multi-actiu | Validació −47,37% composta i PF 0,749 | [Fitxa](pead_ear_and_xlf_price_action_20260816.md) |
| Earnings gap continuation | PF recent 2,64, però només 17 observacions i train compost −2,97% | [Fitxa](earnings_gap_continuation_v1.md) |
| SPY SMA200 1,5× | Validació −10,54% i més DD que buy-and-hold | [Fitxa](leverage_overlays_20260817.md) |
| Leverage constant 2× quatre edges | +10,42% contra SPY +26,93%; finançament sobre cash ineficient | [Fitxa](leverage_overlays_20260817.md) |
| XLF price action SQ D1 | Cinc representants perden en validació; PF 0,60–0,83 | [Fitxa](pead_ear_and_xlf_price_action_20260816.md) |
| NFLX D1 breakout 0.4681 | Edge aparent, però veí DD 40,35% i paritat d'execució incompleta | [Fitxa](nflx_d1_volatility_breakout_04681.md) |
| PEP → KO D1 trend pullback | M1 resol l'ordre intrabar, però KO OOS stress perd −4,87% a −6,72% | [Fitxa](pep_ko_d1_trend_pullback_v1.md) |
| Cinquena edge sobre marge residual | Millora CAGR a 17,70%, però DD 21,01% supera el gate congelat del 20% | [Fitxa](five_edge_residual_margin_v1.md) |
| IDTL TSMOM12 durada | Validation −6,50%, OOS −4,47% i només 5/35 mesos invertit | [Fitxa](idtl_tsmom12_v1.md) |
| IBTM TSMOM12 durada curta | Validació −0,44% i Sharpe combinat 0,229 < 0,40 | [Fitxa](ibtm_tsmom12_v1.md) |
| GOOG Momentum60 sobre marge residual | CAGR millora, però DD 25,06% supera el gate del 20% | [Fitxa](goog_momentum60_residual_margin_v1.md) |

Les watchlists i resultats condicionals no s'inclouen aquí fins que hi hagi una
decisió formal de rebuig.
