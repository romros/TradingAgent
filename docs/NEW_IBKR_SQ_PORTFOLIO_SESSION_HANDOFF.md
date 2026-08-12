# Handoff de sessió — cartera teòrica SQCLI amb univers nou

**Actualitzat:** 2026-08-12
**Estat:** preparat per iniciar una campanya nova; no hi ha cap candidata nova
promoguda encara.

Aquest és el manual de reentrada. Una sessió nova no ha d'intentar reconstruir
la intenció a partir dels centenars d'artefactes antics: ha de llegir primer
`CURRENT_OBJECTIVE.md` i després aquest document.

Mapa d'evidència i ordre de famílies:
`docs/EVIDENCE_BASED_STRATEGY_FAMILIES.md`.

## 1. Objectiu, en llenguatge planer

Volem saber si SQCLI pot trobar una cartera teòrica realment sòlida i agressiva
per a capital petit, fent servir **actius nous que IBKR ofereixi públicament**.
Primer provem que les estratègies tenen mèrit estadístic i econòmic. Només si
ho demostren invertirem temps a connectar IBKR o BrokerageService.

El broker no crea l'avantatge: només executaria una cartera ja validada. El
leverage tampoc crea avantatge; amplifica tant el guany com l'error i només es
pot calcular després de conèixer distribució de pèrdues, mida mínima i costos.

## 2. Abast exacte

Inclòs:

- StrategyQuant/SQCLI al màxim ús segur de CPU, amb monitoratge i checkpoints;
- actius tradicionals nous: ETFs, accions, índexs, futurs, FX o metalls només
  si no pertanyen a l'univers antic i hi ha dades adequades;
- D1 com a embut inicial; H4/H1/M30 només per a famílies prometedores o una
  hipòtesi intradia preregistrada;
- cerca random per explorar i genètica per aprofundir quan hi hagi senyal;
- estratègies long, short, sessions i sortides diferents quan la hipòtesi ho
  justifiqui;
- costos base, conservadors i d'estrès; Monte Carlo; walk-forward; pertorbació
  de paràmetres; precisió superior; reproducció Python;
- cartera de 4–8 estratègies només si totes mereixen entrar-hi.

Exclòs de la fase actual:

- IB Gateway, TWS, API privada, permisos del compte i adaptadors d'execució;
- paper i live;
- criptoactius;
- Yahoo com a font certificada;
- qualsevol candidat o holdout de l'etapa Ostium/Alquímia.

## 3. Mur de separació respecte del projecte anterior

Com a mínim queden exclosos US500/IBUS500/SPY, QQQ/NDX, NVDA, EURUSD,
XAU i TLT. La regla general és més forta: **qualsevol actiu que s'hagués
investigat per a Ostium queda fora**, llevat que l'operador el reautoritzi de
manera explícita en el futur.

Reautorització explícita 2026-08-12: AAPL, GOOGL, MSFT i TSLA formen una cohort
mega-cap nova. No es pot reutilitzar cap performance, candidat, paràmetre ni
holdout antic. `MSFT` antic/Yahoo queda prohibit; cal certificar `MSFTUSUSD`
Dukascopy des de zero. AAPL i TSLA tenen recursos locals grans però no es poden
usar fins auditar-los. GOOGL encara no està importada.

No executar el worker EURUSD antic: ja va acabar el filtre determinista amb
`REJECT` (0 seleccionades de 27). No estava pendent d'SQCLI.

La recerca US500/SPY també està tancada. Va aportar dues regles interessants al
proxy, però el mapping i l'economia del vehicle petit no van aguantar. La
descoberta directa SPY va retornar 0/10.015 i 0/11.155. És una lliçó, no una
candidata.

## 4. Estat operatiu verificat

- SQCLI: saludable i amb zero projectes actius després de l'últim smoke test.
- Neteja: eliminats 4.265 JAR regenerables de `internal/tmp/stock`; recuperats
  aproximadament 3,05 GB del disc arrel.
- `internal/testfiles`: intacte perquè era recent; no eliminar-lo per defecte.
- Imatge `sqcli-sqcli:latest`: intacta i necessària.
- `/mnt/volume-SQ`: tenia aproximadament 2,8 GB lliures (93% ocupat); cal
  pressupostar la mida abans d'importar nous històrics.
