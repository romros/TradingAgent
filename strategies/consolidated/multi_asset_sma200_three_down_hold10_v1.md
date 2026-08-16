# Multi-actiu D1 — SMA200 + tres baixades + sortida a 10 sessions

Estat: **edge estadístic de recerca; pendent de paritat nativa SQ i no autoritzat per paper/live**.

## Regla executable

Per cada actiu, al tancament D1:

1. Calcula la mitjana simple dels últims 200 tancaments, inclòs l'actual.
2. Exigeix `close > SMA(200)`.
3. Exigeix tres descensos consecutius: `close[t] < close[t-1] < close[t-2] < close[t-3]`.
4. Compra accions senceres a l'obertura de la sessió següent.
5. Tanca a l'obertura de la desena sessió posterior al senyal.
6. No obre una segona posició en el mateix actiu mentre la primera és viva.

No hi ha stop, take-profit, volum, leverage ni filtre de notícies en aquesta
prova. L'economia congelada usa una butxaca de 1.000 USD per actiu, 1 USD per
ordre i 10 bps adversos a cada costat. Això és una convenció d'avaluació, no
la mida final recomanada.

## Com es va seleccionar

L'embut va congelar abans de rendiment 24 variants de tres famílies conegudes
(trend filter, Donchian i pullback en tendència) sobre deu actius disponibles a
IBKR: AAPL, AMZN, GOOG, META, NVDA, EEM, EFA, IWM, XLE i XLF. Train és
2017–2021; validació, 2022–2023; OOS, 2024.

La selecció exigeix densitat de trades, PF agregat, drawdown de cartera i
transferència a diversos actius. Després de corregir dues errades mecàniques
del prototip (drawdown de cartera i posicions que travessaven fronteres), el
representant congelat va ser SMA200 / 3 baixades / hold 10. Les variants que
havien vist OOS abans de les correccions no es van reutilitzar.

## Evidència OOS 2024

- 85 trades.
- PF agregat: 2,081.
- Retorn mitjà de les deu butxaques: +22,38%.
- Drawdown de la cartera 10% per actiu: 6,14%.
- Sis actius positius i quatre negatius.
- Sense NVDA: 76 trades, PF 1,135, +2,57%, DD 6,77%.
- Les deu proves leave-one-asset-out mantenen retorn positiu i PF >= 1,05.

NVDA és una contribució molt gran (+200,72% en la seva butxaca), però la prova
leave-one-out evita presentar-la com l'única font de l'edge. La dispersió entre
actius continua sent material: META, EEM, EFA i XLE són negatius el 2024.

## Limitacions i següent gate

- És un edge de cartera/equal-weight, no una promesa que cada actiu funcioni.
- L'històric cobreix només 2017–2024 i el 2024 és un sol any OOS.
- Falta reconstrucció SQ, Retest natiu, comparació exacta de senyals i auditoria
  de robustesa per blocs/Monte Carlo.
- Cal decidir una regla de capital compartit i conflictes simultanis abans de
  qualsevol shadow.
- `paper_authorized=false`; `live_authorized=false`.

Evidència reproduïble:

- `lab/sq_bridge/multi_asset_known_edge_funnel_v1.json`
- `lab/sq_bridge/multi_asset_known_edge_funnel_v1.py`
- `data/ibkr_sq_v2/multi_asset_known_edge_funnel_v1/development_boundary_corrected.json`
- `data/ibkr_sq_v2/multi_asset_known_edge_funnel_v1/oos_2024_concentration_audit.json`
