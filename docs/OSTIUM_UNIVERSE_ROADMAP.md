# Full de ruta de mercats Ostium

**Data de contrast:** 2026-08-04  
**Font canònica:** documentació oficial de mercats i fees d'Ostium.

Ostium publica 75 parells. Alquímia no els optimitza tots: aplica primer dades,
mapping, paritat, execució i economia per a 200 USDC. El catàleg executable és
`lab/sq_bridge/ostium_research_universe_v2.json` i el pla es genera amb
`ostium_universe_plan.py`.

## Ordre proposat

1. Renovar paritat `EURUSD` i `XAUUSD`, perquè ja tenim 274 mesos Dukascopy.
2. Descarregar i certificar `GBPUSD`, `USDJPY` i `AUDUSD`, ja suportats i
   verificats pel downloader de BrokerageService.
3. Verificar `USDCHF`, `USDCAD`, `NZDUSD` i `XAGUSD` amb pilots curts abans de
   qualsevol backfill llarg.
4. Resoldre mapping de `US500↔SPXUSD`, `US100↔NDXUSD` i `GER40↔DAXEUR` amb
   candles simultànies. Els noms semblants no demostren el mateix oracle.
5. Deixar petroli i la resta de metalls per després: base de futurs, breaks i
   rollover poden dominar l'edge.
6. `USDMXN` i `USDKRW` queden al final: fee superior, liquiditat/horaris i font
   històrica requereixen més verificació que les divises majors.

Observació de només lectura del 2026-08-04: el recorder ja conté 169.299 M1 de
`GBPUSD`, 169.296 de `USDJPY`, 162.254 de `SPXUSD`, 136.279 de `NDXUSD` i
158.083 de `DAXEUR`. La quarantena neta només conserva ara un dia per GBP/JPY,
SPX/DAX, però 121.255 M1 per NDX. Serveixen per al pilot de mapping; no substitueixen
l'històric Dukascopy ni autoritzen backtest.

## Economia del compte petit

Cada obertura consumeix 0,10 USDC d'oracle, a més del fee percentual, bid/ask i
rollover. Això penalitza especialment notional petit i alta freqüència. Forex,
or i índexs parteixen de 3 bps d'obertura; altres metalls i energia de 5 bps.
El màxim de leverage publicat és només una propietat del venue, mai el cap
d'Alquímia.

## Estat actual

Cap mercat nou queda autoritzat automàticament. `EURUSD` i `XAUUSD` necessiten
paritat recent; els altres necessiten dades o mapping. Aquest bloqueig deliberat
evita repetir una campanya sobre un preu que després no es pot executar a Ostium.

## Incidència del primer pilot GBPUSD

El job `495b023b` del 2026-08-04 va acabar `FAILED`, 0/2 mesos i cap Parquet
creat. La causa de xarxa va ser `HTTP 429` en tots els intents, perquè dos mesos
es van demanar concurrentment amb backoff de només 2/4/8 segons. No s'ha repetit
per evitar agreujar el límit.

També es van detectar dos defectes del wrapper `BrokerageService/scripts/sync_symbol.sh`:

- usa mesos de shell amb zero inicial en aritmètica (`08`/`09` fallen com octal);
- després d'un job fallit, un índex buit produeix `missing=0` i el wrapper informa
  incorrectament `Coverage OK` i retorna èxit.

Correcció requerida a BS abans de reprendre: convertir mesos explícitament en
base 10 o delegar tota l'aritmètica de dates a Python; propagar `any_failed`;
exigir almenys un mes/filera dins del rang; per `429`, respectar `Retry-After`,
afegir jitter i backoff llarg, i començar pilots amb un sol worker/mes.
