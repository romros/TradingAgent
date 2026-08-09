# Auditoria de recerca SPX/USD M15

Data de tall: 8 d'agost de 2026.

## Decisió actual

**SPX/USD M15 continua habilitat com a mercat de recerca, però no hi ha cap
estratègia SPX promocionable a SQCLI, paper trading o live.**

S'han falsificat tres famílies diferents. Aplicar més palanquejament no les pot
rescatar perquè no tenen expectativa positiva després dels costos.

## Què està verificat

### Dades i mapping

- Símbol StrategyQuant: `SP_M1_dukas` (`USA500.IDX_dukascopy`).
- Parell Ostium corresponent: `SPX/USD`, mostrat com `US500/USD`.
- Exportació SQ: 3.977.597 barres M1, del 19/01/2012 al 08/07/2026.
- SHA-256 CSV: `9fccccbffc2860cab7e788dc608374baf4f81d5e203915955021249efd54b289`.
- Rellotge d'origen: broker `America/New_York+07`, normalitzat a UTC amb DST dels EUA.
- Solapament M15 SQ/Ostium 2026: 7.176 barres completes, cobertura 95,81%,
  correlació de retorns 0,9895, coincidència direccional 96,71% i desviació
  p95 del close 8,79 bps.
- M15 passa el gate de mapping per a recerca. H1 i H4 no el passen.

El CSV i el parquet no es versionen perquè són dades voluminoses. Es versionen
el rebut, els hashes i els experiments reproduïbles.

### Economia Ostium confirmada

- La consulta anterior de documentació indicava 3 bps i 200x; queda **obsoleta**
  per a decisions actuals.
