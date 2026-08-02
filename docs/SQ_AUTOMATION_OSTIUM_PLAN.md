# Automatització SQ → BrokerageService → Ostium

**Data:** 2026-08-01
**Estat:** pla acordat, pendent d'implementar.

## Objectiu i responsabilitats

- **StrategyQuant:** genera candidats i aplica IS/OOS, Monte Carlo, robustesa i walk-forward.
- **DuckDB + BrokerageService LAB:** compara dades i reprodueix senyals, operacions, costos i resultats independentment.
- **BrokerageService (BS):** proporciona dades i executa ordres a Ostium.
- **TradingAgent (TA):** decideix, calcula risc i mida, i gestiona paper/live.

SQ farà el screening massiu. No s'han de copiar estratègies manualment; només les supervivents arriben al LAB i després, si passen els gates, al paper probe.

## Pipeline acordat

```text
sq_campaign.yaml + configuració .cfx
    → SQCLI / Custom Project
    → generació, OOS, robustesa i walk-forward
    → exportació del databank, mètriques i estratègies
    → DuckDB: paritat de candles, senyals i trades
    → BS LAB: backtest independent amb costos Ostium
    → matching de mercat, mida, collateral i leverage
    → TA paper probe
    → gate live
```

L'orquestrador Python carregarà i iniciarà SQCLI, en consultarà l'estat, recollirà exportacions i les normalitzarà a JSON/Parquet. Pot caldre configurar el Custom Project una vegada amb la GUI, però no intervenir per cada estratègia.

## Traducció d'estratègies

`.sqx` és propietari; no assumirem una traducció universal a Python. Limitarem SQ a indicadors, operadors, entrades i exits suportats, exportarem codi/pseudocodi i traduirem aquest subconjunt a una representació intermèdia canònica. Qualsevol regla no reproduïble exactament quedarà `UNSUPPORTED`, sense aproximacions silencioses.

## Paritat de dades amb DuckDB

```text
market_candles(source, symbol, timeframe, timestamp_utc,
               open, high, low, close, volume)
```

Fonts: `sq`, `dukascopy`, `brokerage_service` i, quan sigui possible, `ostium`.

Cal comparar UTC, timestamps, construcció del timeframe, candles absents o duplicades, diferències OHLC en bps, spreads, gaps, outliers, ajustos corporatius i l'oracle real d'Ostium.

Mètriques mínimes:

- `candle_coverage_pct`
- `price_diff_median_bps` i percentils
- `signal_match_rate`
- `trade_match_rate`
- `entry_slippage_bps`
- `stop_trigger_mismatch_rate`
- `pnl_correlation`
- `net_pnl_difference_pct`
- `max_drawdown_difference_pct`

**Regla:** si no podem explicar la diferència entre SQ i el backtest independent, la candidata no avança a paper.

## Matching SQ → Ostium

| SQ | Ostium |
|---|---|
| símbol i font | mercat i oracle disponibles |
| timeframe/horari | candles reproduïbles en UTC |
| entrada teòrica | ordre i preu executables |
| stop/target/exit | precisió i condicions admeses |
| mida nocional | mínims i màxims del mercat |
| leverage | límit Ostium i límit segur propi |
| costos | spread, slippage, fee, gas i funding |
| MAE/drawdown | marge de liquidació i risc monetari |

Primer es valida el senyal i el preu; després mida i execució. Una mala paritat no es compensa augmentant leverage.

## Sizing i leverage

```text
risk_budget_usd = equity_usd × risk_per_trade_pct
effective_stop_pct = max(strategy_stop_pct, liquidation_safety_floor_pct)
notional_usd = risk_budget_usd / effective_stop_pct
required_leverage = notional_usd / collateral_usd

approved_leverage = min(required_leverage,
                        ostium_market_max_leverage,
                        strategy_stress_max_leverage,
                        portfolio_risk_max_leverage)
```

Buscarem el leverage més alt que encara superi els gates de risc, no simplement el màxim ofert. Inclourà MAE històrica/estressada, marge a liquidació, costos, funding, drawdown, correlació de cartera i límits de collateral/notional. Augmentar leverage mantenint el mateix nocional no augmenta el benefici; només redueix el marge.

## Gates i estat

Una candidata només avança si passa IS/OOS i walk-forward, costos base/conservadors/estrès, mostra suficient, paritat, traducció exacta, compatibilitat Ostium, leverage segur i paper probe. Un `PASS` de SQ només autoritza verificació independent, mai live directament.

- BS ja té eines d'exportació/paritat SQ i un runner LAB.
- `sq_0423850` es va traduir però va quedar descartada en OOS.
- TA ja té paper execution, costos, risc, liquidacions i live-readiness.
- `capitulation_d1` sobre MSFT és la candidata activa, però només té 6 trades paper.
- Falta el pont complet de campanyes, databank, traducció i matching Ostium.
- **Bloqueig:** SQCLI indica `Trial license expired / License is invalid`.

## Següent tram

1. Activar la llicència SQ i estabilitzar `sqcli-docker`.
2. Fer un MVP de 20–50 estratègies.
3. Automatitzar SQCLI i exportació.
4. Ingerir a DuckDB i generar paritat.