- Dashboard conegut: `http://127.0.0.1:8765` si el servei continua actiu.
- Evidència de neteja:
  `data/ibkr_sq_v1/maintenance/sqcli_cleanup_20260812.json`.
- Dry-run segur:
  `scripts/maintenance/sqcli-safe-cleanup.sh --dry-run`.

L'estat anterior s'ha de tornar a verificar; no s'ha de donar per cert en una
sessió futura.

## 5. Procediment exacte en començar una sessió

```bash
cd /mnt/volume-SQ/dev/TradingAgent
pwd
sed -n '1,240p' CURRENT_OBJECTIVE.md
sed -n '1,320p' docs/NEW_IBKR_SQ_PORTFOLIO_SESSION_HANDOFF.md
git status --short
docker ps --filter name=sqcli-docker
df -h /mnt/volume-SQ /
scripts/maintenance/sqcli-safe-cleanup.sh --dry-run
```

Després:

1. Comprovar amb SQCLI que no hi hagi cap projecte actiu abans de crear-ne un.
2. No modificar ni netejar canvis aliens. Verificar sempre el worktree abans
   d'afegir-hi resultats nous i consolidar cada bloc amb un commit coherent.
3. Revisar si l'Acadèmia ha incorporat coneixement nou rellevant, però sense
   deixar que això substitueixi les proves.
4. Crear primer el registre versionat de l'univers nou i la procedència de les
   dades; encara no llançar una cerca massiva.

## 6. Registre inicial creat i següent lliurable

El registre machine-readable separat de l'univers antic ja és
`lab/sq_bridge/ibkr_new_universe_v2.json`. El seu validador és
`lab/sq_bridge/validate_ibkr_new_universe_v2.py`. Conté tretze candidats: CAT,
JPM, JNJ, KO, IWM, EEM, EFA, XLE, XLF i la cohort reautoritzada AAPL, GOOGL,
MSFT i TSLA. Les accions tenen prioritat; els ETFs queden marcats per a una
futura comprovació PRIIPs.

Cada fila incorpora:

- identificador canònic i símbol públic d'IBKR;
- classe d'actiu i mercat;
- prova/URL pública que apareix al catàleg d'IBKR i data de consulta;
- marca `NEW_VS_OSTIUM=true` amb evidència de la comparació;
- font, zona horària, sessió, ajustos i cobertura de dades;
- disponibilitat local a SQ i cost estimat d'importació en disc;
- estat: `CATALOG_CANDIDATE`, `DATA_READY`, `PREREGISTERED`, `REJECTED`;
- motiu de rebuig, si escau.

La cobertura general al web d'IBKR **no prova** que un resident a Espanya tingui permís
per comprar aquell instrument (per exemple, poden intervenir PRIIPs o el tipus
de compte). Aquesta comprovació queda ajornada fins al `THEORETICAL_PASS`.

La validació local confirma que tots tretze existeixen al catàleg Dukascopy d'SQ i
que cap coincideix amb la llista d'exclusions coneguda. Això encara no certifica
l'històric. El següent lliurable és el `DATA_PREFLIGHT` dels quatre priority-1:
pressupost de disc, importació, cobertura, buits, timezone, sessions i ajustos
corporatius abans de definir cap campanya.

### Resultat del primer preflight CAT

El 2026-08-12 s'ha provat CAT sense consultar cap performance:

- el feed públic BI5 Dukascopy ha fallat principalment amb HTTP 503; els dos
  intents són al journal i no han publicat cap partició parcial com a completa;
- el Data Manager natiu d'SQ ha acceptat crear `CATUSUSD` i iniciar l'update,
  però només ha escrit 8 KB, sense missatge final ni D1 exportable;
- repetir l'exportació amb el directori temporal creat prèviament també retorna
  zero fitxers, de manera que no era un error del path;
- la llicència observada és `StrategyQuant X Pro Build 143 (Trial)`, vàlida
  fins al 2026-08-22. Segons el suport oficial d'SQ, Professional necessita una
  subscripció separada per dades d'equities; és la causa probable, no provada;
