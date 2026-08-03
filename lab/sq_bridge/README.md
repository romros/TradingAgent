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
