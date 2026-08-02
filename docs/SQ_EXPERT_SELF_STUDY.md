# Autoaprenentatge StrategyQuant per a Alquímia

Estat: curs viu, iniciat el 2026-08-02. Versió objectiu de laboratori: SQX
143.2708. Aquest document no promet rendibilitat: defineix com aprendre a formular,
automatitzar i falsar estratègies abans d'arriscar capital.

## Principis

1. Una corba atractiva és una hipòtesi, no evidència suficient.
2. El holdout no es consulta ni s'usa per decidir fins al gate final.
3. Tot intent compta en el pressupost de cerca; no només els guanyadors.
4. Els costos, el contracte, la mida mínima i la liquidació formen part del model.
5. Una opció de SQ només es considera dominada quan ha estat verificada a la versió
   instal·lada mitjançant XML, log i resultat reproduïble.
6. Fonts comercials i vídeos aporten hipòtesis; mai substitueixen una prova.

## Jerarquia de fonts

- **A — primària:** manual actual, documentació i comportament observat de SQX;
  papers originals dels mètodes estadístics.
- **B — secundària competent:** autors reconeguts i usuaris que mostren procés,
  configuració, fracassos i resultats verificables.
- **C — exploratòria:** fòrums, cursos comercials, YouTube i xarxes. Només serveixen
  per generar experiments.
- **D — rebutjada com a evidència:** promeses de guany fàcil, captures sense
  configuració, backtests sense OOS/costos o afirmacions sense comptar intents.

## Itinerari

### Mòdul 1 — Mapa de SQX i formats

Aprendre Builder, Retester, Optimizer, AlgoWizard, Databanks, Custom Projects,
SQX/CFX, recursos de símbol i SQCLI.

Laboratori:

- Crear un projecte mínim per cada mòdul.
- Inspeccionar `config.xml`, task XML, `strategy_Portfolio.xml`, `settings.xml`,
  `orders.bin` i manifests.
- Gate: generar, retestar i exportar una estratègia trivial sense GUI i amb hash
  reproduïble.

### Mòdul 2 — Dades i motor d'execució

Aprendre timezone/DST, sessions, timeframe, precisió, spread, slippage, comissions,
swap/rollover, point value, multiplicador i seqüència intrabar.

Laboratori:

- Comparar candles SQ amb BrokerageService/DuckDB.
- Repetir el mateix backtest a precisió ràpida i superior.
- Gate: informe de cobertura i paritat; cap símbol sense recurs exacte.

### Mòdul 3 — Arquitectura d'estratègies

Estudiar simetria long/short, nombre de condicions, graus de llibertat, indicadors,
shifts, ordres, SL/TP ATR, exits i regles horàries.

Laboratori:

- Construir famílies simples i interpretables.
- Mesurar com creix l'espai de cerca en afegir blocs i paràmetres.
- Gate: AST traduïble a Python abans de promocionar una família.

### Mòdul 4 — Generació aleatòria

SQ descriu la generació aleatòria com la base del Builder: combina blocs vàlids i
backtesta cada estructura. S'usa per diversitat i com a baseline contra l'evolució.

Laboratori:

- Executar llavors/campanyes independents amb el mateix preregistre.
- Registrar candidats provats, taxa d'acceptació i diversitat estructural.
- Gate: cap conclusió basada només en el millor candidat.

### Mòdul 5 — Evolució genètica

Aprendre població, illes, migració, decimació, fresh blood, elitisme, mutació,
creuament, estancament i reinicis. La documentació recomana que el filtre de la
població inicial sigui poc estricte, habitualment només activitat/nombre de trades.

Laboratori preregistrat:

- Comparar random vs genetic amb el mateix mercat, blocs, pressupost de backtests
  i dades.
- Provar 4 illes, migració moderada i reinici per estancament sense tocar el holdout.
- Gate: millora OOS i de diversitat, no només fitness IS.

### Mòdul 6 — Ranking i selecció

Separar condicions d'admissió, fitness i capacitat del databank. No usar benefici
absolut dependent de lots com a definició d'edge. Prioritzar mètriques normalitzades,
trades suficients, estabilitat i complexitat baixa.

Laboratori:

- Comparar Return/DD, PF, R-expectancy i una puntuació cost-aware.
- Auditar duplicats i estratègies massa similars.
- Gate: selecció reproduïble i invariant al capital nominal.

### Mòdul 7 — Validació temporal

Fer train, validation, OOS i holdout segellat cronològics. El nostre flux és més
conservador que l'OOS intern del Builder perquè cap període usat per seleccionar es
torna a etiquetar com a prova final.

Laboratori:

- Mesurar degradació de PF i esperança entre finestres.
- Rebutjar estratègies que depenguin d'un únic règim o any.
- Gate: llindars preregistrats; prohibit relaxar-los després de veure el resultat.

### Mòdul 8 — Robustesa

Ordre econòmic de proves:

1. higher precision;
2. manipulació Monte Carlo d'operacions (ordre i operacions omeses);
3. estrès de spread, slippage i història;
4. pertorbació de paràmetres;
5. mercats/timeframes addicionals quan la hipòtesi ho justifiqui;
6. Optimization Profile i System Parameter Permutation;
7. Walk-Forward i Walk-Forward Matrix quan l'estratègia requereixi reoptimització.

No confondre tests: reordenar trades estudia drawdown/seqüència, però no demostra
edge futur; WFA positiva també pot aparèixer per atzar; multi-market pot ser inadequat
per una hipòtesi específica. Es busca una zona estable, no un pic.

