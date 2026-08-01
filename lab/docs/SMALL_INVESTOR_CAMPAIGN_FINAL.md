# Campanya petit inversor — resultat final

**Data:** 2026-08-01
**Decisió:** `NO_CANDIDATE`

## Objectiu i protocol

Es van buscar estratègies long/cash, simples i controlables sobre SPY, QQQ,
IWM, GLD i TLT. Capital de referència: 250 USD. Les regles es van seleccionar
només amb dades fins al 2017; 2018–2022 és validació i 2023–2026 és el test
final. Les execucions utilitzen el següent open disponible, amb cost base,
cost 2x, finançament del leverage i barrera conservadora de liquidació.

El leverage es congela amb validació i el test final només l'aprova o rebutja.
No es redueix retrospectivament fins a trobar un valor que passi.

## Resultats individuals

| Família | Actiu | Paràmetres | PF validació | PF test | CAGR test | DD test | Leverage validació | Decisió |
|---|---|---|---:|---:|---:|---:|---:|---|
| Mean reversion | SPY | RSI2<15, hold 7 | 1.14 | 1.46 | 7.0% | 5.9% | cap | REJECTED |
| Capitulation confirmada | QQQ | drop 2.5%, hold 2 | 0.76 | 1.01 | -0.1% | 8.1% | cap | REJECTED |
| Pullback en tendència | IWM | RSI5<30, hold 5 | 1.02 | 1.57 | 9.3% | 8.1% | cap | REJECTED |
| Donchian breakout | TLT | 100/20 | 1.03 | 0.83 | -1.7% | 7.4% | cap | REJECTED |
| Tendència temporal | SPY | SMA 50/150 | 1.11 | 1.23 | 16.0% | 19.8% | cap | REJECTED |
| Reversió curta | SPY | drop 3d 4%, hold 8 | 1.29 | 3.13 | 0.5% | 0.9% | 1.5x | REJECTED (N) |

La reversió curta és l'única que supera els criteris econòmics provisionals,
però només genera 14 entrades en 22 anys: 7 en validació i 1 al test final.
El PF del test deriva d'una sola operació i no és una estimació fiable. El
bootstrap dels 14 trades és positiu en 96.19% de simulacions, però no resol la
manca d'observacions independents fora de mostra.

## Resultats de cartera

| Família | Paràmetre | PF validació | PF test | CAGR test | DD test | Decisió |
|---|---:|---:|---:|---:|---:|---|
| Momentum relatiu | 252 dies | 1.07 | 1.23 | 23.3% | 21.4% | REJECTED |
| Tendència diversificada | 126 dies | 1.04 | 1.21 | 14.6% | 11.6% | REJECTED |
| Rotació defensiva | 126 dies | 1.00 | 1.23 | 16.9% | 12.3% | REJECTED |

Les carteres tenen retorn absolut interessant al test, però no demostren edge
suficient durant 2018–2022 i fallen el PF mínim. Augmentar leverage amplifica
retorn i drawdown, però no arregla una expectativa insuficient després de
costos.

## Per què no hi ha una cartera de 3–6

1. Cinc famílies individuals fallen expectativa o estabilitat en validació.
2. Les tres carteres fallen el profit factor de validació.
3. L'única anomalia positiva té una mostra final d'una operació.
4. Relaxar PF, mostra o costos després de veure el test seria sobreajustament.
5. Combinar estratègies rebutjades no converteix els components en edge vàlid.

## Decisió operativa

- No implementar cap d'aquestes candidates al TradingAgent productiu.
- No activar trading real ni augmentar leverage.
- Conservar `short_term_reversal` com a hipòtesi de recerca, no com a estratègia.
- El paper probe antic `capitulation_d1` continua `LIVE_NOT_READY` i no forma
  part d'una cartera aprovada.

## Següent recerca recomanada

Una futura campanya hauria d'utilitzar dades intradia o setmanals de
BrokerageService/SQ per obtenir més observacions, costos reals d'Ostium i
famílies econòmicament diferents. Cal congelar un nou test final abans de
començar; no s'han de reutilitzar 2023–2026 per ajustar les regles provades aquí.

## Evidència

- Protocol: `lab/docs/SMALL_INVESTOR_RESEARCH_PROTOCOL.md`
- Runner individual: `lab/studies/small_investor_campaign.py`
- Runner cartera: `lab/studies/small_investor_portfolios.py`
- Artifact individual: `lab/out/small_investor_campaign/results.json`
- Artifact cartera: `lab/out/small_investor_campaign/portfolio_results.json`
- Resums: `lab/out/small_investor_campaign/SUMMARY.md` i `PORTFOLIOS.md`
