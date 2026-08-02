# Revisió d'estratègies amb evidència — decisió Alquímia

**Data:** 2026-08-02  
**Objectiu:** estratègies simples, controlables i viables amb 200 USDC a Ostium.

## Criteri

Una estratègia famosa no és automàticament transferible al nostre venue. Ha de
conservar el mecanisme després de fees, bid/ask, rollover, liquidació, mida petita,
fonts disponibles i execució Ostium. No s'accepten resultats només IS ni millores
posteriors a obrir un holdout.

## Famílies revisades

| Família | Evidència externa | Encaix Ostium/200 | Evidència pròpia | Decisió |
|---|---|---|---|---|
| Time-series momentum | Forta i multi-actiu | Dolent si manté mesos i paga rollover | 126d positiu brut, negatiu amb carry base | Rebutjada per venue |
| Volatility management | Bona com a sizing, no és edge sol | Útil per limitar risc | Redueix concentració; no rescata EV | Conservar com a sizing |
| Opening-range breakout | Evidència en alguns futurs/índexs | Bona: intradia, sense rollover | XAU 15/30/60m PF base màx. OOS 0,81 | Rebutjada |
| Overnight equity | Evidència històrica, però sensible a microestructura | Requereix open/close i carry | Open MSFT no certificat | Bloquejada |
| RSI/pullback/reversió curta | Evidència coneguda però molt dependent d'actiu | Exposició curta favorable | Campanya anterior falla validació o mostra | Rebutjada |
| Capitulation extrema | Mean reversion després de venda forçada | Exposició d'un dia, moviment gran | Única família que ha repetit edge; paper 6 trades | Continuar paper, no live |

## Fonts principals

- Moskowitz, Ooi i Pedersen, *Time Series Momentum*, Journal of Financial
  Economics 104 (2012), DOI 10.1016/j.jfineco.2011.11.003:
  https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf
- Hurst, Ooi i Pedersen, *A Century of Evidence on Trend-Following Investing*:
  https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing
- Moreira i Muir, *Volatility-Managed Portfolios*, Journal of Finance / NBER:
  https://www.nber.org/papers/w22208
- Tsai et al., *Assessing the Profitability of Timely Opening Range Breakout on
  Index Futures Markets*, IEEE Access (2019), DOI 10.1109/ACCESS.2019.2899177.
- Cooper, Cliff i Gulen, *Return Differences between Trading and Non-Trading
  Hours: Like Night and Day*: https://ssrn.com/abstract=1004081
- Ostium, mercats i fees actuals:
  https://docs.ostium.com/traders/reference/markets i
  https://docs.ostium.com/traders/reference/fees

## Experiments nous

### TSMOM Dukascopy EURUSD + XAUUSD

17,85 milions de candles M1, D1 amb frontera 17:00 NY i models fixos de
21/63/126/252 sessions més ensemble. El model 126d és el millor brut: validació
+10,44%, Sharpe 0,29; OOS +11,52%, Sharpe 0,35 i DD 8,59%. Amb només un 4%
anual advers de rollover passa a -10,3% i -7,4%. Com que Ostium aplica rollover
continu i variable a totes les parelles, l'edge brut no té marge suficient.
Holdout 2024–2026 preservat.

### XAU COMEX opening-range breakout

Dukascopy M1 agregat a 5m, 2003–2026. Rang des de 08:20 NY de 15/30/60 minuts,
confirmació al close, entrada al següent open, stop al costat oposat, target 1,5R
i sortida 15:45. Les tres variants perden abans de costos d'estrès. La millor OOS
és 60m: 1.215 trades, PF base 0,805 i -37,36%. Holdout preservat.

## Conclusió

No s'ha trobat una segona estratègia apta. La millor decisió no és multiplicar
bots mediocres: és conservar `capitulation_d1` com a únic paper probe, acumular
moltes més observacions i millorar la paritat d'execució. TSMOM es pot reobrir si
disposem d'una sèrie històrica real de rollover i almenys 8–12 mercats; ORB XAU
queda tancada perquè falla fins i tot abans de l'estrès.

Abans de qualsevol live també cal verificar que l'operador no sigui una persona
restringida segons els termes vigents d'Ostium; la documentació actual enumera,
entre altres, EUA, Regne Unit i Unió Europea.
