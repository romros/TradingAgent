# Protocol de recerca intradia FX per a petit inversor

## Objectiu

Buscar un màxim de sis estratègies simples sobre EURUSD i XAUUSD, amb capital
de referència de 250 USD, costos compatibles amb una operativa petita i el
leverage més alt que conservi el risc controlat. No es força cap candidata.

## Dades i divisió temporal

- Font: Parquet M1 local de BrokerageService (Dukascopy), agregat a barres 4H.
- EURUSD: 35.490 barres 4H, 2004-01-01–2026-02-27.
- XAUUSD: 35.147 barres 4H, 2004-01-02–2026-02-27.
- Desenvolupament: fins a 2013-12-31.
- Validació: 2014-01-01–2019-12-31.
- Test final: 2020-01-01–2026-02-27.
- El senyal es calcula al tancament i l'entrada és a l'obertura de la barra 4H
  següent. El test no participa en la selecció.

## Univers de recerca

Sis famílies, amb graelles petites i durades d'1, 2, 3 o 6 barres 4H:

1. Reversió Bollinger/RSI.
2. Breakout Donchian amb filtre de tendència.
3. Pullback en tendència EMA/RSI.
4. Expansió de volatilitat.
5. Reversió després d'una barra gran.
6. Creuament de mitjanes.

## Model de costos i risc

- Capital inicial: 250 USD.
- Gas fix: 0,22 USD per round trip.
- Cost variable base: 2 pb EURUSD i 8 pb XAUUSD.
- Estrès: costos fixos i variables duplicats; auditoria addicional a 3x.
- Finançament: 6% anual sobre exposició prestada, prorratejat per durada.
- Liquidació conservadora quan el MAE toca `1 / leverage`.
- Leverage provat: 1x, 1,5x, 2x, 3x, 4x, 5x, 7,5x i 10x.
- Col·lateral: 5%, 10%, 15% o 20% del capital.

El màxim de 10x i 50 USD de col·lateral provenen del `preflight` local actual
de BrokerageService per EURUSD/XAUUSD. El leverage s'escull amb validació i no
es redueix retrospectivament mirant el test.

## Gates

- Desenvolupament: mínim 50 operacions, EV base i 2x positiva, DD <=20% i
  liquidacions <=1%.
- Validació: PF >=1,20, DD <=20%, liquidacions <=1%, p5 mensual >=-25 USD i EV
  positiva a costos 2x.
- Test: PF >=1,20, DD <=25%, zero liquidacions, p5 mensual >=-25 USD i EV
  positiva a costos 2x.
- Acceptació final: almenys 25 trades en validació i test, 100 totals, PF
  >=1,25 en validació i test i almenys 70% de veïns positius.

Si cap combinació supera els gates sense mirar el test, la decisió és
`NO_CANDIDATE`; no es relaxen costos, mostra ni drawdown a posteriori.
