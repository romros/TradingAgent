# Alquímia — laboratori quantitatiu SQ → Ostium

**Data:** 2026-08-02
**Estat:** MVP en construcció; validació XAU H4 executada
**Capital canònic:** 200 USDC

Perfil i guardrails de l'operador:
[`OPERATOR_PROFILE_AND_RISK_POLICY.md`](OPERATOR_PROFILE_AND_RISK_POLICY.md).

## Missió

Alquímia és el laboratori determinista per descobrir, falsar i industrialitzar
estratègies executables directament a Ostium. StrategyQuant genera candidats;
MT4 és només un format d'exportació; el runtime final és Python amb TradingAgent
(decisió/risc) i BrokerageService (dades/execució).

Objectiu: 3–6 estratègies robustes i complementàries per a un petit inversor.

## Pipeline canònic

```text
Mercat Ostium executable
 → timeframe/dataset certificats
 → generació evolutiva SQ
 → IS → OOS → Monte Carlo/estrès → walk-forward
 → tuning controlat → holdout final congelat
 → exportació SQ/MT4/pseudocodi → traducció Python
 → paritat SQ↔Python → paritat SQ↔BS↔Ostium
 → simulació 200 USDC → paper Ostium
 → live només amb evidència i autorització explícita
```

TRAIN cerca estructures; VALIDATION selecciona; OOS/walk-forward comprova
estabilitat; FINAL HOLDOUT no s'utilitza mai per ajustar. Si falla el holdout,
es rebutja o es formula una hipòtesi nova. Cada campanya registra configuració,
rangs, versions, datasets, seed quan SQ l'exposi i hashes.

## Gate Ostium abans de gastar CPU

Cal confirmar: perpetual actual, pair/pair ID, símbols SQ i BS, històric comparable,
oracle, horari, fees, rollover, leverage, mínims compatibles amb 200 USDC i paritat
certificable. `research_eligible` permet investigar; `live_eligible` exigeix PASS
del registre BS. Allowlist: [`lab/sq_bridge/ostium_markets.json`](../lab/sq_bridge/ostium_markets.json).

Ostium ofereix perpetuals sintètics liquidats en USDC, no tokens spot custodiats.

## Robustesa

- Monte Carlo/bootstraps i ordre de trades.
- Spread, slippage, retard, costos base/conservadors/estrès.
- Pertorbació de paràmetres i candles.
- Walk-forward i règims de mercat.
- MAE, gaps, liquidació i leverage.
- Correlació/exposició de cartera.
- Fonts, timezone, sessions i construcció de candles.

Un PASS de SQ només autoritza verificació independent.

## SQ/MT4 → Python

`.sqx` és propietari: no pressuposem traducció universal. Limitarem SQ a blocs
suportats; qualsevol regla no reproduïble queda `UNSUPPORTED`. Python ha de
reproduir senyals, timestamps, entries/exits, stops/targets, trades i PnL dins
toleràncies. Després es recalcula amb bid/ask, impact, gas, fees i rollover Ostium.

## Compte petit: 200 USDC

SQ pot usar 10.000 USD com a escala tècnica, però Alquímia resimula
100/200/300/500/1.000 USDC i decideix sobre 200.

```text
risk_budget = equity × risk_per_trade
notional = risk_budget / adverse_move_or_stop_pct
required_leverage = notional / collateral
approved_leverage = min(required_leverage, venue_max, BS_guard_max,
                        stress_safe_max, portfolio_risk_max)
```

Inclou mínims, collateral, bid/ask, impact, slippage, gas, fees, rollover, horari,
tancament diari, liquidació, drawdown i reserva. El leverage no crea edge: es tria
el més alt que encara supera els gates.

Verdictes: `SMALL_ACCOUNT_200_USDC_VIABLE`, `VIABLE_BUT_TOO_INFREQUENT`,
`NOT_VIABLE_COSTS`, `NOT_VIABLE_MIN_SIZE`, `NOT_VIABLE_LIQUIDATION` i
`NOT_VIABLE_WITH_200_USDC`.

## Pipelines, hooks i servei futur

Pipelines versionades: crear, iniciar, aturar, reprendre, observar, exportar i
arxivar. Configuracions manuals antigues són plantilles, mai execucions cegues.

```text
SQ stdout/API → parser local → status.json → hook de canvi/finalització
```

L'estat conté fase, generades/acceptades/rebutjades, errors, recursos, hashes i
artifacts. PinchTab/Playwright només si SQCLI no cobreix una configuració. Primer
CLI i artifacts; API/web només quan el pipeline complet funcioni. Recerca mai
autoritza live.

