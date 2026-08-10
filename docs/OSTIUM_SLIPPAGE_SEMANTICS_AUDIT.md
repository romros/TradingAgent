# Ostium — auditoria de `getSimSlippage()` i bid/ask

## Decisió

Per `@ostium/builder-sdk` 0.7.0, el camp `slippage` retornat per
`getSimSlippage()` és `priceImpactP` expressat en percentatge. Aquest impacte
**ja incorpora el component bid/ask**. No s'hi pot tornar a sumar el spread
complet.

La conversió canònica és:

- `slippage_bps = slippage_pct × 100`;
- `roundtrip_proxy_bps = open_fee + close_fee + long_open_impact + short_open_impact`.

El collector només simula obertures (`isOpen=true`). Una obertura long consumeix
el costat buy i el seu tancament consumeix el costat oposat; per això la suma
long-open + short-open és el proxy observable per al round-trip dels dos
sentits. No es declara com a fill real ni com a impacte futur garantit.

El spread derivat de `ask-bid` es conserva separadament per diagnosticar mercat
i divergències temporals, però no entra una segona vegada al cost.

## Evidència primària reproduïble

Inspeccionat dins la imatge immutable
`tradingagent-ostium-readonly:0.7.0-generic`:

1. `builder-sdk/dist/index.js::simulateSlippageForPair()` retorna
   `formatTokens(result.priceImpactP)`.
2. Crida `CalculateDynamicPriceImpact(..., isOpen=true, isBuy=side, ...)` de
   `@ostium/formulae`.
3. `PriceImpactFunction()` inicia `priceImpactP` amb
   `(ask-bid)/(2*mid)` i després afegeix el component dinàmic.
4. Quan el component dinàmic està desactivat, `GetPriceImpact()` calcula
   directament la distància mid→ask o mid→bid.

Referències oficials:

- <https://docs.ostium.com/developer/reference/get-pairs>
- <https://docs.ostium.com/traders/reference/markets>
- <https://www.npmjs.com/package/@ostium/builder-sdk/v/0.7.0>

## Conseqüència observada per EUR/USD

Recalculant les sis captures del 2026-08-10 a 200 USDC:

- p50 round-trip: `2,9964 bps`;
- p95 round-trip: `4,6207 bps`;
- màxim: `5,1188 bps`;
- spread p50 separat: `1,0396 bps`.

Els valors continuen provisionals fins complir totes les cobertures. L'auditoria
no autoritza SQCLI, paper ni live.
