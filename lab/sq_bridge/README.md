# SQ bridge — campanyes programàtiques

Primera peça del pont StrategyQuant → DuckDB/BS → TradingAgent. Prepara una còpia
limitada d'un projecte `.cfx` sense modificar l'original i deixa un manifest amb
hashes per poder reproduir la campanya.

## Alquímia v3 — cadena d'evidència nativa

`methodology_v3.json` és el contracte canònic per a campanyes noves. No permet
usar resultats quantitatius heretats per promocionar candidats; un CFX anterior
només pot aportar sintaxi XML i recursos de mercat. `evidence_chain.py` encadena
rebuts SHA-256 en l'ordre obligatori:

```text
market_preflight → discovery → temporal_validation → robustness
→ small_account_economics → python_translation → parity → paper
```

Cada rebut fixa artifact, decisió, candidats, accés al holdout i hash del rebut
anterior. Només `PASS` avança; `REJECT` i `BLOCK` són terminals. Traducció
requereix equivalència exacta i paritat requereix `parity_pass=true`. Paper no
autoritza live.

`market_universe_gate.py` congela la idoneïtat de la font abans de descobrir
estratègies. `xau_d1_inside_breakout_v9.py` és un preflight nadiu preregistrat:
agrega Dukascopy M1 amb sessió New York/DST, incorpora costos i funding, exigeix
regions de paràmetres i impedeix obrir validació des del runner de train.
V10 afegeix selecció del medoid del component estable sense mirar rendiment i
un runner independent que només pot consultar el tram de validació congelat.

El recorder BTC viu a BrokerageService. Aquest pont només en comprova maduració:

```bash
python3 -m lab.sq_bridge.ostium_native_coverage_gate \
  --root /mnt/volume-SQ/dev/BrokerageService/datafiles/realtime_datalayer/candles/BTCUSD/America_New_York \
  --output lab/out/alquimia/btcusd_native_coverage_latest.json \
  --fail-unless-ready
```

El codi de sortida és 2 mentre no hi ha 60 dies, cobertura 90%, continuïtat i
frescor. `READY_FOR_PARITY` només permet executar la comparació de fonts; no
autoritza discovery, paper ni live. `market_universe_gate.py` exigeix després
un artifact de paritat `PASS_RESEARCH_OHLC` abans d'incloure BTC.

```bash
python3 evidence_chain.py new --methodology methodology_v3.json \
  --campaign CAMPAIGN --hypothesis HYPOTHESIS --market XAUUSD --output chain.json
python3 evidence_chain.py verify chain.json --methodology methodology_v3.json
```

Per a hipòtesis dirigides, limitar blocs SQ no és evidència semàntica suficient.
`structural_hypothesis_gate.py` valida l'AST extret per `sqx_extract.py`; el
perfil `xau_h4_sweep_reclaim_v4` exigeix exactament break + reclaim tant long
com short abans de consultar les mètriques.

La v5 fixa aquesta semàntica en un seed i usa un preflight Dukascopy train-only
abans de gastar una optimització SQ. La malla conserva l'agregació H4 escassa de
BrokerageService, resol amb stop-first qualsevol ambigüitat H4 i exigeix una
regió amb almenys dos veïns ortogonals, no un màxim aïllat:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m lab.sq_bridge.xau_sweep_reclaim_preflight \
  --root /mnt/volume-SQ/dev/BrokerageService/datafiles/historical_parquet \
  --output lab/out/alquimia/xau_h4_sweep_reclaim_v5/train_preflight.json \
  --summary-output lab/sq_bridge/evidence/xau_h4_sweep_reclaim_v5_train_preflight_summary.json
```

Resultat congelat: 1.350 punts, 0 PASS d'estrès, 0 membres estables i holdout no
consultat. Per tant v5 acaba en `REJECT_FAMILY_V5`; no s'ha executat l'Optimizer
de 5.000 punts. El resum versionat fixa el SHA-256 de l'artifact complet ignorat.

V6 amplia el preflight reutilitzable a H1 per mecanisme, direcció, hora, dia,
expansió ATR i durada. V7 mostra com congelar una observació de train amb el
biaix declarat i executar una única validació independent:

```bash
.venv/bin/python -m lab.sq_bridge.xau_h1_displacement_preflight \
  --root /mnt/volume-SQ/dev/BrokerageService/datafiles/historical_parquet \
  --output lab/out/alquimia/xau_h1_displacement_v6/train_preflight.json \
  --summary-output lab/sq_bridge/evidence/xau_h1_displacement_v6_train_summary.json

.venv/bin/python -m lab.sq_bridge.xau_h1_late_reversal_v7 \
  --stage validation \
  --root /mnt/volume-SQ/dev/BrokerageService/datafiles/historical_parquet \
  --family lab/sq_bridge/family_xau_h1_late_reversal_v7.json \
  --output lab/sq_bridge/evidence/xau_h1_late_reversal_v7_validation.json
```

V6 acaba sense regió estable. V7 passa train però falla validació amb costos
d'estrès; ambdues cadenes són terminals i no consulten OOS ni holdout.

## Paritat equity SQ → Ostium

`sq_ostium_equity_parity.py` compara un CSV custom exportat pel Data Manager d'SQ
amb M1 Ostium agregat a la sessió regular. És offline i comprova OHLC, correlació
de retorns, direcció, sessions incompletes i outliers; un PASS és només de font
de recerca, mai de fills o live.

```bash
.venv/bin/python -m lab.sq_bridge.sq_ostium_equity_parity \
  --sq-csv '/mnt/volume-SQ/user/exports/alquimia_msft_d1/MSFT-D1-No Session.csv' \
  --ostium-root /mnt/volume-SQ/dev/BrokerageService/datafiles/realtime_datalayer/candles/MSFT \
  --symbol MSFT --output lab/sq_bridge/evidence/msft_d1_gap_shock_v8_source_parity.json
```

MSFT v8 passa close però falla open/high/low, de manera que una família de gaps
queda bloquejada abans de Builder. No es pot convertir un PASS close-only en un
PASS OHLC.

```bash
cd lab/sq_bridge
python3 test_sq_campaign.py

python3 sq_campaign.py prepare \
  --source "/mnt/volume-SQ/user/projects/NVIDIA/project.cfx" \
  --output "/mnt/volume-SQ/user/projects/TA_SQ_PILOT/project.cfx" \
  --name TA_SQ_PILOT \
  --limit 20
```

Abans d'executar el projecte cal inspeccionar el resultat:

```bash
python3 sq_campaign.py inspect \
  /mnt/volume-SQ/user/projects/TA_SQ_PILOT/project.cfx