- en aquell punt CAT va quedar provisionalment `BLOCK_SOURCE_NOT_COMPLETE`;
- evidència: `data/ibkr_sq_v2/preflight/cat_data_preflight_20260812.json`;
- es va impedir afegir JPM/JNJ/KO o iniciar Builder abans de resoldre la font.

Aquest bloqueig inicial s'ha superat parcialment amb una ruta pròpia BI5
millorada. El feed recent 2026 fallava, però dies antics de 2018/2020/2024
responen. L'arxivador ara té escala explícita, cache diària atòmica, retries
només dels dies pendents, data inicial de catàleg i calendari NYSE 2017–2025.

Resultat CAT 2017 (maig–desembre):

- 8 mesos complets i hashats;
- 234.720 M1 únics, zero duplicats;
- 163 sessions RTH `America/New_York`;
- totes les sessions amb exactament 390 minuts;
- D1 RTH hash `a789be47…`;
- decisió `PASS_YEAR_PILOT_SOURCE_ONLY`.

Evidència canònica:
`data/ibkr_sq_v2/preflight/cat_2017_mechanical_preflight.json`. CAT encara no
és `DATA_READY`: falten 2018–2025, ajustos de splits/dividends, particions
temporals congelades i round-trip d'SQ. JPM/JNJ/KO continuen esperant.

Checkpoint de descàrrega 2018 actualitzat després de la represa:

- gener–juliol: 7 mesos complets amb manifest;
- agost: només el 27/08 continuava pendent en l'última passada;
- setembre: parcial en cache; el feed es va degradar amb 503/timeouts i es va
  aturar voluntàriament abans d'octubre;
- octubre–desembre: encara no iniciats;
- total CAT local (mesos + cache): aproximadament 6,5 MB;
- cap procés de descàrrega queda actiu.

Ordre segura de represa (salta mesos complets i conserva cache):

```bash
python3 lab/sq_bridge/dukascopy_m1_archive.py \
  --root data/ibkr_sq_v2/dukascopy_m1 \
  --symbol CATUSUSD --from-year 2018 --to-year 2018 \
  --price-scale 1000 --market-calendar nyse --workers 8 \
  --journal data/ibkr_sq_v2/dukascopy_m1/CATUSUSD/download.jsonl
```

Quan els 12 mesos tinguin manifest, tornar a executar
`ibkr_us_equity_data_preflight_v2.py` i exigir zero duplicats i 390 minuts per
sessió abans de començar 2019.

Una acció completa comparable (AAPL/TSLA) ocupa aproximadament 1,3 GB perquè SQ
conserva ticks. El disc arrel disposava de ~87,6 GB i ho pot suportar, però
`/mnt/volume-SQ` només ~2,97 GB: els historials complets no s'han d'escriure al
volum de treball. S'importa un actiu cada vegada i es verifica abans del següent.

## 7. Contracte de cada campanya SQ

Abans de veure performance s'ha de congelar:

- hipòtesi econòmica i condició que la falsaria;
- actiu, timeframe, sessió i direcció;
- períodes train, validation i OOS/holdout segellat;
- blocs d'entrada i sortida autoritzats;
- límit de complexitat i nombre màxim de regles;
- costos i slippage en tres escenaris;
- mínim de trades per tram;
- gates de PF, estabilitat, drawdown i expectativa;
- pressupost de CPU/temps i regla d'aturada per manca de convergència;
- hash de projecte, dades i configuració.

La cerca random serveix per saber si una família té densitat de solucions. La
genètica només s'empra després per explotar una zona prometedora, mantenint
diversitat i una validació que no participa en l'evolució. No s'ha d'optimitzar
una família inviable indefinidament.

## 8. Embut de promoció

```text
univers nou verificat
 → dades certificades i mapping temporal
 → preregistre immutable
 → descoberta SQ en train
 → validation completa sense censura
 → OOS/holdout una sola vegada
 → precisió superior i paritat de trades
 → costos i slippage base/conservador/estrès
 → Monte Carlo i risc de ruïna
 → pertorbació de paràmetres
 → walk-forward quan sigui informatiu
 → reproducció independent en Python
 → correlació, solapament i concurrència de cartera
 → capital i compounding teòrics
 → THEORETICAL_PASS o NO_CANDIDATE
```

