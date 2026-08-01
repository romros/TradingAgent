# Import BrokerageService — sq_0423850 XAUUSD H4

Data: 2026-08-01

## Decisió

**REJECTED_OOS. No incorporar al paper probe ni a producció.**

El backtest brut 2016–2025 sembla positiu, però el guany queda concentrat al
tram inicial 2016–2018. Amb els paràmetres congelats, el període out-of-sample
2019–2025 no conserva edge després de costos.

## Contracte de validació

- Estratègia: sq_0423850, LONG only, Bollinger Lower crossover.
- Asset/timeframe: XAUUSD H4.
- Dades: Dukascopy M1 Parquet de BrokerageService, agregades a H4.
- Train inicial: 2016–2018.
- OOS anual ancorat: 2019–2025.
- Mostra total: 45 trades; mostra OOS: 33 trades.
- Paràmetres congelats; no hi ha reoptimització per finestra.

## Costos Ostium modelats

La documentació oficial indica per XAU/USD:

- opening fee: 3 bps sobre nominal;
- cap closing fee;
- execució bid/ask;
- rollover continu variable;
- oracle fee retornada en un full close correcte.

| Escenari | Open | Spread | Slippage | Rollover anual |
|---|---:|---:|---:|---:|
| official_base | 3 bps | 2 bps | 1 bp | 200 bps |
| conservative | 3 bps | 5 bps | 2 bps | 500 bps |
| stress | 3 bps | 10 bps | 5 bps | 1000 bps |

Fonts: https://docs.ostium.com/traders/reference/fees i
https://docs.ostium.com/traders/reference/markets

## Resultat

| Escenari | OOS compost | PF | WR | Max DD | Anys positius |
|---|---:|---:|---:|---:|---:|
| official_base | **-1.00%** | 0.9600 | 45.45% | 5.50% | 3/7 |
| conservative | **-2.99%** | 0.8626 | 45.45% | 6.85% | 2/7 |
| stress | **-6.62%** | 0.7058 | 45.45% | 9.57% | 2/7 |

Referència bruta 2016–2025: +16.38% compost, PF 1.84, WR 57.78%.
La diferència entre brut total i OOS revela dependència de règim o degradació
temporal. El gate de TradingAgent exigeix almenys 65–70% de finestres
positives; aquí el millor cas dona 42.9%.

## Impacte a TradingAgent

- No canviar capitulation_d1 ni el paper probe MSFT/NVDA/NDXUSD.
- No crear executor ni scheduler per sq_0423850.
- Conservar el resultat com a control negatiu.
- Si es reobre aquesta línia, cal una hipòtesi de règim definida ex ante i una
  nova validació OOS; no ajustar paràmetres sobre 2019–2025.

Artifacts: lab/out/brokerage_sq_0423850/.

## Auditoria del paper probe existent

El reporting anterior restava 5.38$ fixos per trade. Per als sis trades
existents això registrava -11.39$, tot i que el PnL brut era +20.895$.
Recalculat sobre els nominals exactes sense alterar la base històrica:

| Cost | PnL net 6 trades | EV/trade |
|---|---:|---:|
| base (6 bps) | +17.56$ | +2.93$ |
| conservative (10 bps) | +15.33$ | +2.55$ |
| stress (18 bps) | +10.88$ | +1.81$ |

El runtime usa ara PAPER_COST_BPS=6.0 per als trades nous. FEE continua
disponible només com override retrocompatible. Els trades antics no es
reescriuen, de manera que la traçabilitat original queda intacta.