```

L'execució SQCLI es fa com a procés `one-off`: aturar temporalment la GUI,
executar la campanya i tornar a iniciar la GUI. Un `PASS` de SQ no autoritza ni
paper ni live; després cal paritat de dades/trades i el gate Ostium.

## Font BTC reproduïble i round-trip SQ

`binance_sq_source.py` construeix una font separada a partir dels arxius oficials
amb checksum. `sq_data_roundtrip_audit.py` compara la reexportació de SQ fila per
fila. El primer rebut és `evidence/btcusdt_binance_sq_roundtrip.json`: 43.200
timestamps exactes, error OHLC màxim 0,05 USD i volum no exacte. El seu PASS és
només per recerca de senyals sense volum; no implica paritat Ostium ni autoritza
paper/live.

La font multirègim i les dues falsificacions BTC es reprodueixen així:

```bash
python3 binance_sq_source.py --symbol BTCUSDT \
  --from-month 2018-03 --to-month 2026-06 \
  --archive-dir /path/archives --output-csv /path/BTCUSDT_M1_FULL.csv \
  --manifest evidence/btcusdt_binance_full_source_manifest.json
PYTHONPATH=../.. python3 btc_multimechanism_v11.py \
  --source /path/BTCUSDT_M1_FULL.csv --family family_btc_multimechanism_v11.json \
  --output evidence/btc_multimechanism_v11_train.json
PYTHONPATH=../.. python3 btc_multimechanism_v11_validation.py \
  --source /path/BTCUSDT_M1_FULL.csv --family family_btc_multimechanism_v11.json \
  --train evidence/btc_multimechanism_v11_train.json \
  --output evidence/btc_multimechanism_v11_validation.json
```

V12 usa `btc_regime_breakout_v12.py` i
`btc_regime_breakout_v12_validation.py`. El verificador final
`btc_research_checkpoint.py` exigeix mateixa font, rebuig terminal de totes dues
validacions i holdout intacte. Cap PASS de proxy pot saltar-se el gate natiu
Ostium ni el small-account gate.

V13 i V14 comparteixen un motor de sessió però no evidència de promoció:

```bash
PYTHONPATH=../.. python3 btc_session_breakout_v13.py \
  --source /path/BTCUSDT_M1_FULL.csv \
  --family family_btc_session_breakout_v13.json \
  --output evidence/btc_session_breakout_v13_development.json
PYTHONPATH=../.. python3 btc_session_breakout_v13.py \
  --source /path/BTCUSDT_M1_FULL.csv \
  --family family_btc_session_fade_v14.json \
  --output evidence/btc_session_fade_v14_development.json
```

`btc_session_checkpoint.py` comprova mateixa font, zero regions estables i que
validació/OOS/holdout continuen tancats. ETHUSD i SOLUSD també acumulen M1 al
recorder de BrokerageService; els artifacts inicials de cobertura són només
`WARMING`, mai permisos de recerca, paper o live.

## Fallback Python MSFT D1

Quan el Retest SQCLI no progressa ni amb un únic candidat, el subset compatible
es pot traduir i validar sense GUI. La selecció normal no obre el holdout:

```bash
python3 msft_python_validation.py \
  --inventory ../out/alquimia/ALQUIMIA_MSFT_D1_TREND_LONG_inventory.json \
  --output ../out/alquimia/msft_python_validation.json
```

`--unseal-holdout` només s'utilitza després de congelar `--finalist`. El gate
final determinista aplica costos 12/24/36 bps, bootstrap Monte Carlo amb seed
derivada de la identitat SQX i sizing a risc 1% per 200 USDC:

```bash
python3 msft_final_gate.py \
  --source ../out/alquimia/msft_finalists_holdout.json \
  --output ../out/alquimia/msft_final_gate.json --runs 10000
```

L'execució usa Yahoo OHLC provisional. Només el close D1 està certificat contra
Ostium; per tant el resultat no pot autoritzar live.

## Campanyes Dukascopy amb DuckDB

Els runners `tsmom_duka_campaign.py` i `xau_orb_campaign.py` consulten directament
els Parquet de BrokerageService. Per no modificar el Python del sistema:

```bash
python3 -m venv .venv-alquimia
.venv-alquimia/bin/pip install duckdb pandas numpy
```

Els dos runners mantenen el holdout tancat per defecte. L'opció
`--unseal-holdout` només és vàlida juntament amb un únic `--finalist` congelat.

## Inventari offline d'un databank congelat

`discovery_inventory.py` és genèric per a qualsevol directori de fitxers `.sqx`.
No inicia SQCLI ni consulta cap holdout. Verifica membres obligatoris, calcula
hashes i extreu fingerprints, trades, benefici, drawdown, fitness, complexitat,
indicadors i estructures de senyal.

```bash
python3 discovery_inventory.py \
  /path/to/project/databanks/Results \
  --project-cfx /path/to/project/project.cfx \
  --project-manifest /path/to/project/project.manifest.json \
  --output /path/to/inventory.json
```

Produeix tres nivells deliberadament separats:

- `structural_family`: arbre de senyals sense valors de paràmetres;
- `archetype`: conjunt d'operadors/indicadors;
- `entry_indicator_archetype`: agrupació ampla dels indicadors d'entrada.

També calcula un front de Pareto descriptiu IS. No és un gate de promoció: només
marca candidats no dominats en les mètriques observades. Validació temporal,
costos, règims i Ostium continuen sent obligatoris.

## Screen determinista v4 abans d'SQ

Una campanya v4 no escriu a mà els PF train ni el nombre de veïns. Congela una
graella finita `hypothesis_screen_grid_trace` amb variants centrals, topologia de
veïnat i trades bruts amb costat i durada. Per a EURUSD D1, el productor
preregistrat crea aquesta graella només després de congelar costos:

```bash
PYTHONPATH=../.. python3 eurusd_d1_hypothesis_trace_v4.py \
  --source /mnt/volume-SQ/user/imports/alquimia_eurusd_v4/EURUSD_ALQ_NY17_D1.csv \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --output /path/to/hypothesis-screen.trace.json
```

El trace queda lligat per SHA-256 al CSV canònic, al tall posicional de train i
a totes les dates d'entrada i sortida. El gate reobre les candles i reexecuta
les nou variants: el hash de la font sense replay exacte dels trades no basta.
Quan el readiness autoritza el screen, el trigger operatiu congela primer tots
els `latest`, el CSV i la metodologia en un snapshot immutable; després el
bootstrap executa trace i rebut una sola vegada i crea una cadena i un pla SQ
separats per cada hipòtesi que passi:

```bash
PYTHONPATH=../.. python3 eurusd_v4_screen_trigger.py \
  --preflight /path/to/eurusd_market_preflight_latest_v4.json \
  --source /mnt/volume-SQ/user/imports/alquimia_eurusd_v4/EURUSD_ALQ_NY17_D1.csv \
  --output-dir /path/to/state/eurusd-v4-screen
```

En `BLOCK`, el trigger retorna `WAITING_FOR_MARKET_PREFLIGHT` sense crear estat
ni consultar rendiment. En `PASS`, journalitza, congela i recompon el preflight
amb les còpies; una interrupció es reprèn des del snapshot. Una repetició
revalida hashes, cadenes i plans sense adoptar noves mostres. El bootstrap no
inicia SQCLI. Si cap hipòtesi passa, escriu `REJECT_NO_HYPOTHESIS` sense crear
branques.

Només train és visible. El nocional canònic del screen és 200 USDC; el
constructor verifica el model congelat, recomputa round-trip i carry, recompte
els intents reals i recalcula PF
per variant i exigeix que la central i almenys dos veïns superin 50 trades i PF
1,20 sota tots tres costos. Una hipòtesi rebutjada no arriba a SQCLI.

Quan la cadena queda exactament a `next_stage=sq_generation`, es compila el pla
de la hipòtesi seleccionada i el contracte posicional compartit amb SQ:

```bash
PYTHONPATH=../.. python3 eurusd_sq_generation_plan_v4.py \
  --screen /path/to/state/artifacts/02_hypothesis_screen.json \
  --chain /path/to/state/chain.json \
  --period-contract-output /path/to/state/eurusd-periods-v4.json \
  --output /path/to/state/eurusd-sq-plan-v4.json