### Mòdul 9 — Control del data mining

Registrar el nombre total d'estratègies i variants examinades. Estudiar Deflated
Sharpe Ratio, Probability of Backtest Overfitting i SPP. DSR corregeix biaix de
selecció, no-normalitat i múltiples proves; no substitueix validació temporal.

Gate: cap promoció sense un ledger d'intents i una estimació explícita del biaix de
selecció.

### Mòdul 10 — Paritat SQ → Python

Adoptar la màquina d'estats útil de SQRunner:

`DATA_READY → ORACLE_READY → INDICATOR_PASS → SIGNAL_PASS → EXECUTION_PASS → TRADES_PASS`

Millores d'Alquímia:

- oracle oficial exportat per SQCLI abans que parser heurístic d'`orders.bin`;
- toleràncies per instrument/tick, no hardcodejades per EURUSD;
- AST genèric per SMA, EMA, RSI, ATR, ADX, preus, comparadors i exits;
- hashes i artifacts JSON per cada gate.

### Mòdul 11 — Economia Ostium amb 200 USDC

Afegir `OSTIUM_ECONOMICS_PASS`: parell existent, fee, oracle, rollover, bid/ask,
mida mínima, precisió, notional, marge, MAE, stop i liquidació. El leverage és una
restricció de marge, no una font d'edge. S'escull el màxim que encara compleixi els
gates de risc i liquidació.

Escenaris obligatoris: base, conservador i estrès. Gate: EV net positiu i
distribució Monte Carlo acceptable amb la mida real executable.

### Mòdul 12 — Paper i promoció

Executar paper trading amb la mateixa font de dades, timestamps, sizing i costos.
Comparar expectativa SQ/Python amb fills observats. `LIVE_READY` requereix mostra
suficient, paritat vigent i safeguards; sis operacions no són confirmació.

## Fonts inicials auditades

### Oficials StrategyQuant

- [Manual SQX actual (PDF)](https://1859438673.rsc.cdn77.org/ninstall/sq4/StrategyQuantX_Help.pdf)
- [Com funciona SQ: random i genetic](https://strategyquant.com/doc/strategyquant/how-does-strategyquant-work/)
- [Modes de generació](https://strategyquant.com/doc/strategyquant/different-build-modes/)
- [Opcions genètiques](https://strategyquant.com/doc/strategyquant/genetic-options/)
- [Workflow recomanat](https://strategyquant.com/doc/strategyquant/workflow/)
- [Ranking](https://strategyquant.com/doc/strategyquant/ranking-options/)
- [Cross-checks](https://strategyquant.com/doc/strategyquant/cross-checks-automated-strategy-robustness-tests/)
- [Tipus de tests de robustesa](https://strategyquant.com/doc/strategyquant/types-of-robustness-tests-in-sqx/)
- [Walk-Forward Matrix](https://strategyquant.com/doc/strategyquant/walk-forward-matrix/)
- [Optimization Profile i SPP](https://strategyquant.com/doc/strategyquant/optimization-profile-system-parameter-permutation-strategyquant/)
- [Custom Projects](https://strategyquant.com/doc/strategyquant/introduction-to-custom-projects/)
- [Backtest programàtic i robustesa](https://strategyquant.com/doc/programming-for-sq/backtesting-strategy-programmatically-including-robustness-tests/)

### Fonts primàries quantitatives

- [Bailey i López de Prado — Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
- [Dave Walton — System Parameter Permutation](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2423187)
- Robert Pardo, *The Evaluation and Optimization of Trading Strategies*, 2a ed.

### Vídeo i pràctica externa: ús crític

- [Ali Casey / StatOasis — Genetic Algorithm en SQX](https://www.youtube.com/watch?v=0iyMzOhkyps):
  útil per visualitzar illes, fresh blood i gestió d'evolució; tota configuració es
  verificarà contra manual i experiments locals.
- Trivium Systems Trading: hipòtesis sobre workflow i selecció; les afirmacions de
  track record o hores d'experiència no es tracten com a prova metodològica.
- Vídeos centrats en “passar fondeig”, rendibilitat fàcil o presets universals:
  prioritat baixa; només s'extreuen idees falsables.

## Conclusions pròpies inicials

1. Random i genetic són exploradors; cap dels dos valida edge.
2. Fer cross-checks cars dins del Builder pot malgastar CPU i introduir selecció
   opaca. És preferible un embut: descobriment barat, retests explícits i artifacts.
3. El WFM és apropiat si es pretén reoptimitzar en producció. Per una estratègia de
   paràmetres fixos és una diagnosi, no una obligació universal.
4. SPP és més informatiu amb pocs graus de llibertat i cobertura àmplia de l'espai;
   amb milions de combinacions i una mostra petita pot donar falsa confiança.
5. Multi-market no ha de premiar una estratègia genèrica a costa de destruir una
   hipòtesi específica; els mercats de prova s'han de preregistrar per relació causal.
6. Per 200 USDC, el filtre de costos ha d'entrar abans que les proves més cares:
   una estratègia robusta però econòmicament inviable no és candidata.

## Evidència de domini

El curs es considerarà superat quan Alquímia pugui, sense GUI:

- generar campanyes random i genetic verificades;
- inspeccionar progrés i errors;
- executar tot l'embut de robustesa amb holdout segellat;
- traduir almenys una estratègia no trivial a Python;
- obtenir paritat trade a trade amb SQ;
- demostrar o rebutjar viabilitat neta per 200 USDC a Ostium;
- produir un dossier reproduïble que inclogui també tots els fracassos.
