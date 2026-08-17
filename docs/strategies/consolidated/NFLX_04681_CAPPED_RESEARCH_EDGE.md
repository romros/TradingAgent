# NFLX D1 0.4681 — edge de breakout capat

## Estat

**Edge estadístic de recerca consolidat i component marginal teòric admès,
amb notional màxim de 1.000 USD dins el compte de 2.000 USD.** No autoritza
paper ni live.

## Regla reproduïble

- Actiu: NFLX, D1, només long.
- Condició: `Low[3] < High[1]`.
- Entrada stop: màxim de `High(10)[1] + 0,30 × ATR(104)[3]`.
- Ordre vàlida 80 barres i reemplaçada quan es recalcula.
- Stop: `2,5 × ATR(15)`; target: `2,8 × ATR(15)`.
- Contracte de risc consolidat: com a màxim 50% de l’equity de la màniga,
  accions senceres i sense palanquejament addicional.

## Evidència central

- OOS 2024, 1.000 USD stress: 10 trades, +31,33%, PF 5,65 i DD 5,36%; els
  quatre trimestres són positius.
- Paritat independent: 68/68 trades explicats.
- Auditoria M1 central: entrades i sortides executables, cap ambigüitat
  optimista i sessions RTH de 390 minuts.
- Monte Carlo natiu de paràmetres ±10%: 2.000 simulacions conceptuals, 100%
  rendibles; mediana +9,05%, percentil 5 +8,16% i mínim +7,24% sobre el balanç
  SQ de 10.000.
- Veïnat capat al 50%: 10/10 variants positives, PF 1,88–2,44 i DD
  6,73–18,01%. El veí stop 2,25 tenia dos trades same-session; M1 confirma que
  en tots dos l’entrada precedeix el target i el stop no es toca abans.

## Admissió marginal, sense reescriure el gate original

El gate original a exposició completa va fallar: un veí arribava a 40,35% de
DD i un altre no tenia paritat D1 suficient. El cap del 50% és una remediació
de risc posterior, no una excusa per reescriure aquell resultat. Per això:

- es conserva el `REJECT_PARAMETER_NEIGHBORHOOD` original;
- el nou PASS es diu explícitament `post_observation_risk_remediation`;
- la prova marginal canònica 2022–2024 passa: la cartera puja de +56,04% a
  +89,73%, CAGR de 16,00% a 23,81%, amb DD 19,29%;
- NFLX executa 26/26 senyals, aporta 710,30 USD abans de 36,58 USD de
  finançament incremental i manté PF 2,43;
- aquesta admissió és per aportació marginal i risc capat; no converteix el
  FAIL original a exposició completa en un PASS;
- el període 2025+ continua sent holdout i no s’ha usat en aquesta decisió.

## Evidència

- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/oos_gate_audit.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/native_mc_gate_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/neighborhood/capped_50pct_remediation_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/neighborhood/stop225_same_bar_m1_v1.json`
- `data/ibkr_sq_v2/nflx_04681_residual_margin_portfolio_v1/result.json`