```

El pla assigna un perfil de blocs traduïbles diferent a `d1_breakout`,
`d1_momentum` i `d1_shock_reversion`. Cada mecanisme es criba separadament com
`both`, `long` i `short`, de manera que una direcció dolenta no pot ocultar una
direcció útil; el CFX conserva aquesta direcció per contracte. Els tres perfils
permeten `BarDayOfWeekIs`, però D1 prohibeix inventar filtres horaris intradia.
El pla exigeix cerca genètica i conserva el
pressupost màxim de 10.000 intents. `Highest` i `Lowest` formen part del subset
SQX→IR→Python provat; ATR es manté com a fórmula de stop, no com a operador de
senyal no reproduït.

No cal traslladar aquests plans a mà. Quan el bootstrap tingui branques, el batch
recompila independentment cada pla des del screen i la cadena, genera tots els
CFX i els reobre amb el contracte genètic:

```bash
PYTHONPATH=../.. python3 eurusd_v4_project_batch.py \
  --bootstrap /path/to/state/eurusd-v4-screen/bootstrap.json \
  --scaffold /path/to/technical-scaffold.cfx \
  --output-dir /path/to/state/eurusd-v4-projects
```

El resultat `project_batch.json` lliga bootstrap, scaffold, registre Ostium,
metodologia, CFX i manifests per ruta/hash i manté `sqcli_started=false`. No
importa ni inicia projectes. Un checkpoint marca cada branca `VERIFIED` només
després de reobrir CFX i manifest; una interrupció reconstrueix la branca
parcial i una repetició completa només revalida. CFX i manifest són
byte-reproduïbles: dues compilacions amb les mateixes entrades produeixen el
mateix SHA-256; timestamps operatius pertanyen al journal, no al contracte
científic.

La importació també és una fase separada de l'inici:

```bash
PYTHONPATH=../.. python3 sqcli_import_batch.py \
  --batch /path/to/state/eurusd-v4-projects/project_batch.json \
  --output-dir /path/to/state/eurusd-v4-import
```

Abans de mutar SQ valida tots els hashes/CFX i rebutja noms ja existents. Usa un
fitxer temporal restringit dins el contenidor, crida `taskmanager/openProject`,
elimina el temporal, torna a exportar el CFX reserialitzat per SQ i verifica de
nou forma genètica, stop i recursos resolts. El rebut conserva ambdós hashes i
sempre declara `sqcli_started=false`; iniciar és una operació posterior. Abans
de cada mutació escriu un `IMPORT_INTENT` i, després de reexportar/verificar el
CFX, el converteix en `VERIFIED`. Repetir un batch complet és idempotent; si el
procés cau després d'obrir un projecte, el checkpoint permet reprendre'l sense
confondre'l amb una col·lisió aliena ni tornar-lo a importar.
Una importació nova també exigeix inactivitat global d'SQCLI; si Academia o un
altre projecte està calculant, es nega abans del primer `docker cp`.

L'inici també és una fase contractada i només admet una hipòtesi ja importada:

```bash
PYTHONPATH=../.. python3 sqcli_supervised_run.py \
  --import-receipt /path/to/state/eurusd-v4-import/sqcli_import_receipt.json \
  --hypothesis d1_breakout_both \
  --output-dir /path/to/state/eurusd-v4-runs/d1_breakout_both
```

El llançador revalida el batch, manifest i CFX reserialitzat, rebutja qualsevol
altre projecte SQ en execució i exigeix que el projecte objectiu estigui resolt
i amb databank buit. Escriu el preflight abans de començar i entrega el control
al watchdog fins que existeix el log final exacte; ni paper ni live queden
autoritzats per una execució de generació.

## Worker EURUSD v4 separat

`eurusd_v4_sq_worker.py` encadena les fases anteriors sense compartir procés ni
lock amb el collector de costos. Abans del screen retorna `WAITING_FOR_SCREEN`;
un `REJECT_SCREEN_TRIGGER` és terminal i no toca SQ. Amb un PASS congela el
scaffold, el registre Ostium i la metodologia, compila el batch, espera
inactivitat global, importa i executa les branques en ordre. Si el procés cau,
només reprèn un projecte actiu quan el journal demostra que és exactament la
seva branca actual.

El scaffold preregistrat és `/mnt/volume-SQ/user/projects/EURUSD/project.cfx`,
SHA-256 `48a0484d...13da5d`, de SQ 143.2708. Es valida que contingui exactament
un Build task, els camps estructurals requerits i els 18 blocs necessaris. Es
reutilitza exclusivament com a format XML: `alquimia_project.py` elimina les
altres tasques i reescriu mercat, dates, regles, cerca genètica, risc, ranking i
pressupost des de la cadena v4. No se'n reutilitzen estratègies, databanks,
rendiments ni paràmetres quantitatius.

Aquesta última garantia és executable: `methodology_v4.json` preregistra
genètica 80% crossover / 20% mutació i migració 5 generacions / 10%, i espais
separats per família. Breakout usa períodes 20–100 i sortides 8–25 barres;
momentum 40–150 i 10–30; shock reversion 2–30 i 2–10. El constructor elimina
presets i thresholds del scaffold, força Close-only, pesos uniformes i rangs
RSI/ROC propis. `verify_genetic_project` reobre l'XML i rebutja qualsevol
herència o desviació abans de la importació.

El worker s'instal·la independentment cada deu minuts laborables:

```bash
scripts/install_eurusd_v4_sq_worker_cron.sh
```

`flock` impedeix dos workers simultanis. Una execució llarga conserva aquest
lock, però el collector horari continua perquè utilitza un lock diferent. El
rebut final és `PASS_SQ_GENERATION_ORCHESTRATED` si existeixen candidats o
`REJECT_NO_SQ_CANDIDATES` si totes les branques acaben sense SQX; cap dels dos
autoritza paper o live.

El `market_preflight` observat que precedeix aquest screen no es valida només
amb els seus totals. Conserva `campaign_config_path` i SHA-256; el contracte
reexecuta el compositor sobre cobertura històrica, mapping i costos congelats.
VIX o un altre estat de règim és opcional, però quan existeix també forma part
de les fonts hashades i ha de respectar el timing anti-look-ahead.

El CFX que s'executa s'ha d'haver creat amb la cadena preparada exactament per
a generació:

```bash
PYTHONPATH=../.. python3 alquimia_project.py \
  --source /path/to/technical-scaffold.cfx \
  --output /path/to/project.cfx --name PROJECT_NAME --market EURUSD \
  --methodology methodology_v4.json --date-from YYYY-MM-DD --date-to YYYY-MM-DD \
  --generation-type genetic-evolution --attempt-budget 10000 \
  --period-contract /path/to/state/eurusd-periods-v4.json \
  --evidence-chain /path/to/state/chain.json \
  --campaign-id CAMPAIGN_ID --source-hypothesis-id HYPOTHESIS_ID
