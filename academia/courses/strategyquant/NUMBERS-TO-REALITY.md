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

## Decisions que no s'han de barrejar

- `INCOMPLET`: falten dades; no és prova que la lògica sigui dolenta.
- `DESCARTAR`: ha fallat un gate que invalida el candidat actual.
- `PROVA DIRIGIDA`: hi ha un únic dubte resoluble sense obrir el holdout.
- `OBRIR HOLDOUT`: mecanisme, règims i economia passen; el tram final continua intacte.
- `PREPARAR PAPER TRADING`: el holdout ja ha passat; encara falten traducció i paritat.

El nocional mínim superior al capital no implica automàticament inviabilitat: implica
palanquejament. La pregunta correcta és si el palanquejament requerit queda per sota
d'un límit segur justificat amb marge i liquidació. Si aquest límit falta, la decisió
és una prova dirigida, no una suposició optimista.

Per comptes petits, informar també en diners: risc per trade, expectativa neta per
trade i estimació anual basada en freqüència observada. Una estratègia pot tenir edge
positiu i ser massa petita per compensar complexitat, errors i temps operatiu.

Els placeholders s'han de marcar amb `current_execution.evidence_complete=false`.
Zero significa zero mesurat; no s'ha d'utilitzar per representar «encara no ho sé».

## Incubació no és només un altre backtest

Deixar una regla intacta i observar dades que encara no existien és evidència més
forta que afegir una altra pertorbació sobre el mateix historial. Pot ser paper,
retest posterior segellat o live controlat; cada via necessita logs, costos i
paritat. «Ho tinc en producció» no basta sense artifact i mètriques verificables.

En un cas aportat per l'usuari, l'àudio revisa un edge XAUUSD D1 un any després,
canvia de Dukascopy a ticks Darwinex i declara spread, comissió i swap. És un bon
patró conceptual. No podem validar el resultat perquè les mètriques només apareixen
a pantalla, la transcripció no les conté i la versió de producció afegeix filtres
a la regla crua. Font exploratòria: `yt_ruben_pgxeiqau1hu`, 00:01–06:39.

Regla: separar sempre **afirmació de l'àudio**, **valor visible a pantalla** i
**artifact reproduïble**. Si una capa falta, limitar la conclusió.

## El mecanisme també té data de caducitat

Una regla de gap pot degradar-se si s'amplia l'horari de negociació i disminueix
el temps en què el mercat queda tancat. Una regla horària pot canviar per DST,
sessió o fus del broker. Una estacional pot desaparèixer quan canvien participants,
contractes o calendari. Per tant, l'informe ha d'identificar el driver proposat,
una variable observable que el representi i una condició de retirada. Si no podem
explicar què ha de continuar existint, la transferència queda en exploració.

Fonts exploratòries que motiven aquesta comprovació, no que la demostren:
`yt_ruben_g21taqv7ou` 06:09–09:14, `yt_ruben_sseje4vpgpu` 00:31–02:34 i
`yt_ruben_y0kztm5duxg` 00:01–05:30.

## Exemple XAU, no excepció XAU

2004–2015 barreja expansió, crisi, polítiques extraordinàries, gran cicle alcista
i reversió. El 2025–Q1 2026 mostra preus, ETF, demanda oficial i volatilitat molt
diferents. Això invalida stops monetaris comparats mecànicament, però no demostra
que una regla normalitzada per ATR funcioni: només crea una hipòtesi a provar.

El candidat `0.7893` encara no té artifact local identificable. Sabem que una
combinació EMA/SMA, ADX i ATR podria escalar millor que distàncies fixes; no sabem
si el benefici travessa règims. L'exemple JSON queda deliberadament en
`INCOMPLET` fins que hi hagi resultats per règim i condicions Ostium verificades.

Executar:

```bash
python3 academia/tools/reality_transfer.py academia/experiments/examples/reality-transfer-xau-example.json
```

Fonts: `wgc_gold_demand_2025` i `wgc_gold_demand_q1_2026`.