La política canònica per pressupost, estancament, checkpoints i recuperació és
[`SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md`](SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md).
El watchdog pilot existent encara no implementa tota aquesta política.

## MSFT: calendari i sessió

### Política de fonts

Dukascopy és la font històrica preferida quan l'actiu hi existeix, perquè les
campanyes anteriors han mostrat millor paritat de preu i hora amb Ostium que
Yahoo. Yahoo no s'ha de considerar automàticament executable a Ostium.

`MSFT`, `NVDA` i `NDXUSD` no estan disponibles a Dukascopy segons el contracte
actual de BrokerageService. Per aquests actius, Yahoo només pot actuar com a
font de recerca provisional i de referència per ajustos corporatius. Abans de
Builder cal certificar contra el tram natiu d'Ostium: escala de preus, retorns
D1, gaps, timestamp/sessió, splits i divergència OHLC. Si aquesta paritat no és
explicable o supera els llindars congelats, la família queda bloquejada encara
que el backtest Yahoo sigui positiu.

El recurs SQ i el mapping també han de coincidir explícitament: el recurs nou
és `MSFT`, el broker usa `MSFT` i Ostium executa `MSFTUSD`. El símbol SQ antic
`MSFTUSUSD_TICK_UTCMinus05` no es reutilitza sense demostrar-ne la procedència.

La recerca MSFT es divideix deliberadament en dues famílies independents:

- `MSFT D1 calendar`: dia de la setmana, dia/setmana del mes, primer o últim
  dia de negociació i direcció long/short. Long i short s'avaluen per separat;
  no s'imposa simetria ni es permet seleccionar el millor dia després de veure
  el holdout.
- `MSFT intraday session`: hora d'entrada, hora de sortida i franges de sessió.
  Aquesta família queda bloquejada fins a disposar d'un historial intradia llarg,
  amb timezone, DST, sessió regular i paritat amb `MSFTUSD` d'Ostium certificats.

La família de calendari ha de corregir explícitament per múltiples proves: cada
combinació dia/direcció compta com una hipòtesi intentada. A més dels gates
habituals, ha de superar validació temporal per anys, comparació amb entrada
aleatòria condicionada al mateix nombre d'operacions i costos del compte de
200 USDC. Els aproximadament cinc mesos de candles natives Ostium disponibles
el 2026 només serveixen per paritat recent, no per descobrir efectes horaris.

### Resultat MSFT D1 close v1 (2026-08-02)

La paritat recent certifica únicament el tancament D1: 95 dies solapats,
diferència mediana 5,28 bps, p95 24,65 bps i correlació de retorns 0,9975 entre
Yahoo sense ajustar i el tancament robust d'Ostium. Open/high/low i execució
intrabar continuen sense certificar.

SQ va generar 80 estratègies en quatre famílies (trend/calendar × long/short).
El front Pareto IS va congelar 48 candidats. El Retest SQCLI 143 queda encallat
després de preparar MSFT fins i tot amb un sol SQX; es va aturar netament i es
va activar el fallback Python auditable. El traductor reprodueix el subset
close/calendar, entrada next-open, stop percentual o ATR i target ATR, amb stop
primer quan una barra toca stop i target.

Validació + OOS van deixar 8 candidats quantitativament positius. Abans d'obrir
el holdout es van congelar tres finalistes compatibles amb close-only:

- `calendar long 0.14`: primer dia negociable del mes, stop 2,1%, target 3,9×ATR20.
  Holdout: 29 trades, PF brut 2,03, retorn 45,4%, DD 15,6%. Amb 36 bps: PF 1,66,
  retorn 31,1%.
- `calendar long 0.77`: primer dia de mes amb confirmació de tancament, stop
  2,8×ATR30 i target 4,1×ATR20. Holdout: només 12 trades; PF estrès 1,41.
- `trend long 0.14`: compra després de tres tancaments descendents, stop
  2,6×ATR30 i target 4,6×ATR25. El PF cau a 1,12 en holdout amb estrès.

El primer semblava el millor candidat de recerca, però la falsificació posterior
el rebutja com a **timing edge**. Amb 36 bps, 500 calendaris aleatoris que també
intenten una entrada per mes obtenen una mediana superior en validació (37,38%
contra 26,51%; p empírica 0,617). Tampoc és significatiu en OOS (p 0,295) ni en
holdout (p 0,186). Les 27 pertorbacions ±10% de stop/target sí que passen els
gates: els paràmetres són estables, però això no demostra que el primer dia de
mes aporti informació respecte a estar long MSFT en un dia mensual qualsevol.

