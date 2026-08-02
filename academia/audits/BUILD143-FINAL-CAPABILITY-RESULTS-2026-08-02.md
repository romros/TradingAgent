# Resultat de les tres capacitats finals — SQX 143.2708

## Estat útil

- **Monte Carlo de paràmetres: provat.** El candidat `4.1.133` es va retestar amb 50 simulacions exclusivament de paràmetres. L'SQX resultant conté 152 membres Monte Carlo executats; no és una simple configuració XML.
- **Builder random vs genetic: contracte provat, comparació rebutjada.** Builder va carregar EURUSD H4, va completar el test inicial i va començar a generar amb dos CPU. SQX 143 permet fixar `PopulationSize × MaxGenerations` per genetic, però random no exposa un límit equivalent sobre intents totals. Comparar només supervivents o aturar arbitràriament a temps igual no respon la pregunta original de 2.000 intents iguals.
- **Export/paritat: costat SQ provat, paritat pendent.** SQCLI va exportar 130 ordres del resultat a CSV. No hi ha exportació de codi font a SQCLI 143 ni ordres d'un motor objectiu escollit; per tant, la paritat es rebutja correctament en comptes de declarar-la per compilació o semblança visual.

## Aprenentatge operatiu

1. En aquest build, `startOnlyTask task=1` va acabar sense executar l'única tasca del projecte; `action=start` sí que va executar el retest. Cal comprovar activitat real al log i a l'artifacte.
2. `MonteCarloRetest use=true` no basta si `CrossChecks use=false`. Els dos interruptors han d'estar actius.
3. Una prova de robustesa passa només quan l'SQX conté resultats executats. L'auditor local va comptar 152 membres Monte Carlo.
4. La comparació random/genetic necessita el mateix recurs causal. Temps igual, supervivents iguals i intents iguals són experiments diferents.
5. La paritat multiplataforma necessita dues sèries d'ordres. Les 130 ordres SQ són la referència, no la conclusió.

## Decisió de cobertura

La cobertura queda en **12/14 capacitats provades**. `builder-improver` i `export-crossplatform` continuen operatives perquè els seus resultats finals encara no compleixen el contracte. Aquesta és una limitació explícita i accionable, no treball pendent ocult.

Els SQX, CSV complet i runtime continuen ignorats sota `academia/runtime/`. L'evidència versionada conserva hashes, recomptes, configuració i conclusions transformadores a `experiments/observations/build143-final-capability-tests-2026-08.json`.
