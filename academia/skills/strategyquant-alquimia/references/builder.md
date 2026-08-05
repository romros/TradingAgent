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

## De la sèrie històrica al venue actual

Separar quatre papers de les dades abans de donar llum verda a Builder:

1. `discovery`: història llarga per generar, sense holdout;
2. `validation`: període no usat per generar;
3. `venue_overlap`: solapament amb el feed actual per mesurar basis, sessions,
   gaps, spread i transformacions;
4. `sealed_holdout`: una sola avaluació dels finalistes.

No exigir que una sola font faci els quatre papers. Sí exigir símbol, timezone,
OHLC, política d'ajustos, cobertura, gaps, hash i provenance per a cada tram.
Una sèrie del subjacent anterior a l'alta del parell al venue és un proxy: serveix
per estudiar el mecanisme però no prova execució històrica real. Comparar-la amb
el venue durant el solapament i rebutjar-la si les diferències canvien senyals o
economia.

Per campanyes Ostium, executar primer `academia/tools/audit_portfolio_data.py` i,
si cal refrescar cobertura oficial, `academia/tools/probe_ostium_ohlc.py`. No
persistir espelmes en Git. No obrir SQ perquè un endpoint respongui: el gate exigeix
la finestra requerida i camps compatibles. Bloquejos, 429 i murs anti-bot fan el
proveïdor no operatiu; no autoritzen evasió amb navegador.

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