Cap candidat es promociona només per tenir un backtest bonic. Cal guardar també
els rebutjats, perquè provar molts sistemes i ensenyar només el millor genera
biaix de selecció.

## 9. Criteris mínims de cartera i capital

Els llindars numèrics definitius s'han de preregistrar segons classe d'actiu i
freqüència. En tot cas s'exigeix:

- expectativa neta positiva en validation i OOS;
- prou operacions perquè el resultat no depengui de tres encerts;
- drawdown i risc de ruïna compatibles amb la fase de capital;
- supervivència a costos conservadors i d'estrès;
- estabilitat temporal i paramètrica;
- poca dependència d'una sola crisi, règim o any;
- diversificació per font d'alpha, no només per ticker;
- sizing viable amb unitats senceres o fraccionàries, que es comprovarà amb el
  contracte real després del pass teòric.

Cal modelar 200, 400, 500, 700, 1.000 i 2.000 de capital, però sense afirmar que
el broker permet aquella execució. L'objectiu de x2 o 50% anual és una aspiració
i un escenari; mai una garantia ni un gate que autoritzi sobreajustament.

## 10. Mecanismes contra perdre hores de càlcul

- un projecte per campanya i noms immutables;
- manifests i hashes abans d'executar;
- exportació periòdica del databank i dels millors candidats;
- heartbeat amb fase, generació, velocitat, acceptats i temps sense millora;
- watchdog que alerta però no mata una execució que encara escriu/progressa;
- snapshots atòmics fora dels directoris temporals d'SQ;
- resum HTML derivat dels artefactes, mai com a única font de veritat;
- tancament explícit amb `PASS`, `REJECT`, `NO_CANDIDATE` o `FAILED_CONFIG`;
- neteja només quan no hi ha projectes actius i després d'un smoke test.

## 11. Regla d'aturada i recalibratge

No hi ha un timeout universal. Per campanya es defineix un pressupost inicial i
es mira la corba de millora: acceptats nous, diversitat, millor validation i
temps des de l'última millora material. Si diverses finestres consecutives no
milloren i la densitat de supervivents és nul·la, es tanca `NO_CANDIDATE`.

La següent prova ha de canviar una hipòtesi material —actiu, règim, família,
direcció o timeframe—, no només allargar el mateix procés o afluixar els gates.

## 12. Arxiu històric útil, però no actiu

- `docs/IBKR_D1_DOWN_FUNNEL.md`: què va passar a US500/SPY.
- `data/ibkr_sq_v1/temporal_d1_v3/`: evidència temporal del proxy antic.
- `data/ibkr_sq_v1/spy_transfer_v1/`: prova de transferència rebutjada.
- `docs/SQ_CAMPAIGN_STOPPING_AND_HANDOFF.md`: idees reutilitzables d'aturada.
- `docs/SQCLI_CLEANUP_AND_IMAGE_AUDIT.md`: política de manteniment.
- `lab/docs/SMALL_INVESTOR_RESEARCH_PROTOCOL.md`: metodologia general, filtrant
  qualsevol literal o dependència d'Ostium.

## 13. Definició de final de la fase

La fase acaba quan hi ha un paquet reproduïble amb:

1. cartera de supervivents o declaració honesta `NO_CANDIDATE`;
2. projectes SQ, configuracions, hashes i resultats íntegres;
3. paritat Python i taula de robustesa;
4. escenaris de capital/compounding i riscos, sense promeses;
5. explicació econòmica i contextual per períodes històrics;
6. decisió escrita sobre si val la pena començar la fase IBKR.

Fins aleshores no es construeix infraestructura de broker. La següent acció
concreta és **estendre CAT 2018–2025, un any cada vegada, i certificar ajustos
corporatius abans de preregistrar performance**. JPM, JNJ i KO
esperen; no toca una cerca SPY/EURUSD ni un adaptador d'ordres.
