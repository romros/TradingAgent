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
veïnat i trades bruts amb costat i durada, i construeix el rebut:

```bash
PYTHONPATH=../.. python3 hypothesis_screen_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --trace /path/to/hypothesis-screen.trace.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --artifact-output /path/to/state/artifacts/02_hypothesis_screen.json
```

Només train és visible. El nocional canònic del screen és 200 USDC; el
constructor verifica el model congelat, recomputa round-trip i carry, recompte
els intents reals i recalcula PF
per variant i exigeix que la central i almenys dos veïns superin 50 trades i PF
1,20 sota tots tres costos. Una hipòtesi rebutjada no arriba a SQCLI.

El `market_preflight` observat que precedeix aquest screen no es valida només
amb els seus totals. Conserva `campaign_config_path` i SHA-256; el contracte
reexecuta el compositor sobre cobertura històrica, mapping i costos congelats.
VIX o un altre estat de règim és opcional, però quan existeix també forma part
de les fonts hashades i ha de respectar el timing anti-look-ahead.

Per a una campanya v4, el rebut de `sq_generation` no s'escriu a mà. Després de
congelar el databank i el recompte real d'intents, es genera així:

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

`sq_generation` conserva tots els candidats únics que compleixen el subset de
traducció i el límit estructural; no declara un fals «millor candidat» a partir
del fitness intern d'SQ. El front Pareto promocionable es calcula a
`temporal_validation`, quan ja existeixen expectativa neta amb costos,
drawdown OOS i estabilitat entre finestres. El rebut temporal ha d'incloure
l'univers complet rebut d'SQ i el validador recalcula tant els dominats com els
IDs seleccionats.

Cada candidat aporta un trace `temporal_validation_trade_trace` amb capital i
nocional comparatiu de 200, retorn brut, costat, durada, trades train i
finestres OOS UTC no solapades.
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
més veïns paramètrics a ±10%, PnL trade a trade amb costos 2×, leverage provat,
límit Ostium i excursió adversa màxima de cada run:

```bash
PYTHONPATH=../.. python3 robustness_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --trace /path/to/candidate-a.robustness.trace.json \
  --artifact-output /path/to/state/artifacts/05_robustness.json
```

El constructor recomputa proporció Monte Carlo rendible, estabilitat dels veïns,
PF estressat i liquidacions. Aquestes últimes no són booleans acceptats de la
font: es deriven de l'excursió adversa, leverage i límit del mercat. El sizing
posterior no pot usar més leverage ni un límit de venue diferent del provat.

`small_account_economics` parteix de retorns bruts trade a trade, costat i
durada, del model de costos congelat i del rebut de robustesa anterior:

```bash
PYTHONPATH=../.. python3 small_account_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --trace /path/to/candidate-a.small-account.trace.json \
  --robustness-artifact /path/to/state/artifacts/05_robustness.json \
  --cost-model /path/to/eurusd_costs_frozen_v4.json \
  --artifact-output /path/to/state/artifacts/06_small_account_economics.json
```

Amb 200 USDC, el nocional es deriva de `capital × risc% / stop%`. El leverage
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
i economia de 200 USDC deixin un sol candidat congelat, es crea una única
avaluació amb un trace de trades ordenats i PnL net per cost:

```bash
PYTHONPATH=../.. python3 final_holdout_artifact_v4.py \
  --campaign-id CAMPAIGN_ID \
  --candidate-id EXACT_STRATEGY_NAME \
  --trace /path/to/final-holdout.trace.json \
  --artifact-output /path/to/state/artifacts/07_final_holdout_validation.json
```

El trace exigeix capital 200 USDC, selecció congelada, zero canvis de
paràmetres, `holdout_evaluation_count=1` i exactament els costos base,
conservador i estrès. El gate recalcula sobre almenys 20 trades PF ≥1,10,
esperança neta ≥0,10 USDC per trade i drawdown ≤20% en el pitjor escenari. No
s'accepta PF no estimable sense cap trade perdedor. Qualsevol reavaluació,
retuneig, hash alterat o resum que no coincideixi amb els trades invalida la
cadena. Si falla, la família queda terminal: el holdout no es reutilitza per
buscar una variant de rescat.

## Traducció SQX a Python v4

El perfil `generic_translatable` només habilita blocs que comparteixen
extractor i runtime Python. Operadors amb semàntica encara no provada, com
`Highest`, `Lowest`, `ADX`, Bollinger, desviació, `Not` o comparadors inclusius,
queden fora i no poden consumir una campanya v4. Qualsevol indicador amb un
`ComputedFrom` diferent del close canònic també falla tancat.

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

L'IR conserva senyals, accions, execució, hashes i complexitat, i
`strategy_ir_runtime.py` executa els senyals sobre OHLC amb un índex temporal
creixent. La traducció no consulta el holdout. El verificador reconstrueix l'IR
des del SQX i exigeix coincidència exacta, però això encara no prova que els
càlculs numèrics siguin idèntics als d'SQ: la paritat posterior de senyals,
trades i PnL continua sent obligatòria.

## Paritat SQ ↔ Python v4

La paritat observada es calcula exclusivament des de dos traces JSON congelats.
Cada trace identifica candidat i font (`strategyquant` o `python`) i conté
candles UTC ordenades, senyals directionals i trades amb entrada, sortida,
direcció i PnL en USDC. No s'accepten timestamps sense zona, duplicats, events
fora de les candles ni PnL no finit.

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

`alquimia_retest.py` pot reutilitzar una plantilla Retest i importar-hi un únic
recurs de mercat verificat des d'un altre CFX. Rebutja absències o coincidències
ambigües, no modifica els CFX originals i registra al manifest els hashes de la
plantilla, del recurs i del resultat.

```bash
python3 alquimia_retest.py \
  --source /path/to/retest-template.cfx \
  --resource-source /path/to/discovery-with-market-resource.cfx \
  --resource-task-file Build-Task1.xml \
  --slippage 400 \
  --test-precision 4 \
  --money-management fixed_size --fixed-size 1 \
  --output /path/to/validation.cfx \
  --name CAMPAIGN_VALIDATION --stage validation \
  --discovery-manifest /path/to/discovery.manifest.json \
  --methodology methodology_v2.json \
  --symbol EXACT_SQ_SYMBOL --timeframe H4
```
