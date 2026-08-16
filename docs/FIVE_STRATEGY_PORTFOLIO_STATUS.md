# Cartera de cinc edges — estat canònic

Aquest document amplia, però no reescriu, la cartera nativa de quatre peces
descrita a `FOUR_STRATEGY_PORTFOLIO_STATUS.md`. No s'ha autoritzat paper ni
LIVE.

## Què tenim

La llibreria admesa conté cinc fonts d'edge:

1. CAT trend pullback D1.
2. MSFT capitulation D1.
3. JPM Momentum60 a canvi de mes.
4. SGLN TSMOM12, limitat a un màxim del 25% de la cartera de quatre peces.
5. Pullback multi-actiu: `close>SMA200`, tres tancaments consecutius a la
   baixa, entrada al següent open i sortida deu sessions després.

La cinquena regla va ser escollida només amb train 2017–2021 i validation
2022–2023. Després del freeze, l'OOS 2024 va donar 85 trades, PF 2,0811,
retorn mitjà per sleeve de +22,3835% i DD 6,1381%. Les 10 proves
leave-one-asset-out van ser positives; sense NVDA encara va donar 76 trades,
PF 1,1346 i +2,5689%. La paritat nativa SQ està comprovada sobre AAPL: 63/63
parelles entrada/sortida dins la finestra de recerca.

## Capital compartit de la cinquena regla

La simulació canònica usa com a màxim tres posicions, capital/3 per posició,
accions senceres, sense palanquejament, 1 USD per ordre i 10 bps per costat.
Per col·lisions prioritza el retorn de tres sessions més negatiu.

| Capital | Validation 2022–23 | OOS 2024 | Lectura |
|---:|---:|---:|---|
| 500 USD | -17,68% | -6,27% | No viable; massa senyals no es poden comprar |
| 1.000 USD | +6,83% | +8,12% | Primer nivell que supera el gate |
| 2.000 USD | +15,81% | +11,27% | Més senyals executables |
| 5.000 USD | +23,36% | +15,10% | Diagnòstic, no objectiu necessari |

En el període continu 2022–2024, el compte de 1.000 USD dona 130 operacions,
+177,22 USD (+17,72%), PF 1,2466 i DD 19,92%. Queden 12 senyals sense executar
per manca de capital i tres posicions obertes excloses al final. No s'ha
optimitzat la regla després de veure aquests resultats.

## Agregació teòrica de cinc edges

La política congelada conserva dos compartiments sense transferències:

- 2.000 USD per a la cartera nativa CAT/MSFT/JPM/SGLN;
- 1.000 USD per al motor multi-actiu.

Entre 2022–2024, sota costos d'estrès, els endpoints sumen:

- cartera de quatre: +402,24 USD;
- motor multi-actiu: +177,22 USD;
- total: **+579,46 USD, o +19,32% sobre 3.000 USD**.

La reconstrucció posterior ha sincronitzat **1.089 observacions diàries** de
les dues corbes. Reprodueix el mateix endpoint de 3.579,46 USD i dona un
**drawdown conjunt observat del 10,92%**, entre 2022-01-12 i 2022-09-23. Passa
el gate congelat de DD <=15%. El 12,07% anterior queda només com a pressupost
ponderat preliminar i no s'ha d'usar com a mesura final.

El +19,32% no és una expectativa anual: cobreix tres anys històrics i no
inclou compounding ni transferències entre compartiments.

## Decisió per capital inicial

- 500 USD: cap configuració actual passa els gates.
- 1.000 USD: l'única configuració demostrada és el motor multi-actiu sol.
- 2.000 USD: es pot escollir la cartera antiga de quatre; no executa les cinc.
- 3.000 USD: primer capital auditat per mantenir totes cinc amb els
  compartiments congelats.

No es crearà retrospectivament un selector dinàmic per encaixar cinc edges en
1.000 USD: després d'haver vist 2024 seria una nova política sobreajustada i
necessitaria una mostra independent nova.

## Benchmark passiu i decisió actual

La comparació preregistrada usa SPY total-return (dividends ajustats) només com
a benchmark, amb el mateix període, capital, accions senceres i costos
d'estrès. Cap dels tres nivells actius supera buy-and-hold en rendiment:

| Capital | Activa CAGR / DD | SPY CAGR / DD | Decisió |
|---:|---:|---:|---|
| 1.000 USD | 5,59% / 19,92% | 8,25% / 23,43% | FAIL |
| 2.000 USD | 6,30% / 8,15% | 8,28% / 23,41% | Només utilitat defensiva |
| 3.000 USD | 6,07% / 10,92% | 8,29% / 23,40% | FAIL del gate congelat |

Per tant, **no hi ha capital recomanat encara per a l'objectiu de superar
buy-and-hold**. Si l'objectiu fos exclusivament defensiu, 2.000 USD seria la
configuració actual més eficient. Aquesta distinció no es pot esborrar ni
reinterpretar.

La cartera final queda limitada a 6–8 estratègies identificables. La sisena
ha d'aportar retorn marginal i diversificació; no s'admetrà només per arribar
al mínim.

## Evidència principal

- `data/ibkr_sq_v2/five_edge_portfolio_v1/result.json`
- `data/ibkr_sq_v2/five_edge_portfolio_v1/daily_mtm_v1.json`
- `data/ibkr_sq_v2/five_edge_portfolio_v1/vs_spy_buy_hold_v1.json`
- `data/ibkr_sq_v2/five_edge_portfolio_v1/capital_ladder_vs_spy_v1.json`
- `data/ibkr_sq_v2/multi_asset_known_edge_funnel_v1/shared_capital_v1.json`
- `data/ibkr_sq_v2/multi_asset_known_edge_funnel_v1/oos_2024_concentration_audit.json`
- `data/ibkr_sq_v2/four_edge_portfolio_composer_v1/net_daily_mtm_gate_v1.json`

La corba diària conjunta ja està reconstruïda. Les millores tècniques pendents
són estendre la paritat SQ de la cinquena regla més enllà del control AAPL i
preparar una auditoria de contractes i costos IBKR. Després, només un
shadow/paper curt pot promoure la cartera. Fins aleshores
`paper_authorized=false` i `live_authorized=false`.
