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
   base/conservador/estrès i regió estable. No produeix estratègies SQ.
3. `sq_generation`: projecte StrategyQuant nou; els candidats apareixen aquí
   per primera vegada i cada artefacte SQ queda lligat per SHA-256.
4. `temporal_validation`: finestres independents i degradació limitada.
5. `robustness`: Monte Carlo, perturbació, estrès i liquidació.
6. `small_account_economics`: 200 USDC, nocional, risc, marge, reserva i
   apalancament admès.
7. `python_translation`: IR exacta i subset suportat.
8. `parity`: senyals/trades 100%, candles ≥95% i PnL correlacionat ≥0,99.
9. `paper`: configuració paper explícita; live continua requerint autorització
   humana externa.

`REJECT` i `BLOCK` són terminals. Una cadena sintètica pot demostrar que els
cables funcionen, però mai és promocionable ni `paper_ready`.

La cobertura no és un booleà de confiança: el verificador recalcula la ràtio
global amb observacions completes/esperades i el mínim del diccionari de
períodes. Qualsevol resum que no coincideixi matemàticament amb aquests detalls
invalida el rebut.

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

El control esperat té nou rebuts PASS, `operational_control_complete=true`, però
`promotable=false`, `paper_ready=false` i `live_authorized=false` perquè és
sintètic.

L'execució reprenable d'una campanya real està documentada a
[`ALQUIMIA_V4_RUNNER.md`](ALQUIMIA_V4_RUNNER.md).

El `hypothesis_screen` no pot passar amb una simple etiqueta: l'artefacte ha de
provar almenys 50 trades train, PF train ≥1,20, dos veïns estables, aplicació
exacta dels costos base/conservador/estrès, futurs segellats i ≤5.000 intents.
La generació SQ queda limitada a 10.000 intents i tres regles. El validador
també rebutja qualsevol metodologia v4 nova que relaxi aquests mínims, els 1.000
Monte Carlo, la probabilitat de liquidació ≤0,1%, el risc ≤1,5% o la reserva
≥40% del compte de 200 USDC.

L'etapa de compte petit ha d'avaluar la graella completa
`1,2,3,5,8,10,15,20,30,50,75,100` fins al límit vigent del mercat i seleccionar
el valor segur més alt. Cada leverage superior ha de tenir un motiu de rebuig.
El verificador recalcula `collateral=notional/leverage`, marge, reserva i risc al
stop, exigeix stop obligatori, model de liquidació exacte d'Ostium i una
distància de liquidació d'almenys 1,5 vegades el stop. Això maximitza leverage
dins del risc; no confon leverage amb augmentar arbitràriament el nocional.

La generació usa `genetic_evolution`, no una cerca oberta sense filiació. Cada
artefacte SQ ha d'indicar les hipòtesis font aprovades, el hash de cada candidat
i el nombre de regles (1–3). El verificador de cadena comprova que aquestes
hipòtesis són un subconjunt exacte de les que van passar `hypothesis_screen`;
un candidat d'una família diferent queda invàlid encara que tingui bon PnL.
