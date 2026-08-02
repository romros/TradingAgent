# Dades, hipòtesi i Builder

Llegir `academia/courses/strategyquant/01-DATA-HYPOTHESIS-BUILDER.md` quan es
dissenyi o diagnostiqui una generació.

Abans d'iniciar Builder, exigir dades versionades, holdout intacte, mecanisme i
falsador, arquitectura justificada, blocs limitats i pressupost total d'intents.
Comptar decimation, poblacions, illes i reinicis. Databank és selecció truncada,
no recompte d'intents. Si l'usuari proposa més blocs o còmput, demanar quina part
de la hipòtesi ho necessita; si no n'hi ha, simplificar.

En SQX 143, el Task Manager mostra el recompte real com
`projectStats.totalJobsDone` (`Strategies generated`). Fer servir un projecte
descartable d'una sola tasca Build perquè el comptador sigui inequívoc. No
inferir mai els intents a partir del Databank. Abans de comparar Random i
Genetic, exportar dos manifests amb `attempted` idèntic i validar-los amb
`academia/tools/compare_builder_runs.py --contract equal_attempts`. Si `stop`
deixa drenar treballadors i sobrepassa el límit, la passada és calibratge, no
evidència comparativa; reduir CPU o provar `pause` abans de repetir.