El leverage preliminar de 21× tampoc supera la història completa: el llindar de
liquidació proxy és 4,76% i hi ha un gap de 4,94% durant validació, a més d'un
11,12% a train. El primer nivell de la graella sense gaps històrics més grans que
el llindar proxy és 8× (12,5%), encara sense certificar contra l'oracle d'Ostium.

Decisió final de la família: `REJECT_CALENDAR_TIMING_EDGE_KEEP_LONG_DRIFT_REFERENCE`.
No s'integra al paper bot i no es retoca després del holdout. Amb 200 USDC i risc
màxim de l'1%, el nocional teòric continuava limitat a ~81,30 USDC; el leverage
només canviava el marge, no aquest risc. Artifacts canònics: `msft_source_parity.json`,
`msft_finalists_holdout.json`, `msft_final_gate.json`,
`msft_calendar_014_robustness.json` i `msft_calendar_014_gap_risk.json`.

## Revisió de famílies famoses (2026-08-02)

S'han contrastat time-series momentum, volatility management, overnight equity,
opening-range breakout i reversió curta amb evidència publicada i amb les nostres
campanyes. Dos experiments nous usen exclusivament Dukascopy local:

- TSMOM EURUSD+XAUUSD: el lookback 126d és positiu brut en validació i OOS,
  però fins i tot el carry base conservador del 4% el torna negatiu. Holdout segellat.
- ORB XAU 08:20 NY: 15/30/60 minuts; totes perden abans de costos d'estrès.
  Millor OOS PF base 0,805 sobre 1.215 trades. Holdout segellat.

No hi ha nova candidata. `capitulation_d1` continua sent l'única família amb
evidència pròpia repetida i es manté només en paper. Revisió completa:
[`STRATEGY_EVIDENCE_REVIEW_2026.md`](STRATEGY_EVIDENCE_REVIEW_2026.md).

### Capitulació confirmada close-only v1

S'ha preregistrat una prova diferent del senyal productiu: caiguda diària
normalitzada per volatilitat, recuperació observable del 25% o 50%, entrada al
tancament de confirmació i sortida després d'1–3 dies. La graella conté 36
variants per actiu sobre MSFT, NVDA i QQQ; train 2004–2013, validació 2014–2018,
OOS 2019–2023 i holdout 2024–2026 segellat.

Cap actiu passa. MSFT falla validació (PF base 0,82; p contra timing aleatori
0,832), NVDA passa de PF 2,09 al train a 0,35/0,75 fora de train, i QQQ és
negatiu en els tres trams. Decisió:
`REJECT_HOLDOUT_REMAINS_SEALED`. No es tuneja, no passa a SQ i no modifica
`capitulation_d1`. Metodologia, runner i resultat:
`methodology_confirmed_capitulation_v1.json`,
`confirmed_capitulation_campaign.py` i
`confirmed_capitulation_v1_decision.json`.

### Anatomia del `capitulation_d1` congelat

L'auditoria preserva la regla productiva exacta: senyal al close de T, entrada
a l'open de T+1 i sortida al close de T+1. Amb 15 bps conservadors, MSFT dona
74 trades, PF 2,98 i EV +91,3 bps; NVDA 144, PF 1,82 i +70,4 bps; QQQ 83,
PF 2,00 i +49,5 bps. Els p empírics contra dies aleatoris aparellats per any
són 0,0002, 0,0004 i 0,0002. L'edge és intradia: el gap previ no explica el
retorn operat. QQQ és negatiu el 2003–2013 i continua sent només proxy.

La història ampliada invalida el cap global antic de 20x. La pitjor MAE
observada és 5,57% MSFT, 12,75% NVDA i 10,07% QQQ. A 20x, el proxy hauria
liquidat 2,70%, 7,64% i 2,41% dels trades. Amb buffer del 25%, els nous caps
de **paper** són MSFT 10x i NVDA/NDXUSD 5x; fallback 5x. El nocional continua
limitat independentment pel tram vigent del glidepath i marge màxim 35%. Cal certificar open/low
contra Ostium abans de considerar aquests caps per live.

El paper executor aplica aquesta separació de forma explícita a les noves
operacions: pressupost de risc segons capital, stop diagnòstic per actiu, nocional
`risc/stop` i collateral `nocional/leverage`. Si el low diari travessa el stop,
registra `stop_settled`. No hi havia trades pendents durant la migració i no
s'ha reescrit cap operació històrica.