- Captura read-only de l'SDK oficial `@ostium/builder-sdk 0.7.0` el 08/08/2026:
  fee d'obertura 1 bp, tancament 0, leverage màxim 100x, mínim nocional 5 USD i
  `overnightMaxLeverage=0` (cap restricció overnight segons els tipus de l'SDK).
- Comissió de tancament: 0 bps.
- Oracle: 0,10 USDC; es retorna després d'un tancament complet reeixit.
- Execució bid/ask: el spread s'ha d'afegir al backtest.
- Rollover continu: per als índexs depèn de SOFR més prima de carry.
- En la captura amb mercat tancat: spread 0,9672 bps i impacte simulat 0,4836
  bps entre 10 i 1.000 USD de nocional. Són una observació, no percentils de sessió.
- Rollover live per 8 h en aquella captura: long −0,0052122% (cobra) i short
  +0,00154884% (paga); pot canviar amb el mercat.
- Horari publicat: diumenge 18:00 ET fins divendres 17:00 ET, amb pausa diària
  17:00–18:00 ET. La sèrie Dukascopy disponible és principalment sessió americana.

Per a recerca es mantenen els escenaris totals conservadors de 8, 15 i 30 bps.
`getPairs()`, slippage i rollover ja es capturen, però encara falten almenys 30
mostres amb mercat obert, tres dies i sis hores UTC diferents abans de congelar
percentils base/conservador/estrès. Paper continua bloquejat.

## Famílies provades

| Família | Intents | Gate/resultat | Decisió |
|---|---:|---|---|
| Gap i opening drive | 144 | 0 passen desenvolupament a 15 bps | Descartar |
| Compressió → ruptura de canal | 1.728 | 0 passen; els pics tenen només 3–5 trades | Descartar |
| Pullback RSI dins tendència EMA | 1.944 | 0 passen; 790 punts tenen ≥100 trades, millor PF base 0,51 | Descartar |
| Flux final/inici de mes | 20 | 0 passen; millor PF base 1,43 però només 4/7 anys, estrès PF 1,019 i 3/7 anys | Descartar |

Total: **3.836 configuracions deterministes**, sense comptar SQ Builder perquè cap
família va superar el filtre Python previ.

### 1. Gap i opening drive

Es van separar continuació/reversió, long/short, dies de la setmana i sortides
15:30/15:59 ET. Cap configuració cobreix 15 bps en desenvolupament.

Incident metodològic: la primera implementació va calcular 2023–2025 abans
d'aplicar el gate. Aquest període queda contaminat per a aquesta família i els
resultats es van descartar. El 2026 no es va consultar.

### 2. Compressió i expansió

Combinava rang de compressió, quantil de volatilitat, canal, stop ATR, durada,
hora i direcció. Els PF aparentment elevats provenien de 3–5 trades en set anys;
no hi ha mostra suficient ni regió estable.

### 3. Pullback dins tendència

Combinava EMA 50/100, RSI 2/3/5, extrems RSI, stop i objectiu ATR, durada i
finestra horària. És la falsificació més concloent:

- 790 punts tenen almenys 100 trades;
- millor PF amb costos base de 8 bps: 0,512288;
- millor PF amb estrès de 30 bps: 0,075728.

Per tant, el fracàs no és només baixa freqüència. El mecanisme té expectativa
negativa amb una mostra àmplia.

## Estat de les finestres

| Període | Estat | Ús permès |
|---|---|---|
| 2012–2018 | Desenvolupament | Ja utilitzat |
| 2019–2022 | Validació | No consultat per v2/v3 |
| 2023–2025 | Contaminat per v1 | No usar com a OOS cec de v1 |
| 2026 | Holdout segellat | No obrir sense finalista preregistrat |

No s'ha d'obrir validació ni holdout per «confirmar» famílies que ja fallen en
desenvolupament.

## Què significa per a un compte de 200–500 USDC

Amb risc de l'1%, el nocional depèn de la distància de l'stop, no del desig
d'obtenir més rendiment. Per exemple, amb 200 USDC:

| Stop | Risc | Nocional | Exposició/capital | Comissió d'obertura |
|---:|---:|---:|---:|---:|
| 1,00% | 2 USDC | 200 USDC | 1x | 0,06 USDC |
| 0,50% | 2 USDC | 400 USDC | 2x | 0,12 USDC |
| 0,25% | 2 USDC | 800 USDC | 4x | 0,24 USDC |

El leverage pot reduir el collateral necessari, però no converteix PF inferior a
1 en una estratègia rendible. No hi ha una projecció de compounding SPX honesta
fins tenir expectativa OOS neta, drawdown, freqüència i risc de ruïna.

## Següent pas únic

**Mesurar l'economia live d'SPX/USD abans d'obrir una quarta família:**

1. executar `scripts/capture_ostium_spx_economics.sh` durant mercat obert;
2. arribar a 30 mostres, tres dies i sis hores UTC diferents;
3. congelar p50/p95/màxim de spread i slippage en els escenaris de costos.

El collector automàtic s'instal·la amb `scripts/install_ostium_spx_capture_cron.sh`.
Mostreja cada dues hores de dilluns a divendres, usa un lock anti-solapament i
desa dades regenerables a `data/ostium_economics/`, fora de Git.

Després cal formular un mecanisme econòmic nou amb un input extern justificat,
per exemple règim de volatilitat preregistrat. No s'han de tornar a ajustar RSI,
EMA, gap, opening drive, compressió o dies de final de mes per rescatar experiments.

## Artifacts reproduïbles

- Dades: `lab/sq_bridge/evidence/sp_m1_dukas_utc_2012_2026_source.json`
- Mapping: `lab/sq_bridge/evidence/spxusd_sq_ostium_parity_2026_extended_common.json`
- Economia: `lab/sq_bridge/spxusd_execution_economics.py`
- Capturador: `scripts/capture_ostium_spx_economics.sh`
- Gate agregat: `lab/sq_bridge/evidence/spxusd_ostium_execution_summary_latest.json`
- Sessió v1: `lab/sq_bridge/spx_m15_session_screen_v1.py`
- Compressió v2: `lab/sq_bridge/spx_m15_compression_expansion_v2.py`
- Pullback v3: `lab/sq_bridge/spx_m15_trend_pullback_v3.py`
- Turn-of-month v4: `lab/sq_bridge/spx_turn_of_month_v4.py`
- Memòria de fracassos: `academia/experiments/failure-memory.json`

## Com reprendre en una sessió nova

1. Llegir aquest document i `docs/ESTAT.md`.
2. No executar les tres famílies descartades amb paràmetres nous.
3. Verificar que l'exportació/parquet coincideixi amb els hashes versionats.
4. Completar el gate de captures amb mercat obert; no comptar mostres tancades.
5. Preregistrar una sola hipòtesi nova abans de consultar 2019–2022 o 2026.
