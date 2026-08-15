# Estratègies consolidades

Aquest directori és el punt d'entrada net a les estratègies que han superat els
gates de recerca disponibles. No conté còpies dels resultats: cada fitxa apunta
als artefactes originals, que conserven hashes i traçabilitat.

## Estat del catàleg

| Estratègia | Actiu | Mecanisme | Estat | Fitxa |
|---|---|---|---|---|
| `cat_d1_trend_0168` | CAT | Trend pullback D1 | Admesa per recerca | [CAT](cat_d1_trend_0168.md) |
| `msft_d1_capitulation` | MSFT | Reversió després de capitulació D1 | Admesa per recerca | [MSFT](msft_d1_capitulation.md) |

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

## Candidata en validació

`aapl_momentum60_v1` ha passat el holdout Python i l'economia de compte petit,
però encara necessita paritat nativa SQCLI i robustesa. Per tant, no està
consolidada ni forma part de la cartera.
