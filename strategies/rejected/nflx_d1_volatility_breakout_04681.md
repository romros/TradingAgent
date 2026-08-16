# NFLX D1 volatility breakout 0.4681 — no consolidada

## Decisió

`Strategy 0.4681` mostra un edge aparent fort, però no entra a
`strategies/consolidated`: ha fallat el gate de robustesa paramètrica congelat
i encara no té paritat independent completa amb l'execució nativa de SQ.

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

## Per què queda fora

- El gate havia fixat DD màxim de 25%; el pitjor veí arriba a 40,35%.
- La variant de stop 2,25 ATR conté una entrada i target a la mateixa barra D1
  que no permet demostrar l'ordre intradia amb OHLC diari.
- La rèplica Python obté 68 operacions, igual que SQ, i coincideix exactament
  en les deu primeres; després divergeix en la semàntica de manteniment de
  l'ordre pendent i dels brackets en gaps. Per tant, la paritat continua
  formalment rebutjada.

Evidència principal:

- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/neighborhood/neighborhood_gate.json`
- `data/ibkr_sq_v2/nflx_d1_volatility_breakout_v1/robustness/nflx_04681_python_parity.json`

## Via futura legítima

No s'ha de rescatar retocant el gate després de veure aquests resultats. Una
nova versió només seria legítima amb una hipòtesi preregistrada diferent i una
font intradia que resolgui les entrades stop, gaps i barres que toquen SL/TP.