Amb el stop aplicat i 200 USDC, MSFT conserva EV de +0,351 USDC/trade en
conservador i +0,288 en estrès; NVDA +0,212 i +0,169. QQQ baixa a +0,126 i
+0,069, respectivament. Per això el paper actiu per defecte queda en
`MSFT,NVDA`; NDXUSD continua watchlist fins que la paritat nativa i l'economia
d'estrès siguin suficients. Els costos per defecte nous són 8/15/30 bps.

#### Resultat combinat MSFT + NVDA amb 200 USDC

Les 218 operacions s'han ordenat cronològicament; senyals simultanis comparteixen
el capital inicial del dia i no fan compounding artificial entre ells. Període:
23,05 anys, aproximadament 9,46 trades/any.

| Cost | Guany amb risc fix 2 USDC | Capital final fix | Guany compounding 1% | Capital final | CAGR |
|---|---:|---:|---:|---:|---:|
| Base 8 bps | 61,54 | 261,54 | 71,14 | 271,14 | 1,33% |
| Conservador 15 bps | 56,49 | 256,49 | 64,39 | 264,39 | 1,22% |
| Estrès 30 bps | 45,65 | 245,65 | 50,47 | 250,47 | 0,98% |

Aquests són resultats històrics, no una projecció. El compounding és limitat
per la baixa freqüència i el risc 1%. L'antic 250→772 a 20x no és comparable:
assumia una exposició molt superior i zero liquidacions, hipòtesi invalidada
per la història ampliada.

#### Risk glidepath

El paper aplica risc decreixent per capital: <400 USDC 1,5%; 400–999 1,25%;
1.000–2.499 1%; 2.500–4.999 0,75%; ≥5.000 0,5%. El leverage no augmenta el
pressupost de risc; només redueix el collateral necessari dins els caps per
actiu.

Simulació cronològica MSFT+NVDA des de 200 USDC: base 314,91, conservador
303,23 i estrès 279,62. Drawdown màxim conservador 4,67%. En 23,05 anys cap
escenari arriba al primer llindar de 400 USDC; per tant, el glidepath és una
infraestructura correcta però no resol la baixa freqüència. Calen estratègies
independents addicionals, no més risc sobre el mateix edge.

### EURUSD intradia v2 — sessions DST

Pilot Dukascopy de 549.497 candles M15 (2004-01-01–2026-02-27), sessions
Europe/London i America/New_York amb DST. Es van congelar 10 variants
representatives de breakout del rang asiàtic, continuació d'expansió i reversió
d'expansió; long/short, entrada posterior al senyal, stop/target i tancament
intradia. Train 2004–2013, validació 2014–2018, OOS 2019–2023; holdout segellat.

Cap família s'apropa al gate fins i tot amb 8 bps: breakout PF 0,31/0,22 en
validació/OOS; continuació 0,11/0,06; reversió 0,07/0,06. Tenen 593–684 trades
OOS, de manera que no és falta de mostra. Decisió `REJECT_NO_SQCLI`: SQ no
optimitza una família sense edge brut/base. Runner ~49 s amb cache de sessions.

Artifacts: `methodology_eurusd_intraday_v2.json`, `eurusd_intraday_v2.py` i
`eurusd_intraday_v2_decision.json`.

Artifacts: `methodology_capitulation_anatomy_v1.json`,
`capitulation_anatomy.py` i `capitulation_anatomy_v1.json`.

## Campanya XAUUSD H4 (2026-08-02)

La incidència del Retest queda resolta: cal partir d'un projecte Retest **H4**
que SQ 143 ja hagi executat, conservar-ne el contracte i empeltar-hi només el
recurs XAU, símbol, dates i costos. El pilot nadiu va retestar `0.7893` en
0,83 s; no era un bloqueig del motor.

S'han validat els 8 representants estructurals de les 60 estratègies descobertes,
en el tram segellat 2015-02-07–2019-07-16, H4, slippage SQ 300 i risc 1%.
Resultat: **0/8 passen**. Els menys dolents són `0.106720` (PF 1,06), `0.34159`
(PF 1,05) i `0.7893` (PF 1,04), tots per sota del gate PF 1,15. `0.91375`
guanya 343,19 amb 41 trades però falla el filtre automàtic de mostra; la resta
inclou pèrdues o altres filtres automàtics. No s'ha obert el holdout.