```

El constructor revalida la cadena i només accepta `next_stage=sq_generation`.
El scaffold continua aportant únicament format XML, mai evidència quantitativa.
La mida genètica nominal queda incorporada al CFX: `Islands × PopulationSize
× MaxGenerations <= attempt_budget`, amb decimació 1 i els reinicis en acabar o
per estancament desactivats. Per al pressupost v4 de 10.000 són 4 illes, 100
individus per illa i 25 generacions. El manifest desa aquesta forma perquè una
auditoria no depengui només del valor declarat a la línia de comandes. No és una
cota dura: SQ pot generar reemplaçaments per omplir la població inicial filtrada.
Per absorbir treballs ja en vol, v4 congela `attempt_stop_guard=64`: amb pressupost
10.000 el watchdog ordena parar quan el comptador live arriba a 9.936. El
watchdog aplica aquest llindar sobre `engine.totalJobsDone` i el log final
`Strategies generated` és l'evidència exacta; un overshoot invalida el contracte.
Aquest 64 és només reserva d'intents en vol. El pressupost del databank és
diferent: **60 candidats globals**, repartits exactament i determinísticament
entre les branques que passin el screen. El `StopCondition`, el manifest i el
validador de cada CFX han de coincidir amb la seva quota congelada. Una branca
que no l'omple aporta menys candidats; no se'n rescaten ni redistribueixen a
posteriori.
L'ingestor no confia en aquest objecte del manifest: reobre `config.xml` i
l'únic `Build-Task*.xml` del CFX, recalcula el producte, verifica decimació,
reinicis i `StopCondition`, i publica la ruta/hash del CFX perquè el validador
de cadena repeteixi la comprovació independentment.

En v4 força spread, comissió i slippage d'SQ a zero i ho registra al manifest:
la descoberta produeix retorn brut i el model Ostium congelat aplica els costos
una sola vegada després. Les metodologies legacy conserven el seu comportament
històric, però no poden promocionar evidència v4.

Per a una campanya v4, el rebut de `sq_generation` tampoc s'escriu a mà. Després
de congelar el databank i el recompte real d'intents, es genera així:

```bash
PYTHONPATH=../.. python3 sq_generation_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --source-hypothesis-id HYPOTHESIS_ID \
  --databank-dir /path/to/frozen/databank \
  --watchdog-status /path/to/final-watchdog-status.json \
  --project-cfx /path/to/project.cfx \
  --project-manifest /path/to/project.manifest.json \
  --output /path/to/state/artifacts/03_sq_generation.json
```

L'ingestor reobre cada SQX i en deriva el `StrategyName`, SHA-256, subset
traduïble i condicions d'entrada long/short. Un `AND` suma predicats, però els
indicadors operands d'un predicat no compten com regles addicionals. La
complexitat és el màxim de les dues direccions actives i v4 rebutja més de tres.
També verifica que el CFX coincideix amb el manifest genètic preregistrat. El
recompte d'intents es deriva del snapshot final del watchdog, que ha d'haver
arribat a un gate congelat. L'inventari és recursiu i lliga totes les rutes i
hashes del databank a aquest snapshot. El validador torna a obrir els SQX i
recalcula l'inventari: alterar el JSON o afegir/treure un fitxer després no pot
fer passar una execució diferent.

En SQX 143.2708 el port CLI 5050 respon `Not implemented` a `project status`.
La GUI 8080 ofereix `taskmanager/listProjects` i els canals WebSocket oficials
`engine-channel`/`progress-channel`; el TaskManager només publica
`tasksIterations`, que compta cicles i no estratègies, mentre hi ha activitat. El
watchdog se subscriu com la GUI i usa `engine.totalJobsDone` com a límit inferior
viu; si SQ resta silenciós retorna telemetria REST degradada
amb `generated=null`: no inventa intents i no pot activar el gate d'intents.
Pausa i stop són sempre opt-in (`--allow-control`) i reprodueixen els GET de la
GUI oficial. En finalitzar copia i hasha el log global, en deriva el recompte
exacte i refresca l'inventari SQX. Sense aquest log, `sq_generation` v4 no passa.

`sq_generation` conserva tots els candidats únics que compleixen el subset de
traducció i el límit estructural; no declara un fals «millor candidat» a partir
del fitness intern d'SQ. El front Pareto promocionable es calcula a
`temporal_validation`, quan ja existeixen expectativa neta amb costos,
drawdown OOS i estabilitat entre finestres. El rebut temporal ha d'incloure
l'univers complet rebut d'SQ i el validador recalcula tant els dominats com els
IDs seleccionats.

Quan s'executa dins del runner, `sq_generation_stage_v4.py` uneix de forma
reprenable el rebut d'importació, el llançador supervisat i l'ingestor anterior.
Un `start_receipt.json` durable impedeix un segon inici després d'una interrupció.
L'artefacte lliga tant el CFX font com el CFX reserialitzat realment importat.
Si el pressupost acaba amb zero SQX, escriu `REJECT` amb candidats buits i tota
l'evidència operativa; no deixa la campanya en un bucle fals de reintents.

Cada candidat aporta un trace `temporal_validation_trade_trace` amb capital i
nocional comparatiu de 200, retorn brut, costat, durada, trades train i
finestres OOS UTC no solapades.
El trace es deriva de l'`orders.csv` observat d'SQ; classifica per la data local
del recurs, construeix finestres anuals dins validation/OOS i falla si un trade
creua una frontera o arriba al holdout:

```bash
PYTHONPATH=../.. python3 sq_temporal_trace_v4.py \
  --candidate-id CANDIDATE_ID --orders /path/to/orders.csv \
  --retest-receipt /path/to/supervised_retest_receipt.json \
  --temporal-contract /path/to/temporal-split-contract.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --source-timezone America/New_York \
  --output /path/to/candidate.temporal.trace.json
```

El validador reconstrueix el trace des del CSV i les fonts hashades; editar
retorns, trades, finestres o costos deixa de ser una via possible. El rebut de
`sqcli_supervised_retest.py` és obligatori: reobre el CFX, el SQX d'entrada i de
sortida, l'`orders.bin`, el log final i el CSV. Un export manual o deslligat del
candidat no és evidència nativa admissible.

L'artefacte no s'edita manualment:

```bash
PYTHONPATH=../.. python3 temporal_validation_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --trace /path/to/candidate-a.temporal.trace.json \
  --trace /path/to/candidate-b.temporal.trace.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --artifact-output /path/to/state/artifacts/04_temporal_validation.json
