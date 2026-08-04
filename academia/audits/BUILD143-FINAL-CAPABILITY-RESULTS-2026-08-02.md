# Resultat de les tres capacitats finals — SQX 143.2708

## Estat útil

- **Monte Carlo de paràmetres: provat.** El candidat `4.1.133` es va retestar amb 50 simulacions exclusivament de paràmetres. L'SQX resultant conté 152 membres Monte Carlo executats; no és una simple configuració XML.
- **Builder random vs genetic: microprova executada, comparació rebutjada.** El Task Manager exposa els intents reals com `projectStats.totalJobsDone` (`Strategies generated`). Les calibracions amb `stop` van acabar en 2.241 i 4.822 intents. Amb `pause`, la microprova final va produir Genetic 100/0 acceptades i Random 105/2. El pressupost no és igual i Genetic no té distribució de supervivents: no hi ha guanyador.
- **Export/paritat: costat SQ provat, paritat pendent.** SQCLI va exportar 130 ordres del resultat a CSV. No hi ha exportació de codi font a SQCLI 143 ni ordres d'un motor objectiu escollit; per tant, la paritat es rebutja correctament en comptes de declarar-la per compilació o semblança visual.
- **Improver exit-only: capacitat provada el 2026-08-03.** Una base verificada va produir 178 variants en 2m11s i un SQX desat. Entrada, direcció i mida es van preservar; les sortides van canviar. El supervivent no es promociona: només té IS i la sortida de regla incorpora una branca `AND false` sospitosa.
- **Improver entry-only: capacitat provada el 2026-08-04, sense supervivents.** Amb ordre i exits congelats es van generar 302 variants: 180 amb massa pocs trades, 72 sense trades i 50 rebutjades pels gates quantitatius. No es relaxen filtres després del resultat.

## Aprenentatge operatiu

1. En aquest build, `startOnlyTask task=1` va acabar sense executar l'única tasca del projecte; `action=start` sí que va executar el retest. Cal comprovar activitat real al log i a l'artifacte.
2. `MonteCarloRetest use=true` no basta si `CrossChecks use=false`. Els dos interruptors han d'estar actius.
3. Una prova de robustesa passa només quan l'SQX conté resultats executats. L'auditor local va comptar 152 membres Monte Carlo.
4. La comparació random/genetic necessita el mateix recurs causal. Temps igual, supervivents iguals i intents iguals són experiments diferents.
5. La paritat multiplataforma necessita dues sèries d'ordres. Les 130 ordres SQ són la referència, no la conclusió.
6. Per igualar intents cal projecte Build d'una sola tasca, comptador explícit i control més fi (`pause` o CPU reduïda). La GUI serveix per observar; no és un rellotge de precisió.
7. SQ 143 va imposar un mínim efectiu de 100 intents Genetic encara que el CFX declarava població 15 i tres generacions. Cal creure el comptador executat, no l'aritmètica configurada.
8. Desactivar els filtres per forçar supervivents va deixar entrar un candidat amb benefici −498,10. El Databank és una selecció definida pels gates, no una mesura autònoma de qualitat.
9. El runtime aïllat necessita `SQ_LICENSE` i el `machine-id` de la llicència en només lectura. Sense aquesta identitat arrenca una trial expirada encara que els fitxers SQ siguin els mateixos.
10. El resolutor de projectes llegeix dates dels `Resources/Symbol`, i també pot exposar referències de cross-check inactives. Veure el `.dat` al disc no basta si el `data.db` efímer no registra el símbol.
11. Improver sobre tot un Databank rebutja `databank-full`; a Build 143 la microprova finita va requerir `time-limit` i una candidata real al Databank d'entrada.
12. Restringir `PartsToImprove` és necessari però no suficient: cal comparar semànticament entrada/ordres i rebutjar sortides degenerades encara que SQ les accepti.
13. Zero supervivents també és informació: en entry-only, el patró dominant va ser destruir la freqüència de trading. Ampliar blocs o abaixar gates per salvar la base seria una campanya nova, no continuació neutral.

## Decisió de cobertura

La cobertura funcional continua en **12/14 capacitats completament provades**, però `improver_exit_only` passa de pendent a provat dins `builder-improver`. El paquet continua `operational` perquè la comparació random/genetic amb pressupost igual encara no compleix el contracte. `export-crossplatform` també continua operativa.

Els SQX, CSV complet i runtime continuen ignorats sota `academia/runtime/`. L'evidència versionada conserva hashes, recomptes, configuració i conclusions transformadores a `experiments/observations/build143-final-capability-tests-2026-08.json`.
