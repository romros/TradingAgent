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
- Spread i slippage efectius d'SQ iguals a zero; comissió i swap explícitament
  desactivats. No n'hi ha prou que el manifest del projecte ho declari:
  l'extractor ho torna a llegir de `SettingsMap` i de l'`InstrumentInfo`
  incrustat en cada SQX final. Un camp absent, ambigu o diferent de zero falla
  tancat.
- Qualsevol preu o indicador d'entrada té `Shift` efectiu mínim 1: només pot
  usar candles completades abans de l'open d'entrada.
- Trailing stop, move-to-break-even i exit signals dinàmics no formen part del
  subset actual.

SQ serialitza aquestes accions a l'SQX. `sqx_extract.py` les extreu,
`sqx_to_ir.py` les normalitza i `validate_executable_ir()` imposa el contracte.
Tant `sq_generation` com `python_translation` tornen a obrir els fitxers i el
revaliden; els booleans declarats a l'artefacte no són suficients per passar.
El constructor d'SQ fixa `minShift=1`, però el verificador torna a caminar l'AST
de cada SQX per impedir que una importació o manipulació amb `Shift=0` eludi la
configuració. `IsMonthLastTradingDay` queda fora de l'execució fins disposar
d'un calendari causal explícit en lloc d'inferir-lo de la següent fila.

## Semàntica determinista del runtime

El trace Python usa candles OHLC úniques, creixents i UTC, i nocional constant
abans de costos. L'ATR replica `ATR.java`: `High-Low` a la primera barra,
mitjana acumulada del true range mentre escalfa i recurrència Wilder quan arriba
al període. Per no mirar dins la candle del senyal, `ATRBasedValue.java` usa
l'ATR de l'última candle completada i l'arrodoneix a sis decimals abans de
multiplicar-lo.

SMA, EMA, RSI, ROC, Highest i Lowest reprodueixen també el warm-up dels
calculadors Java instal·lats d'SQ: EMA se sembra amb la primera barra; SMA i els
extrems usen el prefix disponible; RSI i ROC retornen zero fins arribar al seu
període. Aquesta semàntica evita que NaN artificials eliminin senyals inicials.

La implementació es va contrastar el 2026-08-10 amb els snippets de la
instal·lació SQCLI activa. Hashes SHA-256: `AverageCalculator.java`
`ad89dce741ec64365a01541bc241ba8e5a0ec1493b249a58d3c1601f5a4438df`,
`RSICalculator.java`
`820f62497fc004146ea01d2fa20fa77b51715bd8466a0e088e404f5a0397aa70`,
`HighestCalculator.java`
`9a4be83ad0af74d1507e3a4cbdfe7b23702afbf535cb1279018b158ce6d8725b`,
`LowestCalculator.java`
`0111ddb8842eb903bece3481ac3483aad74115fe183578befc8deb4039a9eb91`,
`ROC.java` `e852479c8cdf2f06c2bdadb9fa84b06b348c826e37389d93ba50a0e99baf6e64`
i `EMA.java`
`f241d8259b60e17818015522a3648368369ea34f0917151033083e1ca534e2f9`.
Per a stops, `ATR.java` és
`feee1fdc1bdd6389396499af8af12feed97e5fa357858f994c847ba4431fbe80` i
`SLPT/ATRBasedValue.java` és
`b50af2952fcd332e3f8071c14e5a6b4bf2eca30ce87baa947ab5fc5be458dbe1`.
Un canvi futur en qualsevol d'aquests snippets obliga a reauditar els vectors i
repetir la paritat observada.

Una sortida temporal s'executa a l'open després del nombre configurat de
candles. Stops i targets entren en vigor després de l'entrada i poden executar
dins la mateixa candle. Un gap advers de stop s'executa a l'open real, no al
nivell teòric; un gap favorable de target també conserva el preu d'open. Si una
sola OHLC toca stop i target i no permet provar quin va passar primer, el
runtime falla tancat.

El PnL del trace és brut: `notional_usdc × retorn del preu`. La comprovació dels
quatre costos dins l'SQX evita tant resultats bruts falsos com comptabilització
doble. Els costos Ostium,
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