```

El constructor verifica el SHA-256 dels costos, deriva PnL base incloent carry i
recomputa trades, PF, EV neta, drawdown, finestres positives i
decay train→OOS; després aplica els gates i forma el front Pareto. Modificar un
trace, ometre un candidat rebut d'SQ o declarar accés al holdout invalida el
rebut.

La robustesa v4 tampoc accepta resums manuals. Cada candidat aporta un
`robustness_simulation_trace` amb exactament 1.000 runs Monte Carlo, quatre o
més veïns paramètrics a ±10%, resultats bruts i exposició, leverage provat,
límit Ostium i excursió adversa màxima de cada run:

El cross-check natiu de paràmetres es genera sense GUI i es verifica reobrint
el CFX. Només `MonteCarloRetest/RandomizeStrategyParameters` queda actiu; el
CFX és reproduïble i el verificador comprova les 1.000 simulacions, probabilitat
10%, canvi màxim 10% i simetria:

```bash
PYTHONPATH=../.. python3 alquimia_monte_carlo.py \
  --source /path/to/candidate-pre-holdout.cfx \
  --output /path/to/candidate-mc.cfx \
  --base-retest-manifest /path/to/candidate-pre-holdout.manifest.json \
  --name ALQUIMIA_MC_CANDIDATE --simulations 1000 \
  --probability-pct 10 --max-change-pct 10
```

Després del Retest, la SQX resultant ha de contenir exactament
`MonteCarloRetest_Simulation0Orders.bin` fins a
`MonteCarloRetest_Simulation999Orders.bin`, tots no buits, i un
`MonteCarloRetest_Results.xml` coherent. Es valida i es materialitza cada run
com una SQX determinista apta per a `orderstocsv`:

```bash
PYTHONPATH=../.. python3 sqcli_supervised_monte_carlo.py \
  --cfx /path/to/candidate-mc.cfx \
  --manifest /path/to/candidate-mc.manifest.json \
  --output-dir /path/to/mc-supervision

PYTHONPATH=../.. python3 sqx_monte_carlo_contract.py \
  --sqx /path/to/native-mc-result.sqx --simulations 1000 \
  --probability-pct 10 --max-change-pct 10

PYTHONPATH=../.. python3 sqx_monte_carlo_materialize.py \
  --sqx /path/to/native-mc-result.sqx --output-dir /path/to/mc-runs \
  --simulations 1000 --probability-pct 10 --max-change-pct 10 \
  --supervised-mc-receipt /path/to/mc-supervision/supervised_monte_carlo_receipt.json

PYTHONPATH=../.. python3 sqcli_supervised_mc_exports.py \
  --materialization-manifest /path/to/mc-runs/materialization.manifest.json \
  --output-dir /mnt/volume-SQ/user/projects/ALQUIMIA_MC/exports \
  --host-projects-root /mnt/volume-SQ/user/projects

PYTHONPATH=../.. python3 robustness_trace_v4.py \
  --candidate-id CANDIDATE_ID \
  --temporal-trace /path/to/candidate.temporal.trace.json \
  --mc-export-receipt /path/to/supervised-mc-exports.receipt.json \
  --cost-model /path/to/costs-frozen-v4.json \
  --tested-leverage 5 --venue-max-leverage 100 \
  --output /path/to/candidate.robustness.trace.json
```

El manifest lliga cada SQX materialitzada al binari natiu original amb
SHA-256 i al rebut de l'execució supervisada. Sense aquest rebut queda marcat
`synthetic_control` i no pot construir evidència promocionable. L'exportador
escriu un checkpoint atòmic per run, valida les columnes
i hashes de cada CSV i reprèn després d'una interrupció sense repetir feina.
La traça separa dues proves: 1.000 bootstraps IID dels trades observats amb
llavor preregistrada `20260811`, i les 1.000 variants natives
`RandomizeStrategyParameters` amb probabilitat 10% i canvi màxim ±10%.
Reobre també el rebut temporal i exigeix la mateixa estratègia, símbol,
timeframe i període pre-holdout. La presència del cross-check per si sola no és
suficient.

```bash
PYTHONPATH=../.. python3 robustness_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --trace /path/to/candidate-a.robustness.trace.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --artifact-output /path/to/state/artifacts/05_robustness.json
```

El constructor aplica al nocional fix de 200 USDC el pitjor entre `stress` i
2×base, inclòs carry, i recomputa proporció Monte Carlo rendible, estabilitat
dels veïns, PF estressat i liquidacions. Aquestes últimes no són booleans acceptats de la
font: es deriven de l'excursió adversa, leverage i límit del mercat. El sizing
posterior no pot usar més leverage ni un límit de venue diferent del provat.
La traça temporal anterior conserva `MAE ($)` convertit a percentatge amb el
`pointValue` i `orderSizeMultiplier` extrets de la mateixa SQX Retest. Per tant,
el càlcul de liquidació no pot assumir erròniament que una mida FX en lots són
unitats, ni accepta un multiplicador escrit a mà.

La cadena completa per candidat temporalment promocionat s'executa amb un sol
stage. Exigeix costos Ostium congelats, i tant el directori de treball com les
SQX queden dins del mount de projectes d'SQCLI:

```bash
PYTHONPATH=../.. python3 sq_robustness_stage_v4.py \
  --campaign-id CAMPAIGN_ID \
  --temporal-artifact /path/to/04_temporal_validation.json \
  --cost-model /path/to/costs-frozen-v4.json \
  --work-dir /mnt/volume-SQ/user/projects/ALQUIMIA_ROBUSTNESS \
  --host-projects-root /mnt/volume-SQ/user/projects \
  --venue-max-leverage 100 \
  --artifact-output /path/to/state/artifacts/05_robustness.json
```

Per cada candidat, genera/reprèn el CFX, supervisa el cross-check, materialitza
i exporta els 1.000 runs, construeix la traça i prova la graella de leverage de
més gran a més petita. Selecciona el primer valor que supera simultàniament
Monte Carlo, estabilitat paramètrica, PF amb costos 2× i liquidació; si cap
valor passa, conserva el leverage mínim com a evidència de `REJECT`. El
contracte reobre totes les traces de l'escaneig i recomputa que el leverage
declarat sigui realment el màxim segur preregistrat.

`small_account_economics` parteix de retorns bruts trade a trade, costat i
durada, del model de costos congelat i del rebut de robustesa anterior. Abans
del sizing cal congelar l'export de candles usat per SQ i demostrar-ne la
paritat OHLC amb Dukascopy, sense consultar rendiment:

```bash
PYTHONPATH=../.. python3 candle_source_contract_v4.py \
  --sq-candles /path/to/sq-candles.csv --sq-timezone UTC \
  --dukascopy-candles /path/to/dukascopy-candles.csv \
  --dukascopy-timezone UTC --symbol EURUSD --timeframe M15 \
  --output /path/to/candle-parity.json

PYTHONPATH=../.. python3 sq_small_account_stage_v4.py \
  --campaign-id CAMPAIGN_ID \
  --robustness-artifact /path/to/state/artifacts/05_robustness.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --candles /path/to/sq-candles.csv --candle-timezone UTC \
  --candle-contract /path/to/candle-parity.json \
  --work-dir /path/to/state/small-account \
  --artifact-output /path/to/state/artifacts/06_small_account_economics.json
