# Dades, hipòtesi i Builder

Llegir `academia/courses/strategyquant/01-DATA-HYPOTHESIS-BUILDER.md` quan es
dissenyi o diagnostiqui una generació.

Abans d'iniciar Builder, exigir dades versionades, holdout intacte, mecanisme i
falsador, arquitectura justificada, blocs limitats i pressupost total d'intents.
Comptar decimation, poblacions, illes i reinicis. Databank és selecció truncada,
no recompte d'intents. Si l'usuari proposa més blocs o còmput, demanar quina part
de la hipòtesi ho necessita; si no n'hi ha, simplificar.

No tractar una allowlist com una obligació estructural. Si el mecanisme requereix
blocs o tipus d'ordre concrets, imposar-los amb template/accions i auditar tots
els `.sqx` supervivents. Informar cobertura `artifacts conformes / artifacts
inspeccionats`; si és incompleta, la campanya no ha provat la hipòtesi declarada.

En SQX 143, el Task Manager mostra el recompte real com
`projectStats.totalJobsDone` (`Strategies generated`). Fer servir un projecte
descartable d'una sola tasca Build perquè el comptador sigui inequívoc. No
inferir mai els intents a partir del Databank. Abans de comparar Random i
Genetic, exportar dos manifests amb `attempted` idèntic i validar-los amb
`academia/tools/compare_builder_runs.py --contract equal_attempts`. Si `stop`
deixa drenar treballadors i sobrepassa el límit, la passada és calibratge, no
evidència comparativa; reduir CPU o provar `pause` abans de repetir.

No assumir que `PopulationSize × MaxGenerations` és el recompte executat: al
build 143 una configuració Genetic 15×3 va executar un mínim efectiu de 100.
Tampoc desactivar els gates per «obtenir mostra»: en la prova local això va
acceptar un candidat de benefici negatiu. Si un mètode no produeix prou
supervivents sota filtres útils, el resultat és inconcloent, no una invitació a
canviar els filtres després de veure'l.

Separar manifest, projecte configurat i execució observada. Un `attempt_budget`
al manifest expressa intenció; només és un límit real si el controlador/stop i
el comptador executat ho confirmen. Registrar també la causa de finalització
(pressupost, Databank ple, temps o intervenció).

## Improver

Tractar cada variant millorada com una nova hipòtesi seleccionada. Exigir hash de
la base, una part modificable explícita, blocs i complexitat limitats, pressupost
de variants i criteri de millora preregistrat. La base és el control. Una variant
només avança si supera el criteri en dades no usades per escollir-la i torna a
passar precisió, costos i robustesa. No obrir parts noves per rescatar una passada
fallida.
