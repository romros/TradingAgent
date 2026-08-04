# Acceptació real del pont SQ → realitat

Data: 2026-08-04. Abast: sis observacions locals ja importades; no es reobren
artifacts externs i no s'utilitza SQCLI.

| Campanya | Decisió | Mètrica coherent | Motiu |
|---|---|---|---|
| `alquimia-eurusd-h4-2026-08` | DESCARTAR | sí | expectativa neta negativa amb costos base |
| `intraday-fx-six-families-2026-08` | DESCARTAR | sí | validació negativa i interval bootstrap sota zero |
| `small-investor-d1-2026-08` | DESCARTAR | sí | el PF final depèn d'un sol trade |
| `sq-0423850-xau-h4-2026-08` | DESCARTAR | sí | OOS negatiu i PF no superior a 1 |
| `alquimia-xau-h4-discovery-07893-is-2026-08` | INCOMPLET | sí | només IS i costos no reconciliats |
| `alquimia-eurusd-h4-41133-window-chain-2026-08` | INCOMPLET | sí | falten normalització, règims i economia actual |

## Què queda demostrat

- Els quatre fracassos coneguts no poden arribar al gate de realitat ni al holdout.
- Una etiqueta `REJECT` sense la mètrica coherent queda `INCOMPLET`, no es copia
  cegament.
- Un candidat positiu fora de train no rep promoció automàtica: `4.1.133` continua
  incomplet fins convertir el resultat en règims, costos actuals i economia del compte.
- Una descoberta IS amb cost mismatch, com `0.7893`, tampoc consumeix holdout.

## Límit i següent pas

Aquesta acceptació comprova decisions sobre metadades i mètriques importades; no
demostra la veracitat dels artifacts originals ni rendibilitat. El següent adaptador
ha d'extreure només camps demostrables d'un SQX/informe verificat i declarar la resta
absent. Només un manifest complet podrà entrar a `reality_transfer.py`.

## Cas cec congelat

Després de construir els gates anteriors es va reservar
`sq-portfolio-1774074144996-2026-08` com a acceptació. Abans d'afegir-ne la regla
es va congelar `portfolio-blind-v1`: havia de rebutjar-se com a evidència de
desplegament si, i només si, coexistien slippage zero i una alerta d'identitat de
component. El resultat és `DESCARTAR` amb consistència mètrica verificada. Això
no declara que la família no tingui edge; declara que aquest artifact agregat no
és una prova executable.