```

L'stage reobre el SQX exacte del Retest, tradueix el seu stop i reconstrueix per
cada trade l'ATR de la barra anterior amb les candles congelades. També exigeix
timestamp i preu d'entrada coincidents dins del `tickStep` de l'instrument. Els
stops percentuals es conserven directament; cap stop dinàmic es reemplaça per
un escalar escrit a mà.

Amb 200 USDC, el nocional de cada operació es deriva de
`capital × risc% / stop_inicial%`. El leverage
no augmenta aquest nocional: només redueix col·lateral fins al màxim que encara
respecta marge, reserva, buffer de liquidació i l'envelope provat a robustesa.
El constructor comprova el SHA-256 del model, selecciona conservadorament el
primer bucket de nocional mesurat igual o superior a la posició i resta
round-trip i carry segons costat i dies. Recalcula PF i EV en USDC sota
base/conservador/estrès, rebutja
pèrdues individuals >3% i avalua tots els candidats supervivents. En congela un
de sol per política determinista: màxima EV del pitjor cost, després PF i ID.

## Holdout final v4

El 10% final no s'obre durant traducció, paritat o paper. Després que robustesa
i economia de 200 USDC deixin un sol candidat congelat, un únic stage escriu
l'intent de release, genera un Retest SQ uncensored, el supervisa i deriva una
traça reproduïble:

```bash
PYTHONPATH=../.. python3 sq_final_holdout_stage_v4.py \
  --campaign-id CAMPAIGN_ID \
  --small-account-artifact /path/to/state/artifacts/06_small_account_economics.json \
  --temporal-contract /path/to/temporal-split.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --candles /path/to/sq-candles.csv --candle-timezone UTC \
  --candle-contract /path/to/candle-parity.json --source-timezone UTC \
  --work-dir /mnt/volume-SQ/user/projects/ALQUIMIA_HOLDOUT_EVIDENCE \
  --artifact-output /path/to/state/artifacts/07_final_holdout_validation.json
```

El release només existeix si `small_account_economics` és PASS per un únic
candidat. El projecte SQ exigeix 1 input/1 output, cap filtre de performance,
`DeleteFailedStrategies=false` i databank `Holdout`; per tant, una estratègia
perdedora no desapareix. Els rebuts de preflight/start permeten reprendre una
interrupció sense iniciar una segona avaluació.

La traça exigeix capital 200 USDC, selecció congelada, zero canvis de
paràmetres i `holdout_evaluation_count=1`. Leverage, risc i màxim nocional
s'hereten del compte petit. Per cada trade reconstrueix el stop SQ i aplica
`min(200×risc%/stop%, nocional_màxim_congelat)`, de manera que un ATR nou no pot
superar l'envelope ja validat. El gate verifica amb SHA-256 sizing i costos,
deriva base/conservador/estrès i recalcula
sobre almenys 20 trades PF ≥1,10,
esperança neta ≥0,10 USDC per trade i drawdown ≤20% en el pitjor escenari. No
s'accepta PF no estimable sense cap trade perdedor: es valora conservadorament
com zero. Zero trades també produeix `REJECT`, no un error repetible. Qualsevol
reavaluació, retuneig, hash alterat o resum que no coincideixi amb els trades
invalida la cadena. Si falla, la família queda terminal: el holdout no es
reutilitza per buscar una variant de rescat.

## Traducció SQX a Python v4

El perfil `generic_translatable` només habilita blocs que comparteixen
extractor i runtime Python. `Highest` i `Lowest` ja estan traduïts, incloent les
set fonts SQ `ComputedFrom` (close, open, high, low, median, typical i weighted).
Operadors amb semàntica encara no provada, com `ADX`, Bollinger, desviació o
comparadors inclusius, queden fora i no poden consumir una campanya v4. `Not`
ja forma part del subset: l'extractor conserva el gate complet de cada regla
d'entrada (per exemple `short AND NOT long`) en lloc de reduir-lo a una sola
`BooleanVariable`.

Després que un únic candidat superi temporalitat, robustesa i economia del
compte petit, la traducció i el seu rebut es creen junts:

```bash
PYTHONPATH=../.. python3 python_translation_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --candidate-id EXACT_STRATEGY_NAME \
  --sqx /path/to/candidate.sqx \
  --ir-output /path/to/candidate.ir.json \
  --artifact-output /path/to/state/artifacts/08_python_translation.json
```

L'IR conserva senyals, accions, execució, hashes i complexitat, i normalitza
entrada a mercat, stop ATR/percentual, profit target i `ExitAfterBars`. Per risc
controlat, tota direcció activa ha de tenir stop; trades duplicats, trailing,
break-even dinàmic i sortides EOD/divendres fallen tancat. El runtime genera el
trace brut de trades sobre OHLC UTC: entrada a l'open del senyal, ATR de Wilder
de l'última candle completada, gaps a preu real d'open, i stop/target actius a
la candle d'entrada. Si stop i target són tocats dins la mateixa OHLC i l'ordre
no és demostrable, no inventa un resultat: rebutja el trace.

Com que l'entrada és a l'open, cada preu o indicador del senyal ha de tenir
`Shift` efectiu ≥1. El projecte SQ ho configura així i la traducció ho recalcula
des de l'AST; un SQX amb `Close[0]` o indicador equivalent falla per look-ahead.

La traducció només s'inicia després del PASS del holdout i consumeix exactament
el SQX hashat dins la seva traça reproduïble:

```bash
PYTHONPATH=../.. python3 sq_python_translation_stage_v4.py \
  --campaign-id CAMPAIGN_ID \
  --final-holdout-artifact /path/to/07_final_holdout_validation.json \
  --ir-output /path/to/candidate.ir.json \
  --artifact-output /path/to/08_python_translation.json
```

No torna a consultar ni recalcular el rendiment del holdout. El verificador
reconstrueix l'IR des del SQX, comprova que és el candidat de l'única avaluació
final PASS i exigeix coincidència exacta. Aquesta especificació executable continua
sense assumir que SQ calcula cada detall igual: la paritat posterior de
senyals, trades i PnL contra un export real d'SQ és obligatòria.

## Paritat SQ ↔ Python v4

La paritat observada es calcula exclusivament des de dos traces JSON congelats.
Cada trace identifica candidat i font (`strategyquant` o `python`) i conté
candles UTC ordenades, senyals directionals i trades amb entrada, sortida,
direcció i PnL en USDC. No s'accepten timestamps sense zona, duplicats, events
fora de les candles ni PnL no finit.

El trace SQ es pot construir des de l'`orders.csv` real, un log independent de
senyals `Timestamp;Direction`, les candles comunes i la zona horària explícita:

```bash
PYTHONPATH=../.. python3 sq_parity_trace_v4.py \
  --candidate-id EXACT_STRATEGY_NAME --orders /path/to/orders.csv \
  --signals /path/to/signals.csv --market-data /path/to/common-mt4.csv \
  --source-timezone UTC --notional-usdc 200 --output /path/to/sq.trace.json
