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

## Per què queda fora

- El gate havia fixat DD màxim de 25%; el pitjor veí arriba a 40,35%.
- La variant veïna de stop 2,25 ATR continua sense una auditoria M1 pròpia;
  l'auditoria executada cobreix exclusivament la regla central 0.4681 i no pot
  rescatar retroactivament el gate de tot el veïnat.

Evidència principal:

- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/neighborhood/neighborhood_gate.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_independent_parity_v1.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_m1_execution_audit_v1.json`

## Via futura legítima

No s'ha de rescatar retocant el gate després de veure aquests resultats. La
via legítima és una nova prova de robustesa independent i preregistrada que no
seleccioni paràmetres després de veure performance. L'execució central ja no
és el bloqueig; ho és l'estabilitat extrema del veïnat.
