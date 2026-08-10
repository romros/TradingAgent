# Contracte d'execució SQ → Python → Ostium v4

Aquest contracte evita promocionar una estratègia només perquè els seus
senyals es poden llegir. Una candidata d'Alquímia també ha de conservar i
reproduir la gestió del trade.

## Subset executable

- Entrada `EnterAtMarket` a l'open de la candle on apareix el senyal.
- Una sola posició; `AllowDuplicateTrades=false`.
- Direcció SQ coherent amb la regla long o short.
- Stop obligatori per cada direcció activa: ATR o percentatge positiu.
- Profit target opcional: ATR, percentatge o desactivat.
- `ExitAfterBars` enter no negatiu; zero significa desactivat.
- `ExitAtEndOfDay=false` i `ExitOnFriday=false` explícits.
- Trailing stop, move-to-break-even i exit signals dinàmics no formen part del
  subset actual.

SQ serialitza aquestes accions a l'SQX. `sqx_extract.py` les extreu,
`sqx_to_ir.py` les normalitza i `validate_executable_ir()` imposa el contracte.
Tant `sq_generation` com `python_translation` tornen a obrir els fitxers i el
revaliden; els booleans declarats a l'artefacte no són suficients per passar.

## Semàntica determinista del runtime

El trace Python usa candles OHLC úniques, creixents i UTC, i nocional constant
abans de costos. L'ATR és Wilder: mitjana aritmètica inicial del true range i
recurrència posterior. Per no mirar dins la candle del senyal, l'stop ATR usa
l'ATR de l'última candle completada.

Una sortida temporal s'executa a l'open després del nombre configurat de
candles. Stops i targets entren en vigor després de l'entrada i poden executar
dins la mateixa candle. Un gap advers de stop s'executa a l'open real, no al
nivell teòric; un gap favorable de target també conserva el preu d'open. Si una
sola OHLC toca stop i target i no permet provar quin va passar primer, el
runtime falla tancat.

El PnL del trace és brut: `notional_usdc × retorn del preu`. Els costos Ostium,
carry, sizing per risc i leverage s'apliquen a les etapes econòmiques
posteriors, amb el model de costos congelat.

## Fonts observades de paritat SQ

`sq_parity_trace_v4.py` transforma l'`orders.csv` real d'StrategyQuant, però no
dedueix falsament tots els senyals a partir de les ordres executades. Exigeix un
segon CSV independent amb capçalera `Timestamp;Direction`, més les mateixes
candles MT4 i la zona horària IANA explícita de l'export SQ. Els timestamps han
de coincidir exactament amb candles comunes. El PnL d'SQ es recalcula des dels
preus d'entrada/sortida al mateix nocional fix que Python, abans de costos; la
columna `Profit/Loss` d'SQ no pot introduir una escala de capital diferent.

```bash
PYTHONPATH=../.. python3 sq_parity_trace_v4.py \
  --candidate-id EXACT_STRATEGY_NAME \
  --orders /path/to/orders.csv \
  --signals /path/to/signals.csv \
  --market-data /path/to/common-mt4.csv \
  --source-timezone UTC --notional-usdc 200 \
  --output /path/to/sq.trace.json
```

Si SQ no ha produït el log de senyals, l'adaptador es nega a crear evidència de
paritat completa. Una llista d'ordres sola pot servir per diagnosticar execució,
però no per superar el gate de senyals. El verificador reobre també ordres,
senyals, candles i IR i recalcula els seus SHA-256; conservar només el trace
després de substituir una font invalida la cadena.

## Què demostra i què no

Els tests unitaris demostren que la nostra semàntica és determinista, que els
hashes lliguen dades/IR/SQX i que casos ambigus o insegurs són rebutjats. No
demostren que StrategyQuant comparteixi exactament el mateix timing, ATR o
tractament intrabar. Aquesta afirmació només s'accepta després de comparar un
export real d'SQ amb el trace Python sobre les mateixes candles: coincidència
exacta de senyals i trades, correlació de PnL mínima 0,99 i errors absoluts dins
els límits preregistrats. Sense aquest PASS, la candidata no arriba a paper.