```

No s'infereixen els senyals a partir de les ordres, perquè un senyal pot quedar
inhibit mentre ja hi ha una posició. Sense ambdues fonts observades no hi ha
paritat completa. El gate reobre també `orders.csv`, el log de senyals, les
candles i l'IR pels hashes declarats dins dels traces; una font desapareguda o
alterada invalida la paritat encara que el report agregat continuï intacte.
La documentació oficial d'SQ confirma que els blocs booleans s'avaluen a cada
barra mitjançant snippets Java, però Custom Analysis s'executa després del
backtest. La incertesa ja s'ha resolt amb un probe real i aïllat:
`sq_signal_probe_build.py` recompila només `SQ/Internal/RulesImpl/Signal.class`
contra la font exacta allowlisted de SQ 143.2708 i produeix un JAR determinista;
`sq_signal_probe_log.py` exigeix cada UUID exactament una vegada per barra,
reobre SQX/JAR/candles pels seus hashes i avalua els gates compostos. El JAR no
modifica la instal·lació ni s'utilitza per generar resultats de producció.

El smoke EURUSD D1 de 2026-08-11 va observar 2.684 barres i 10.736 booleans
(quatre variables), i va reconstruir 2.255 senyals. Amb les candles Dukascopy
de warm-up des de 2003, la finestra operable 2017-01-01–2025-07-31 i
`DontTradeOnWeekends` preservat des de l'SQX, Python coincideix amb SQ en
2.255/2.255 senyals i 86/86 trades. La correlació de PnL és 0,999999994 i
l'error màxim a nocional 200 USDC és 0,00091 USDC; l'artefacte formal retorna
`PASS`. Això certifica la traducció d'aquest subset, no la rendibilitat del
candidat (el Retest SQ és perdedor i no es promociona).

El cicle de vida segur del probe és a `sq_signal_probe_controller.py`. El
subcomandament `capture-retest` fa start→Retest supervisat→verificació→restore
amb journal durable; `status` no muta res i `restore` és la recuperació manual.
Una interrupció del supervisor deixa deliberadament el probe actiu i el journal
en `PROBE_READY`, de manera que repetir la mateixa captura reprèn la feina en
lloc de perdre-la. El contenidor normal només es restaura automàticament després
d'un Retest verificat o si falla la creació inicial del probe.

Per regenerar la traça Python amb warm-up sense operar fora de la prova:

```bash
PYTHONPATH=../.. python3 python_parity_trace_v4.py \
  --ir /path/to/candidate.ir.json --market-data /path/to/full-history.csv \
  --evaluation-start 2017-01-01T00:00:00Z \
  --evaluation-end 2025-07-31T00:00:00Z \
  --notional-usdc 200 --output /path/to/python.trace.json
```

En una campanya v4 nativa no s'invoquen manualment els dos constructors de
trace. `sq_parity_stage_v4.py` consumeix l'artefacte
`08_python_translation.json`, un Retest supervisat amb
`signal_probe_enabled=true` i l'històric complet. Normalitza el SQX post-Retest,
exigeix igualtat semàntica amb l'IR del holdout i genera un
`parity-source-bundle.json` hashat abans d'escriure `09_parity.json`. El
contracte de cadena exigeix aquest bundle; dos traces sense filiació de probe
ja no poden superar una paritat nativa.

```bash
PYTHONPATH=../.. python3 parity_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --candidate-id EXACT_STRATEGY_NAME \
  --sq-trace /path/to/sq.trace.json \
  --python-trace /path/to/python.trace.json \
  --report-output /path/to/parity.report.json \
  --artifact-output /path/to/state/artifacts/09_parity.json
```

El gate exigeix com a mínim 30 senyals i 30 trades coincidents, coincidència
exacta dels conjunts de senyals/trades, ≥95% de candles comunes i correlació de
PnL ≥0,99. La correlació sola no basta: l'error absolut mitjà ha de ser ≤0,005
USDC i el màxim ≤0,01 USDC per trade. L'informe guarda els dos hashes i la
cadena reobre els traces i recalcula totes les mètriques. Mostres buides o
petites, PnL simplement escalat i reports manuals queden rebutjats.

## Paquet paper v4

L'última etapa no desplega ni firma ordres. Construeix una configuració paper
schema v2 a partir dels artefactes PASS de preflight, economia de 200 USDC,
holdout final, traducció i paritat:

```bash
PYTHONPATH=../.. python3 paper_package_artifact_v4.py \
  --campaign-id CAMPAIGN_ID --candidate-id EXACT_STRATEGY_NAME \
  --market-preflight /path/to/01_market_preflight.json \
  --small-account-economics /path/to/06_small_account_economics.json \
  --final-holdout-validation /path/to/07_final_holdout_validation.json \
  --python-translation /path/to/08_python_translation.json \
  --parity /path/to/09_parity.json \
  --config-output /path/to/candidate.paper.json \
  --artifact-output /path/to/state/artifacts/10_paper.json
```

El paquet copia i lliga per SHA-256 el parell Ostium, leverage màxim segur,
nocional, col·lateral, risc, marge, reserva, stop, IR i report de paritat. Tots
els artefactes han de pertànyer a la mateixa campanya i candidat. La cadena
compara aquests hashes amb els rebuts reals anteriors, així que no es poden
substituir per altres JSON marcats manualment com PASS. `mode=paper`,
`live_authorized=false` i `signer_enabled=false` són obligatoris.

Proves:

```bash
python3 -m unittest -v test_discovery_inventory.py
```

## Retest temporal amb recurs desacoblat

`alquimia_retest.py` genera un CFX `pre_holdout` reproduïble per a un únic SQX.
El període cobreix train+validació+OOS però mai el holdout. No aplica filtres de
PF, trades o drawdown dins SQ i no elimina fallits: la selecció es fa després
sobre tota l'evidència, sense censura. Rebutja recursos ambigus i lliga el nom i
hash del candidat al manifest.

```bash
python3 alquimia_retest.py \
  --source /path/to/retest-template.cfx \
  --resource-source /path/to/discovery-with-market-resource.cfx \
  --resource-task-file Build-Task1.xml \
  --slippage 400 \
  --test-precision 4 \
  --money-management fixed_size --fixed-size 1 \
  --candidate-sqx /path/to/EXACT_STRATEGY.sqx \
  --candidate-id EXACT_STRATEGY_NAME \
  --output /path/to/pre-holdout.cfx \
  --name CAMPAIGN_PRE_HOLDOUT --stage pre_holdout \
  --discovery-manifest /path/to/discovery.manifest.json \
  --methodology methodology_v2.json \
  --symbol EXACT_SQ_SYMBOL --timeframe H4
```

Execució observada i export d'ordres:

```bash
PYTHONPATH=../.. python3 sqcli_supervised_retest.py \
  --cfx /path/to/pre-holdout.cfx \
  --manifest /path/to/pre-holdout.manifest.json \
  --output-dir /path/to/evidence/retest/EXACT_STRATEGY_NAME
