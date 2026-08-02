# Dels números a la vida real

Un OOS positiu respon «aquestes regles van sobreviure aquest tall?». No respon si
la causa continua existint ni si la posició mínima és operable avui.

## Contracte general

1. Formular el mecanisme abans de mirar el tram final i escriure què el falsaria.
2. Dividir la història per canvis econòmics, microestructurals i de volatilitat;
   les dates són conseqüència, no la definició del règim.
3. Etiquetar tendència/rang, crisi, inflació, tipus reals, divisa, volatilitat,
   liquiditat i flux dominant quan siguin rellevants per l'instrument.
4. Mesurar trades, expectativa neta, drawdown i concentració per règim.
5. Cercar règims moderns comparables pel mecanisme, no simplement anys posteriors.
6. Escalar distàncies i risc per ATR, volatilitat o percentatge quan la hipòtesi
   ho permeti; justificar qualsevol quantitat fixa.
7. Recalcular preu, spread, slippage, comissió, swap/funding, mida mínima,
   nocional, marge i liquidació amb data i venue actuals.
8. Executar una sola vegada el període final segellat. Si falla, no reajustar-hi.

## Exemple XAU, no excepció XAU

2004–2015 barreja expansió, crisi, polítiques extraordinàries, gran cicle alcista
i reversió. El 2025–Q1 2026 mostra preus, ETF, demanda oficial i volatilitat molt
diferents. Això invalida stops monetaris comparats mecànicament, però no demostra
que una regla normalitzada per ATR funcioni: només crea una hipòtesi a provar.

El candidat `0.7893` encara no té artifact local identificable. Sabem que una
combinació EMA/SMA, ADX i ATR podria escalar millor que distàncies fixes; no sabem
si el benefici travessa règims. L'exemple JSON queda deliberadament en
`DESCARTAR` fins que hi hagi resultats per règim i condicions Ostium verificades.

Executar:

```bash
python3 academia/tools/reality_transfer.py academia/experiments/examples/reality-transfer-xau-example.json
```

Fonts: `wgc_gold_demand_2025` i `wgc_gold_demand_q1_2026`.
