# Ostium — auditoria de signe i unitat del rollover

## Decisió

Per `@ostium/builder-sdk` 0.7.0, `getPairs().rolloverRate.{long,short}` és
**impacte display/PnL percentual per 8 hores**, no el fee signat del contracte:

- valor display negatiu: cost per al trader;
- valor display positiu: crèdit per al trader;
- cost per 8 h usat pel backtest: `max(0, -displayRate)`;
- un crèdit observat avui es limita a cost zero i no s'extrapola al passat.

## Evidència primària reproduïble

1. La README inclosa al paquet npm 0.7.0 defineix `rolloverRate` com
   `8hr % by side`.
2. `getRolloverRateDisplay()` calcula primer el fee contractual per costat i
   després aplica `displayPerBlock = -contractFeePerBlock`; multiplica per
   `8 * 60 * 60 * 4 * 100` per produir percentatge per vuit hores.
3. La dependència oficial inclosa `@ostium/formulae` 1.6.3 implementa
   `CurrentTotalProfit = tradeProfit - rolloverFee - fundingFee`.
4. El contracte oficial, commit
   `8390ce497f68fb128900840e0ec30683afa945d3`, acumula el fee signat i
   `getTradeValuePure()` calcula
   `collateral + pnl - rolloverFee - fundingFee`. Un fee contractual positiu
   redueix el valor; un de negatiu l'incrementa.

Fonts:

- <https://docs.ostium.com/developer/reference/get-pairs>
- <https://docs.ostium.com/traders/reference/fees>
- <https://github.com/0xOstium/smart-contracts-public/blob/8390ce497f68fb128900840e0ec30683afa945d3/src/OstiumPairInfos.sol#L561-L573>
- <https://github.com/0xOstium/smart-contracts-public/blob/8390ce497f68fb128900840e0ec30683afa945d3/src/OstiumPairInfos.sol#L733-L744>
- <https://github.com/0xOstium/smart-contracts-public/blob/8390ce497f68fb128900840e0ec30683afa945d3/src/OstiumPairInfos.sol#L859-L868>

La inspecció local es va fer contra la imatge
`tradingagent-ostium-readonly:0.7.0-generic`, fixada durant l'auditoria pel
digest `sha256:3b9c85ed65240797bb4b01ca30ec26e4618c7fcb528586315cb1de33aa9d0476`,
que conté el paquet i lockfile utilitzats pel collector. Es van verificar directament
`getRolloverRateDisplay()` de Builder SDK 0.7.0 i `CurrentTotalProfit()` de
Formulae 1.6.3. Aquesta auditoria no autoritza paper ni live.

## Conseqüència observada per EUR/USD

La captura del 2026-08-10 mostrava aproximadament:

- long: `-0,0026840954% / 8 h` → cost anualitzat instantani aproximat del
  `2,940%`;
- short: `-0,0000576646% / 8 h` → cost anualitzat instantani aproximat del
  `0,063%`.

Són taxes instantànies i poden canviar diàriament. El freezer usa la distribució
madura observada i manté sòls adversos del 8% conservador i 12% estrès.