```

El supervisor exigeix un projecte nou i resolt, copia exactament un SQX a
`Results`, observa al log `Results (1) -> PreHoldout (1)` i `Total tested: 1`,
comprova l'`orders.bin` de sortida i invoca l'export oficial SQCLI
`tools action=orderstocsv`. El rebut és idempotent i no autoritza paper ni live.

Per executar tota l'etapa temporal sobre els candidats d'un artefacte
`sq_generation` real:

Quan la generació prové de diverses hipòtesis, primer es congela un únic
univers global. Això evita calcular un Pareto per branca i promocionar un
candidat que en realitat queda dominat per un rival d'una altra branca:

```bash
PYTHONPATH=../.. python3 sq_generation_universe_v4.py \
  --campaign-id CAMPAIGN_ID \
  --generation-artifact BREAKOUT /path/to/breakout/sq_generation.json \
  --generation-artifact MOMENTUM /path/to/momentum/sq_generation.json \
  --generation-artifact REVERSION /path/to/reversion/sq_generation.json \
  --output /path/to/state/global_sq_generation.json
```

L'agregador reobre cada SQX, comprova identitat i hash, conserva també les
branques `REJECT`, deduplica només SQX idèntics i rebutja una mateixa identitat
amb bytes diferents. El worker EURUSD crea i hasha aquest artefacte
automàticament abans de declarar completada la generació.

```bash
PYTHONPATH=../.. python3 sq_temporal_stage_v4.py \
  --campaign-id CAMPAIGN_ID \
  --generation-artifact /path/to/state/artifacts/03_sq_generation.json \
  --retest-template /path/to/retest-template.cfx \
  --resource-source /path/to/discovery-resource.cfx \
  --resource-task-file Build-Task1.xml \
  --discovery-manifest /path/to/discovery.manifest.json \
  --temporal-contract /path/to/temporal-split-contract.json \
  --cost-model /path/to/frozen-ostium-costs.json \
  --symbol EXACT_SQ_SYMBOL --timeframe D1 --source-timezone UTC \
  --work-dir /path/to/state/temporal-retests \
  --artifact-output /path/to/state/artifacts/04_temporal_validation.json
```

L'adaptador reobre els SQX i els seus hashes, crea un projecte amb nom derivat
de campanya+candidat, reprèn els checkpoints de cada Retest, deriva els traces
des dels rebuts i finalment aplica el Pareto temporal. El manifest de discovery
i el contracte temporal són entrades diferents: el primer configura dates SQ;
el segon classifica i segella trades. No s'han d'intercanviar.

En la campanya EURUSD aquest pas no requereix una ordre manual.
`eurusd_v4_temporal_worker.py` verifica el rebut del worker d'SQ, reconstrueix
costos, dates, manifest i recurs des del `bootstrap`, espera projectes SQ aliens
i reprèn només un Retest propi amb preflight durable. El mateix script i `flock`
del cron executen generació i després validació temporal, de manera que no poden
competir entre ells. Un `REJECT_NO_SQ_CANDIDATES` és terminal i no inicia SQ.

Si el Pareto temporal passa, `eurusd_v4_robustness_worker.py` continua sota el
mateix lock. El límit no és un `200x` escrit a mà: exigeix 30 observacions
congelades del parell Ostium 2 EUR/USD, adopta el mínim observat de
`max_leverage` i escaneja la graella preregistrada de dalt a baix. Per Forex,
`overnightMaxLeverage=0` no substitueix el límit general: és l'absència de
l'override especial de day trading d'accions. Aquesta interpretació queda
limitada explícitament a `category=forex`; qualsevol valor overnight no nul o
evidència insuficient falla tancat. La documentació oficial descriu aquesta
restricció com a específica de les accions:
https://ostium-labs.gitbook.io/ostium-docs/stocks-day-trading

Robustesa utilitza la metodologia segellada per l'artefacte temporal, no el
fitxer actual del repositori. Això impedeix modificar inadvertidament els gates
entre el Pareto i les 1.000 variants natives d'SQ.

Els supervivents passen automàticament a
`eurusd_v4_small_account_worker.py`. El contracte
`evidence/eurusd_d1_full_candle_parity_v4.json` reobre 5.884 sessions NY-17
entre 2003-05-05 i 2026-02-26: l'export d'SQ i la font D1 construïda des del
Parquet Dukascopy tenen cobertura OHLC i coincidència del 100%. SQ només canvia
el volum 0 d'una sessió festiva a 1; el sizing no usa volum. Per cada trade es
reconstrueix el stop inicial des de la regla SQ i la candle anterior, s'aplica
1,5% de risc sobre 200 USDC i es comproven costos, marge ≤35%, reserva ≥40%,
buffer stop→liquidació ≥1,5 i l'envelope de leverage que havia superat
robustesa. Cap leverage superior al provat per Monte Carlo pot ser seleccionat.

`eurusd_v4_holdout_worker.py` és l'únic component que pot crear la intenció
d'obertura del holdout. Exigeix exactament un candidat `PASS_SMALL_ACCOUNT`,
fonts congelades i cobertura de candles fins al darrer dia del segment. A
2026-08-11 el contracte verificat arriba a 2026-02-26 però el holdout acaba a
2026-07-31; per tant retorna `WAITING_FOR_HOLDOUT_CANDLE_COVERAGE`, amb comptador
d'avaluacions 0, i no genera ni importa cap CFX. Quan la font s'actualitzi,
l'execució serà única, uncensored i reprenable; un resultat negatiu serà
terminal i no permetrà retuning.

Després d'un `PASS_FINAL_HOLDOUT`, el mateix worker cron executa dues portes
addicionals, sense cap pas manual. `eurusd_v4_translation_worker.py` tradueix
només el SQX exacte lligat a aquella única avaluació i segella l'IR canònic.
`eurusd_v4_parity_worker.py` reobre per hash tota la filiació
temporal→robustesa→sizing→holdout→traducció, genera un Retest pre-holdout net i
captura els senyals per barra amb el JAR de probe verificat. El controlador
atura l'SQCLI normal només quan està lliure, restaura el servei després de la
captura i exigeix aquesta restauració abans de comparar SQ amb Python. Una
recepció final existent es revalida i es retorna sense tornar a tocar Docker.

```bash
./scripts/run_eurusd_v4_sq_worker.sh
```

La sortida normal mentre la campanya encara no té guanyador acaba en
`WAITING_FOR_TRANSLATION`. Ni traducció ni paritat autoritzen paper o live. Un
`PASS_PARITY` només habilita la construcció posterior d'un paquet paper-only;
no inicia el motor paper ni habilita un signer.

La construcció posterior també és part del mateix pipeline:
`eurusd_v4_paper_package_worker.py` recupera el preflight congelat i segueix
els enllaços hashats fins a sizing, holdout, traducció i paritat. Escriu
`10_paper.json` i una configuració `*.paper.json` només si
`verify_package()` pot reconstruir-ne tot el contracte. El rebut final fixa
`paper_configured=true`, però conserva sempre `paper_started=false`,
`signer_enabled=false` i `live_authorized=false`. Configurar el paquet no
equival a executar-lo; l'arrencada futura del paper probe requerirà una porta
operativa separada i explícita.

Un candidat sense trades, sense OOS o amb expectativa train no positiva és
evidència científica vàlida però feble: queda registrat amb
`temporal_eligibility_failure` i acaba en `REJECT`, sense avortar el lot. En
canvi, un hash incorrecte, un CSV sense esquema, una frontera/holdout violada o
un rebut no reproduïble continua sent una fallada operativa tancada.
