# T6G_NOTES.md — Commodities + Índexs per capitulation_d1

Data: 2026-03-16
Script: `lab/studies/t6g_capitulation_d1_commodities_indices.py`

---

## Resultat: 0 nous ACCEPTED_D1_ASSET, 1 WATCHLIST (SPY, N insuficient)

| Ticker | N | WR_b | EV@20x | Liq | WF | MC | MAE | Pass | Status |
|--------|---|------|--------|-----|-----|-----|-----|------|--------|
| GLD (Gold) | **3** | 67% | +16.6$ | 0% | 2/3 | 100% | 0.54% | 6/8 | REJECTED (N=3) |
| SPY (S&P500) | 24 | 75% | +2.9$ | 4.2% | 8/9 | 100% | 1.02% | 5/8 | WATCHLIST |
| ^GDAXI (DAX) | 37 | 51% | -4.8$ | 0% | 7/11 | 100% | 0.89% | 4/8 | REJECTED |

---

## Anàlisi per asset

### GLD — El cas més curiós (REJECTED per N=3)

- **Mètriques excepcionals**: EV=+16.6$, liq=0%, MAE=0.54%, MC=100%
- **Però N=3 en 13 anys** (0.4 trades/any) — massa pocs senyals per fer qualsevol conclusió
- **Per què tan pocs?** Gold en D1 rarament baixa -2%+ en un sol dia. El body<-2% és un
  criteri massa restrictiu per a Gold (volatilitat típica D1 = 0.3-1.0%).
- **Tesi estructural**: els dies que Gold sí baixa -2%+ (típicament vendes forçades per
  margin calls en crisis de liquiditat) tendeixen a revertir fort. La tesi és vàlida però
  la freqüència és insuficient per al setup actual.
- **Nota per futur**: gold amb body<-1% o body<-1.5% generaria 15-25 senyals/any.
  Podria ser interessant en una tasca separada. Però queda fora de T6g (setup fix).

### SPY — WATCHLIST (5/8, N insuficient)

- **WR 75%, WF 8/9 (89%), MC 100%** → edge molt consistent estadísticament
- **Però**: N=24 (<35 min), EV=+2.9$ (<8$ min), PF=1.42 (<1.8 min)
- S&P500 és menys volàtil que el Nasdaq (QQQ), per tant menys senyals (2/any)
  i el move post-capitulació és menor → no cobreix bé les fees a 20x
- **Observació**: WF 8/9 és millor que MSFT (10/12) en percentatge! Però N massa petit.
- **Rol en portfolio**: potencialment afegit a QQQ per tenir un senyal addicional a
  l'índex US quan els dos fallen el mateix dia (però correlació alta amb QQQ).

### ^GDAXI (DAX) — REJECTED (4/8)

- N=37 (suficient), pero WR=51% (cap edge significant), EV=-4.8$
- **2020 va ser devastador**: 5 trades, WR=20%, -160$. Crisis COVID-19 al DAX
  va generar múltiples jornades baixes consecutives sense rebot immediat.
- La tesi de "V-shape recovery" funciona pitjor en índexs europeus: menys recompres
  corporatives agressives, diferent composició sectorial, market hours disconnect.
- REJECTED definitiu.

---

## Conclusions T6g

L'screening de commodities i índexs confirma:

1. **Gold (XAU) és conceptualment atractiu** però requereix un threshold diferent
   (body<-1.5% en lloc de -2%) per generar N suficient. Queda com a **candidat futur**
   si s'obré un T6h de variants del setup.

2. **SPY és un duplicat de qualitat** de QQQ: mateixa tesi, N molt menor. No aporta
   prou diversificació per justificar una posició independent en el probe.

3. **DAX no té l'edge**: la tesi de mean-reversion post-capitulació és específica als
   mercats US on el rebot el dia T+1 és estructural (buybacks, Fed put, pes de Big Tech).

4. **Forex i Oil**: confirmat que no val la pena testar (forex: moves insuficients;
   oil: MAE >3%).

**Univers final immutable: MSFT + NVDA + QQQ.**
Cap asset nou afegit al probe.
