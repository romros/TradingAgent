# Alquímia v4 — cobertura abans de rendiment

## Motiu de la versió

La v3 demostrava llinatge, holdout, costos, traducció i paritat, però permetia
que `market_preflight` passés amb un mapping recent sense quantificar la
completitud històrica del train. XAU v36 va exposar el risc: la correlació M15
Dukascopy↔Ostium era bona, però només el 42% de les sessions històriques tenia
tota la ruta executable. Les seves mètriques no eren una discovery vàlida.

La v4 no reescriu cadenes v3. Afegeix un contracte nou per a campanyes futures;
US500+VIX l'haurà d'utilitzar quan el gate de tres dies permeti formular-la.

## Cadena canònica

1. `market_preflight`: identitat Ostium, mapping, economia, cobertura històrica
   global ≥90%, cobertura mínima de cada període ≥80%, hash de configuració i
   zero accés a rendiment.
2. `hypothesis_screen`: grid finit determinista, només train, costos
   base/conservador/estrès i regió estable recalculada des de trades de la
   central i els seus veïns. No produeix estratègies SQ.
3. `sq_generation`: projecte StrategyQuant nou; els candidats apareixen aquí
   per primera vegada i cada artefacte SQ queda lligat per SHA-256.
4. `temporal_validation`: finestres independents, degradació limitada i front
   Pareto recomputat sobre expectativa neta, drawdown i estabilitat.
5. `robustness`: 1.000 Monte Carlo, ≥4 veïns a ±10%, estrès 2× i
   liquidació recalculada amb excursió adversa i leverage Ostium provat.
6. `small_account_economics`: 200 USDC, nocional, risc, marge, reserva i
   apalancament admès; PF i EV es deriven de trades als tres costos.
7. `final_holdout_validation`: una sola obertura del 10% final amb candidat i
   paràmetres congelats, sense retuneig.
8. `python_translation`: IR exacta i subset suportat.
9. `parity`: senyals/trades 100%, candles ≥95% i PnL correlacionat ≥0,99.
10. `paper`: configuració paper explícita; live continua requerint autorització
   humana externa.

`REJECT` i `BLOCK` són terminals. Una cadena sintètica pot demostrar que els
cables funcionen, però mai és promocionable ni `paper_ready`.

La cobertura no és un booleà de confiança: el verificador recalcula la ràtio
global amb observacions completes/esperades i el mínim del diccionari de
períodes. Qualsevol resum que no coincideixi matemàticament amb aquests detalls
invalida el rebut.
Un preflight observat conserva també la ruta i el hash de la configuració. El
verificador torna a executar el compositor sobre cobertura, mapping i costos i
exigeix igualtat completa amb l'artefacte rebut. Un input de règim com VIX és
opcional per altres mercats, però si es declara ha de provar l'anti-look-ahead.
Modificar qualsevol font després del rebut invalida la cadena.

## Controls reproduïbles

```bash
python -m lab.sq_bridge.methodology lab/sq_bridge/methodology_v4.json
python -m lab.sq_bridge.e2e_control \
  --methodology lab/sq_bridge/methodology_v4.json \
  --output-dir /tmp/alquimia-v4-control
python -m lab.sq_bridge.evidence_chain verify \
  /tmp/alquimia-v4-control/chain.json \
  --methodology lab/sq_bridge/methodology_v4.json
```

El control esperat té deu rebuts PASS, `operational_control_complete=true`, però
`promotable=false`, `paper_ready=false` i `live_authorized=false` perquè és
sintètic.

L'execució reprenable d'una campanya real està documentada a
[`ALQUIMIA_V4_RUNNER.md`](ALQUIMIA_V4_RUNNER.md).

El `hypothesis_screen` no pot passar amb una simple etiqueta: l'artefacte ha de
provar almenys 50 trades train, PF train ≥1,20, dos veïns estables, aplicació
exacta dels costos base/conservador/estrès, futurs segellats i ≤5.000 intents.
Els intents són les variants reals del trace congelat. Cada variant aporta
retorn brut, costat i durada sobre un nocional canònic de 200 USDC; la topologia
identifica explícitament la central i els veïns. El validador verifica el
SHA-256 dels costos congelats, deriva PnL net, recalcula tots els PF i impedeix
comptar com a estable una configuració aliena o consultar períodes futurs.
La generació SQ queda limitada a 10.000 intents i tres regles. El validador
també rebutja qualsevol metodologia v4 nova que relaxi aquests mínims, els 1.000
Monte Carlo, la probabilitat de liquidació ≤0,1%, el risc ≤1,5% o la reserva
≥40% del compte de 200 USDC.