Decisió: aquesta shortlist no avança a OOS, Monte Carlo, traducció Python ni
Ostium. Les 60 originals es conserven com a univers congelat/evidència de biaix
de selecció. Artifact canònic:
`lab/out/alquimia/xau_h4_native_shortlist_validation_inventory.json`.

### Nova família stop-channel breakout R2

Hipòtesi dirigida: ordres stop sobre màxim/mínim recent, sortides ATR i com a
màxim un filtre ADX/ATR/ROC. Random va generar 63 intents i va omplir 40 places;
10/40 van passar validació i 4/10 OOS. Amb slippage duplicat (800 unitats SQ),
`0.26`, `0.33` i `0.37` continuen passant. Els tres també passen Monte Carlo
exclusiu de paràmetres: 1.000 simulacions per candidat i 3.003 membres executats
verificats dins els SQX.

El gate posterior confirma que `0.37` és estable per anys (5/5 OOS positius),
no concentra el benefici i no simula liquidacions a 20x (MAE màxim 3,97%). Però
l'economia de 200 USDC falla: a risc 1% l'EV és 0,035 USDC base i 0,019 en estrès;
a risc 3% només passa base i falla conservador/estrès. El funding encara no s'ha
deduït i només ho empitjoraria.

Estat final de la família: `REJECT_FOR_200_USDC_KEEP_RESEARCH_REFERENCE`.
No s'obre holdout ni es consumeix feina de traducció/paritat. El holdout continua
intacte. Resum:
`lab/out/alquimia/xau_h4_stop_breakout_r2_gate_summary.json`.

### Compressió ATR + breakout R3

Nova hipòtesi posterior a R2: exigir ATR decreixent abans de l'entrada stop.
5/40 passen validació, 2/5 OOS i només `0.74` passa slippage 2×. Falla després:
2/5 anys OOS positius i, amb 200 USDC/risc 1%, PnL de +4,17 base i +0,29 estrès
en 130 trades. El cap preliminar arriba a 30x, però el nocional queda limitat pel
risc i l'EV estrès és només 0,0022 USDC/trade.

Decisió: `REJECT_TEMPORAL_AND_SMALL_ACCOUNT_FAIL`; no MC, no holdout, no Python.

### Sweep + reclaim nadiu v4–v5 (2026-08-03)

V4 és la primera campanya sota `alquimia-v3-native-evidence-chain`: cap pipeline
quantitativa antiga, Builder nou i gate sobre l'AST real. SQCLI va generar prop
de 4.000 estratègies i en va acceptar 20, però **0/20** implementaven exactament
el mateix extrem per al sweep i el reclaim. Això prova que una allowlist de blocs
no basta per generar una hipòtesi coordinada.

V5 fixa l'entrada long/short en un SQX nadiu i deixa optimitzables només lookback,
ATR i sortides. El Retester es va reparar eliminant la selecció TSLA residual;
el smoke SQ real acaba en 6,01 s, conserva l'AST i produeix 1.180 trades, amb
−1.037,71 de benefici train. Abans de llançar 5.000 optimitzacions, una malla
DuckDB sobre 18.448 H4 Dukascopy prova 1.350 punts i costos 8/12/20 bps més
funding 4/8/12% anual. Resultat: 0 PASS d'estrès i 0 regions estables.

El millor long (lookback 60, 12 barres, ATR14, stop/target 3×ATR) té 221 trades,
PF 1,149 i +17,88% base, però PF 0,878 i −18,51% en estrès. No té cap trade amb
ordre intrabar ambigu; M1 no pot rescatar aquest deteriorament. Short i combinada
ja són negatives en base. Decisió terminal `REJECT_FAMILY_V5`; validation, OOS i
holdout continuen segellats. L'Optimizer existeix però deliberadament no s'executa.

## Pilot anterior

- `TA_SQ_PILOT`, original `NVIDIA` intacte.
- NVDA/USD confirmat a Ostium.
- `NVDAUSUSD_TICK_UTCMinus05`, M1, 147.024.593 ticks.
- Límit 20; manifest/hashes; límits 6 CPU/14 GB; una campanya.
- Watchdog: stop a 1.000 generades/0 acceptades, RAM host <1 GB o disc <2 GB.
- Generació correcta, sense errors tècnics; acceptació inicial 0%.

Proper gate: acabar o diagnosticar `ZERO_ACCEPTANCE`, exportar databank, construir
col·lector i paritat DuckDB/BS. Cap pas automàtic a paper/live.
