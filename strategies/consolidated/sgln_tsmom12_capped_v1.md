# SGLN TSMOM12 — edge admès només com a sleeve limitat

## Què fa

- Vehicle: iShares Physical Gold ETC, ISIN `IE00B4ND3602`.
- Senyal l'última sessió de cada mes: compara el tancament ajustat amb el
  tancament de fa 12 observacions mensuals.
- Si és superior, manté una posició long; si no, queda en cash.
- El canvi de posició s'executa a l'open de la primera sessió del mes següent.
- No hi ha shorts, leverage, stop, target, notícies ni decisió agentic.
- Cost congelat a capital equivalent de 1.000 EUR: 1,25 EUR per canvi més 5
  bps de slippage. No s'ha optimitzat cap paràmetre.

## Evidència de l'edge

SGLN va ser descobert en 2019–2024 amb +78,84%, Sharpe 0,875 i DD 17,32%.
La confirmació cronològicament nova 2025–juliol 2026 va produir 18 mesos,
+42,13%, Sharpe 1,046. PHAU, un ETC físic diferent sobre el mateix metall,
va donar +51,06% i correlació mensual 0,960. En el bloc combinat 2019–2026,
SGLN obté +158,35%, 13,49% anualitzat i Sharpe 0,892.

La regla **no passa com a estratègia standalone al 100%**: el DD recent de
25,82% supera el gate congelat del 20%. Aquest resultat no s'ha relaxat ni
esborrat.

## Admissió a cartera

La prova downstream fixa quatre sleeves iguals —CAT, MSFT, JPM i SGLN— sense
cercar pesos. En 2022–2024:

| Cartera | Retorn | PF | DD closed-equity |
|---|---:|---:|---:|
| CAT + MSFT + JPM | +22,72% | 1,369 | 10,68% |
| CAT + MSFT + JPM + SGLN | +28,26% | 1,534 | 6,95% |

La correlació mensual absoluta màxima de SGLN amb les altres tres és 0,250.
Per això la classificació és `PASS_EDGE_AS_CAPPED_PORTFOLIO_SLEEVE`, amb un
màxim inicial del 25% del capital. No autoritza augmentar el pes per aprofitar
el rally recent de l'or.

## Vehicle i implementació

BlackRock identifica el producte com a ETC de metall físic, TER 0,12%, base
USD, domicili Irlanda i publica PRIIP KID específic que adverteix els inversors
d'Espanya. Té listings LSE en GBP (`SGLN`), USD (`IGLN`) i EUR (`EGLN`), a més
de Xetra (`PPFB`). Cal resoldre el contracte concret a IBKR per ISIN, moneda i
mercat abans de paper; no s'ha de confiar només en el ticker de Yahoo.

- Producte oficial: https://www.ishares.com/uk/individual/en/products/258441/ishares-physical-gold-etc
- PRIIP KID (ISIN `IE00B4ND3602`): https://www.ishares.com/uk/professional/en/literature/kiid/uk_priips-ishares-physical-gold-etc-gb-ie00b4nd3602-en.pdf

Per reconstruir la recerca:

1. Executar `gold_tsmom_confirmation_screen_v1.py` amb les dues fonts ajustades.
2. Reobrir el resultat standalone, inclòs el `REJECT_CONFIRMATION` per DD.
3. Executar `cat_msft_jpm_gold_portfolio_v1.py` amb pesos iguals.
4. Verificar hashes, dates mensuals i costos abans de qualsevol traducció SQ.

## Limitacions

- La cartera 2022–2024 és un diagnòstic històric downstream, no un holdout nou.
- El drawdown de cartera és closed-equity; abans de paper cal recomputar-lo
  mark-to-market i incloure FX si es compra una línia no denominada en EUR.
- Cal confirmar a IBKR el contracte/KID accessible al compte espanyol i les
  comissions LSE/Xetra reals.
- Paper i LIVE continuen no autoritzats.

## Viabilitat de compte petit

La reconstrucció posterior `four_strategy_small_account_v1.py` substitueix els
quatre sleeves teòrics de 1.000 per una sola dotació total, repartida en quatre
compartiments fixos del 25%, i exigeix unitats senceres. En 2022–2024:

| Capital total | Retorn | DD tancat | Reprodueix les quatre? |
|---:|---:|---:|:---:|
| 500 | +9,80% | 1,22% | No; només SGLN |
| 1.000 | +13,49% | 2,96% | No; CAT queda fora |
| 1.500 | +18,70% | 3,32% | No; CAT queda fora |
| 2.000 | +21,99% | 8,47% | Sí |
| 3.000 | +26,97% | 8,34% | Sí |

Per tant, **2.000 és el primer punt viable de la graella provada**, no un mínim
matemàtic exacte. El resultat encara fixa GBP/account currency a 1:1, conserva
cash sobrant dins cada compartiment i calcula DD closed-equity. No s'ha d'usar
com a promesa de rendiment.

SQCLI Portfolio Master sí que val la pena com a implementació independent: el
smoke real ja prova que pot construir una cartera i generar equity/ordres. No
pot validar encara aquesta cartera perquè primer cal tenir les quatre regles en
SQX natiu amb paritat trade-a-trade i els mateixos costos. Executar Portfolio
Master abans amagaria les discrepàncies de cada cama dins l'agregat.