L'etapa de compte petit ha d'avaluar la graella completa
`1,2,3,5,8,10,15,20,30,50,75,100,150,200` fins al límit vigent del mercat i seleccionar
el valor segur més alt. Cada leverage superior ha de tenir un motiu de rebuig.
El verificador recalcula `collateral=notional/leverage`, marge, reserva i risc al
stop, exigeix stop obligatori, model de liquidació exacte d'Ostium i una
distància de liquidació d'almenys 1,5 vegades el stop. Això maximitza leverage
dins del risc; no confon leverage amb augmentar arbitràriament el nocional.
El nocional queda fixat per `200 × risc% / stop%`; canviar leverage només canvia
el col·lateral requerit. La graella arriba a 200× perquè els màxims 150× i 200×
del venue també s'hagin d'avaluar i rebutjar explícitament quan no superin
robustesa, marge, reserva o distància de liquidació; no es poden ometre. Cada
candidata aporta almenys 30 trades nets sota base,
conservador i estrès. Es recalculen PF≥1,10, EV≥0,10 USDC i pèrdua individual
≤3%. Si en sobreviu més d'una, es congela la de millor EV del pitjor escenari,
després millor PF i finalment ID lexicogràfic; no es consulta el holdout.

Els retorns nets no són una entrada confiada: cada trace aporta retorn brut,
costat i durada. El constructor verifica el SHA-256 del model de costos
congelat, escull el primer bucket mesurat igual o superior al nocional i resta
round-trip més carry. Un nocional superior a la graella o un hash diferent
invalida l'etapa.

La generació usa `genetic_evolution`, no una cerca oberta sense filiació. Cada
artefacte SQ ha d'indicar les hipòtesis font aprovades, el hash de cada candidat
i el nombre de regles (1–3). El verificador de cadena comprova que aquestes
hipòtesis són un subconjunt exacte de les que van passar `hypothesis_screen`;
un candidat d'una família diferent queda invàlid encara que tingui bon PnL.
SQ conserva tots els candidats únics, estructuralment admesos i traduïbles: el
seu `fitness` no coneix encara tota l'economia Ostium ni l'estabilitat temporal
i, per tant, no és el nostre selector final.

El front Pareto es forma després, a `temporal_validation`, només entre candidats
que superen els mínims OOS. Maximitza expectativa neta i proporció de finestres
positives, i minimitza drawdown OOS. L'artefacte ha d'incloure les mètriques de
tot l'univers rebut de `sq_generation`; el verificador recalcula dominància,
impedeix ometre un rival i rebutja la promoció d'un candidat dominat.

El screen, la validació temporal i la robustesa publiquen mètriques individuals
per cada hipòtesi/candidat. Els camps agregats són sempre el pitjor cas
(mínims de trades, PF i finestres positives; màxims de drawdown, decay i
liquidació) i el verificador els recalcula. NaN, infinits i probabilitats fora
de `[0,1]` fallen tancat. L'economia de 200 USDC rep un sol candidat per
campanya; la diversificació combina després diverses cadenes ja aprovades.

Robustesa rep obligatòriament tots els candidats aprovats temporalment. Com a
mínim el 70% dels 1.000 runs i el 75% de quatre veïns paramètrics han de ser
rendibles; el PF amb costos 2× ha de ser ≥1,05. La probabilitat de liquidació
≤0,1% es calcula des de l'excursió adversa de cada run, no des d'un camp
`liquidated`. El leverage de `small_account_economics` queda limitat pel que
aquell mateix candidat va superar aquí, amb el mateix màxim vigent d'Ostium.

Els hashes SQ i de traducció no són camps decoratius. `sq_generation` ha de
referenciar cada `.sqx`; `python_translation` ha de referenciar el `.sqx` font i
la representació intermèdia canònica. El verificador obre aquests fitxers i en
recalcula SHA-256 respecte del directori de l'artefacte. Un fitxer absent,
substituït o alterat invalida la cadena abans de paritat.

Paritat i paper també tenen fitxers JSON hashats. L'informe de paritat ha de
coincidir amb el candidat i amb totes les mètriques declarades. La configuració
paper ha de fixar candidat, capital 200 USDC, `mode=paper`,
`live_authorized=false` i `signer_enabled=false`. Recalcular correctament el hash
d'un JSON amb candidat diferent o signer actiu no el fa vàlid: el contingut
també es comprova.

El constructor de projectes rebutja v4 si rep `random-generation`, si no té
pressupost d'intents o si supera 10.000. Per v4 usa els llindars de
`hypothesis_screen` (el camp v3 `discovery` no existeix). El rebut de generació
referencia també el manifest del projecte i en verifica hash, metodologia,
`genetic-evolution`, pressupost, hash del CFX, capital canònic 200, scaffold amb
rol només tècnic i holdout segellat.
