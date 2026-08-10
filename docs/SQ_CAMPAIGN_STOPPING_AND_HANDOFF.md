# SQCLI — política d'aturada, estancament i handoff

**Data:** 2026-08-02
**Estat:** controlador mínim implementat; no canviar campanyes històriques actives

## Objectiu

Evitar perdre hores perquè SQCLI falla sense checkpoints i evitar cercar
indefinidament fins obtenir un backtest afortunat. La política separa salut
operativa, progrés de cerca i valor científic. Consumir CPU no demostra progrés i
augmentar el databank no demostra diversitat.

## Regla preregistrada per a campanyes noves

Abans d'iniciar SQ, desar al manifest quatre límits. La campanya acaba quan es
compleix el primer:

1. `accepted_target`: candidats acceptats.
2. `attempt_budget`: estratègies totals generades/provades.
3. `wall_time_budget`: temps màxim de paret i CPU assignada.
4. `stagnation_policy`: absència anormal de candidats o famílies noves.

No modificar aquests límits després de veure resultats. Una extensió és una
campanya nova amb ID, manifest i pressupost propis.

## Mostreig determinista cada 10 minuts

Persistir una línia JSON/SQLite amb:

- timestamp UTC, `run_id`, projecte i build SQ;
- procés/contenidor, fase, uptime i exit code;
- CPU, RSS, memòria host i disc lliure;
- `generated`, `failed`, percentatge acceptat i estratègies/hora via API SQ;
- candidats en memòria i `.sqx` persistits;
- últim candidat, autosync i canvi de log;
- errors estructurats i hash de configuració/dataset;
- fingerprint/família lògica dels candidats nous.

L'escriptura ha de ser atòmica. No usar un LLM per polling ni esperes.

## Màquina d'estats

| Estat | Condició | Acció |
|---|---|---|
| `HEALTHY` | procés i intents avancen; arribades dins rang | continuar |
| `SELECTIVE` | intents avancen però cap acceptat encara dins rang | continuar i registrar |
| `WARN_STALE` | supera el primer llindar sense acceptat | revisar logs/configuració |
| `INVESTIGATE` | supera el segon llindar | comprovar API, databank, recursos i filtres |
| `SCIENTIFIC_STALL` | intents avancen però no hi ha candidat/família útil segons política preregistrada | aturar amb snapshot |
| `COMPUTE_STALL` | intents, logs i databank no avancen | diagnosi; reinici segur si estava autoritzat |
| `BROKEN` | procés mort, OOM, corrupció o error fatal | preservar evidència; recuperar |
| `BUDGET_REACHED` | temps/intents/acceptats assolits | aturar i congelar lot |

## Llindar adaptatiu d'arribades

Calcular la mediana robusta del temps entre candidats acceptats, excloent la fase
d'arrencada. Defaults conservadors:

```text
warn_after        = max(60 min, 4 × median_interarrival)
investigate_after = max(120 min, 8 × median_interarrival)
```

`SCIENTIFIC_STALL` no s'activa només pel rellotge: cal que els intents continuïn
augmentant i que la regla (per exemple, tres hores sense candidat/família nova)
hagi quedat congelada al manifest. Sense comptador d'intents fiable, marcar
confiança baixa i no confondre `SELECTIVE` amb `COMPUTE_STALL`.

## Valor marginal i diversitat

Un candidat nou aporta valor si millora una dimensió sense degradar greument la
resta, o aporta una família nova:

- trades i cobertura temporal/règims;
- benefici net, drawdown i concentració;
- complexitat i estabilitat paramètrica;
- fingerprint de regles/indicadors/sortides;
- correlació amb candidats existents;
- viabilitat preliminar per 200 USDC/Ostium.

Detectar clústers per estructura abans que per nom. Cinquanta variants EMA/SMA no
són cinquanta hipòtesis independents. Front de Pareto i famílies informen; la
regla d'aturada ha d'estar preregistrada.

## Checkpoints i recuperació

