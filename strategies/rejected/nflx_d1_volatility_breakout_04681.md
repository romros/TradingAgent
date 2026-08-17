# NFLX D1 volatility breakout 0.4681 — no consolidada

## Decisió

`Strategy 0.4681` mostra un edge aparent fort, però no entra a
`strategies/consolidated`: ha fallat el gate de robustesa paramètrica congelat
malgrat haver superat posteriorment la paritat independent i l'auditoria M1.

No està autoritzada per paper ni live. Tampoc s'ha consultat 2025.

## Regla exacta de SQ

- Actiu: NFLX, D1, només long.
- Condició: `Low[3] < High[1]`.
- Entrada stop: màxim dels 10 highs previs + `0,30 × ATR(104)[3]`.
- Ordre vàlida 80 barres, amb substitució de l'ordre existent.
- Stop loss: `2,5 × ATR(15)`.
- Profit target: `2,8 × ATR(15)`.
- Sense sortida temporal.

El SQX original és
`data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/train_selected/Strategy 0.4681.sqx`
(SHA-256 `04ecb1cb88854c787530ad2d5d899b119e486898bef751e638a83a4922aae643`).

## Evidència favorable

- Validació 2022–2023, 2.000 USD stress: +47,61%, PF 1,859, DD 12,36%,
  16 operacions i 3/4 semestres positius.
- OOS segellat 2024, 2.000 USD stress: +45,00%, PF 5,638, DD 7,70%,
  10 operacions i 4/4 trimestres positius.
- En la graella preregistrada de deu veïns, 9/10 variants auditables són
  rendibles amb costos d'estrès i PF ≥1,10.
- La rèplica Python reprodueix exactament les 68/68 operacions de SQ, sense
  cap discrepància de data, tipus de sortida o preu. La paritat incorpora la
  vida real de `EnterAtStop`: gap abans d'`OnBarUpdate`, rebuig d'ordres noves
  fora de rang, ATR/bracket congelats en crear l'ordre i reentrada només
  després d'una sortida al mateix open.
- L'auditoria dels 2.872.800 minuts Dukascopy confirma 68/68 entrades i 68/68
  sortides executables, cap bracket contrari tocat abans i cap minut ambigu
  resolt favorablement. Les 1.995 sessions RTH tenen 390 minuts.
- La prova de resiliència estadística central, preregistrada després de resoldre
  la paritat però abans de calcular-la, passa 5/5 gates. Amb 100 bps per round
  trip conserva PF 1,90; sense els tres millors trades conserva PF 1,88; els
  blocs 2017–2020 i 2021–2024 donen PF 2,14 i 2,18. Els tres guanyadors més
  grans només representen el 12,7% dels guanys positius. En 20.000 bootstraps
  anuals, la probabilitat de retorn compost positiu és 100% i el percentil 5
  és +194%. Aquests retorns compostos són una prova estadística per trade, no
  una previsió de cartera ni una recomanació d'assignar-hi tot el capital.
- La prova de sizing preregistrada amb 3.000 USD, accions senceres, sense
  leverage, comissió IBKR fixed i 10 bps adversos per costat selecciona 75%
  d'exposició pel millor Calmar: CAGR teòric 20,60%, PF 2,33 i DD sobre equity
  tancada 9,40%. A 100% d'exposició, la regla arriba a CAGR 27,86% versus
  25,10% del buy-and-hold diagnòstic, però amb pitjor Calmar. El 75% no supera
  buy-and-hold en retorn brut; prioritza estabilitat i reserva 25% per a altres
  edges. L'auditoria diària mark-to-market posterior passa el veto congelat:
  DD 15,24% per l'estratègia al 75% versus 75,15% per buy-and-hold NFLX sobre
  les mateixes dates. Continua faltant risc intraminut i de gap extrem abans
  de considerar capital real.

## Per què queda fora

- El gate havia fixat DD màxim de 25%; el pitjor veí arriba a 40,35%.
- La variant veïna de stop 2,25 ATR continua sense una auditoria M1 pròpia;
  l'auditoria executada cobreix exclusivament la regla central 0.4681 i no pot
  rescatar retroactivament el gate de tot el veïnat.

Evidència principal:

- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/neighborhood/neighborhood_gate.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_independent_parity_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_m1_execution_audit_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_statistical_resilience_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_risk_overlay_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_daily_mtm_v1.json`

## Via futura legítima

No s'ha de rescatar retocant el gate després de veure aquests resultats. La
via legítima és una nova prova de robustesa independent i preregistrada que no
seleccioni paràmetres després de veure performance. L'execució central ja no
és el bloqueig; ho és l'estabilitat extrema del veïnat.
