# Resultat de les tres capacitats finals — SQX 143.2708

## Estat útil

- **Monte Carlo de paràmetres: provat.** El candidat `4.1.133` es va retestar amb 50 simulacions exclusivament de paràmetres. L'SQX resultant conté 152 membres Monte Carlo executats; no és una simple configuració XML.
- **Builder random vs genetic: comptador descobert, comparació encara rebutjada.** El Task Manager exposa els intents reals com `projectStats.totalJobsDone` (`Strategies generated`). Amb dos CPU, però, el mostreig visual i `stop` tenen prou latència perquè els treballadors superin molt el límit: les calibracions van acabar en 2.241 i 4.822 intents. No es falseja una igualtat de 2.000 que no ha existit.
- **Export/paritat: costat SQ provat, paritat pendent.** SQCLI va exportar 130 ordres del resultat a CSV. No hi ha exportació de codi font a SQCLI 143 ni ordres d'un motor objectiu escollit; per tant, la paritat es rebutja correctament en comptes de declarar-la per compilació o semblança visual.

## Aprenentatge operatiu

1. En aquest build, `startOnlyTask task=1` va acabar sense executar l'única tasca del projecte; `action=start` sí que va executar el retest. Cal comprovar activitat real al log i a l'artifacte.
2. `MonteCarloRetest use=true` no basta si `CrossChecks use=false`. Els dos interruptors han d'estar actius.
3. Una prova de robustesa passa només quan l'SQX conté resultats executats. L'auditor local va comptar 152 membres Monte Carlo.
4. La comparació random/genetic necessita el mateix recurs causal. Temps igual, supervivents iguals i intents iguals són experiments diferents.
5. La paritat multiplataforma necessita dues sèries d'ordres. Les 130 ordres SQ són la referència, no la conclusió.
6. Per igualar intents cal projecte Build d'una sola tasca, comptador explícit i control més fi (`pause` o CPU reduïda). La GUI serveix per observar; no és un rellotge de precisió.

## Decisió de cobertura

La cobertura queda en **12/14 capacitats provades**. `builder-improver` i `export-crossplatform` continuen operatives perquè els seus resultats finals encara no compleixen el contracte. Aquesta és una limitació explícita i accionable, no treball pendent ocult.

Els SQX, CSV complet i runtime continuen ignorats sota `academia/runtime/`. L'evidència versionada conserva hashes, recomptes, configuració i conclusions transformadores a `experiments/observations/build143-final-capability-tests-2026-08.json`.