- Projecte/databank en volum persistent, mai només dins `--rm`.
- Autosync SQ cada 10 minuts.
- Inventari atòmic de `.sqx`: path, mida, mtime i SHA-256.
- Snapshot de manifest/configuració abans i després de cada fase.
- No copiar `internal/tmp`, testfiles o dades regenerables.
- No netejar mentre hi hagi SQCLI actiu.
- En fallada, conservar stdout/logs/API/status abans de reiniciar.

Reiniciar pot conservar acceptats, però no garanteix reprendre el mateix estat
aleatori. És continuació operativa, no reproducció exacta.

## Campanya activa XAU H4

Projecte: `ALQUIMIA_XAU_H4_DISCOVERY`.

- Criteri original: databank ple amb 60 acceptats.
- Sense límit temporal ni pressupost d'intents preregistrat.
- Autosync cada 10 minuts; volum persistent `/mnt/volume-SQ/user`.
- Holdout segellat; no modificar criteris després dels resultats observats.
- Aplicar només alertes de salut. No inventar ara un timeout científic.
- En acabar: congelar lot, inventariar/hashing, deduplicar i iniciar embut.

## Controlador implementat

`lab/sq_bridge/sq_watchdog.py` carrega els límits del manifest, compta els intents
reals quan SQ publica `tasksIterations`, desa journal JSONL append-only i una
vista atòmica, i inventaria els `.sqx` sense modificar-los. En SQX 143.2708 el
CLI HTTP no implementa `project status` i el broadcast TaskManager pot quedar
silenciós amb projectes aturats. En aquest cas el transport GUI conserva només
identitat/databank via REST, marca `generated=null` i no activa el gate d'intents.
Per defecte és només lectura. `--allow-control` és obligatori perquè un gate
terminal executi primer `pause` i després `stop`; un error del monitor mai envia
control a SQ.

Les campanyes genètiques noves incorporen una segona barrera al CFX:
`illes × població × generacions <= attempt_budget`, decimació 1 i sense reinici
automàtic. Això evita una cerca infinita encara que el WebSocket falli. El
comptador observat continua sent l'autoritat final: la cota nominal no substitueix
el snapshot i un overshoot no es maquilla.

En projectes d'una sola tasca, declarar `attempt_budget_per_project`. Si el
manifest només té un pressupost total divisible pel nombre de símbols, el
controlador el reparteix de forma inequívoca. El polling pot sobrepassar el límit
en els treballs que ja estiguin en vol: registrar l'overshoot real i no usar dues
passades amb intents diferents com una comparació Random/Genetic.

Encara queden fora del controlador mínim la diversitat semàntica, l'autosync i
el reinici automàtic. Són observables addicionals; no bloquegen el pilot aïllat
de 1.000 intents perquè el journal, l'inventari i el volum persistent preserven
els resultats.

## Tasca preparada per a una sessió nova

```text
Implementa docs/SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md sense tocar ni aturar
ALQUIMIA_XAU_H4_DISCOVERY. Refactoritza lab/sq_bridge/sq_watchdog.py perquè tots
els límits vinguin d'un manifest versionat; elimina target=20; afegeix snapshots
append-only, interarribades robustes, la màquina d'estats documentada i inventari
SHA-256 de .sqx. Separa monitorització de la facultat d'aturar: per defecte només
observa; stop/restart requereixen flags explícits. Afegeix tests amb rellotge i API
SQ simulats: reinici, API absent, arribades irregulars, autosync retardat,
disc/memòria baixa i cap fals stall. No modifiquis academia/, BrokerageService,
Ostium ni trading live. Prova primer amb fixtures i després read-only en un SQ real.
```

## Criteris d'acceptació

1. Cap límit màgic codificat.
2. Mateixa seqüència d'inputs produeix els mateixos estats.
3. Una fallada del monitor no pot aturar SQ.
4. Mode per defecte read-only; stop/restart opt-in i auditats.
5. Cap candidat persistit es modifica o elimina.
6. Tests de falsos positius per arribades irregulars.
7. Handoff amb comanda, esquema, tests i recuperació provada.
