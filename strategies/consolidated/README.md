# Estratègies consolidades

Aquest directori és el punt d'entrada net a les estratègies que han superat els
gates de recerca disponibles. No conté còpies dels resultats: cada fitxa apunta
als artefactes originals, que conserven hashes i traçabilitat.

L'estat transversal actual, capital petit i agregació són a
[FIVE_STRATEGY_PORTFOLIO_STATUS](../../docs/FIVE_STRATEGY_PORTFOLIO_STATUS.md).
La reconstrucció nativa de les quatre peces prèvies continua documentada a
[FOUR_STRATEGY_PORTFOLIO_STATUS](../../docs/FOUR_STRATEGY_PORTFOLIO_STATUS.md).

## Estat del catàleg

| Estratègia | Actiu | Mecanisme | Estat | Fitxa |
|---|---|---|---|---|
| `cat_d1_trend_0168` | CAT | Trend pullback D1 | Admesa per recerca | [CAT](cat_d1_trend_0168.md) |
| `msft_d1_capitulation` | MSFT | Reversió després de capitulació D1 | Admesa per recerca | [MSFT](msft_d1_capitulation.md) |
| `jpm_momentum60_month_end_v1` | JPM | Momentum mitjà mostrejat a final de mes | Admesa; aporta a cartera | [JPM](jpm_momentum60_month_end_v1.md) |
| `sgln_tsmom12_capped_v1` | SGLN/IGLN/EGLN | Momentum 12 mesos sobre or físic | Admesa només com a sleeve ≤25% | [SGLN](sgln_tsmom12_capped_v1.md) |
| `aapl_momentum60_month_end_v1` | AAPL | Momentum mitjà mostrejat a final de mes | Recerca admesa; cartera rebutjada | [AAPL](aapl_momentum60_month_end_v1.md) |
| `multi_asset_sma200_three_down_hold10_v1` | 10 equities/ETF | Pullback curt dins tendència SMA200 | Edge de recerca; paritat SQ AAPL | [Multi-actiu](multi_asset_sma200_three_down_hold10_v1.md) |

`Admesa per recerca` no significa autorització per operar. Encara cal la capa
de cartera, risc, paper trading i validació d'execució IBKR abans de LIVE.

## Política d'entrada

Una estratègia només entra aquí quan té:

1. Regla determinista i reproduïble.
2. Evidència temporal fora de mostra.
3. Costos executables auditats.
4. Cap gate crític pendent que invalidi l'edge observat.
5. Fitxa amb limitacions explícites i enllaç a l'evidència original.

Les hipòtesis, watchlists i estratègies rebutjades es mantenen a
`data/ibkr_sq_v2` i al catàleg complet
`lab/sq_bridge/theoretical_strategy_library_v1.json`; no es barregen amb aquest
directori.

L'índex llegible de vies mortes és a [estratègies rebutjades](../rejected/README.md).

## Cinquena font d'edge

La família multi-actiu SMA200/3-down/hold-10 ha superat el gate estadístic,
OOS, robustesa per blocs, paritat nativa SQ sobre AAPL i contracte de capital
compartit. Amb 1.000 USD supera validation i OOS; amb 500 USD falla. La paritat
SQ dels altres actius és una millora tècnica pendent, no una llicència per
reinterpretar la regla. No està autoritzada per paper ni live.
