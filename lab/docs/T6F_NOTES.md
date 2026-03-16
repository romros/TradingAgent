# T6F_NOTES.md — Screening final actius addicionals capitulation_d1

Data: 2026-03-16
Script: `lab/studies/t6f_capitulation_d1_asset_screen.py`
Gate: `lab/docs/D1_GATE_CRITERIA.md` (T6e)

---

## Resultat: 0 nous ACCEPTED_D1_ASSET, 0 nous WATCHLIST

**5 actius nous testats: AMD, NFLX, META, GOOGL, AMZN — tots REJECTED.**

| Ticker | N | WR_b | EV@20x | Liq@20x | WF | MC | MAE | Pass | Status |
|--------|---|------|--------|---------|-----|-----|-----|------|--------|
| AMD | 104 | 46% | -14.3$ | 16.3% | 6/13 | **0%** | 2.0% | 1/8 | REJECTED |
| NFLX | 70 | 59% | -3.2$ | 7.1% | 11/14 | 100% | 1.4% | 4/8 | REJECTED |
| META | 63 | 60% | -3.3$ | 6.3% | 8/12 | 100% | 1.3% | 4/8 | REJECTED |
| GOOGL | 50 | 56% | -4.2$ | 2.0% | 8/12 | 100% | 1.2% | 4/8 | REJECTED |
| AMZN | 62 | 53% | -5.7$ | 6.5% | 8/12 | 100% | 1.7% | 2/8 | REJECTED |

---

## Per asset: per què fallen

### AMD — REJECTED dur (1/8)
- WR baseline = 46% → cap edge (pitjor que random)
- MC shuffle = **0%** → distribució de trades sense edge estadístic
- Liq@20x = 16.3% → MAE massa alta (2.0%), massa liquidacions
- Conclusió: AMD és massa volàtil per a un setup de baixa freqüència D1.
  El setup captura "dips extrems que reboten" però AMD sovint continua baixant.

### NFLX — El cas més interessant (4/8)
- MC = 100%, WF = 11/14 (79%) → **edge real** (senyal estadísticament vàlid)
- MAE mediana = 1.4% → just per sota del threshold (✓ MAE)
- PERÒ liq@20x = 7.1% (> 5%) i EV = -3.2$ (negatiu)
- Per què EV negatiu malgrat edge? Les liquidacions consumeixen les guanys.
  Al 7.1% de liq, cada liquidació costa ~55$ (col + fee); 5 liq en 70 trades = -275$ neta.
- **Nota per futur**: NFLX a 15x (liq_th=6.7%) probablement reduiria liq ≈0-2%
  i l'EV podria ser positiu. Però no entra en T6f (setup i leverage no canvien).

### META — REJECTED (4/8)
- MC=100%, WF=8/12 (67%) → edge estadístic present
- PERÒ: EV = -3.3$. Per què? Liq = 6.3% (sobre el 5%) + 2022 va ser devastador
  (13 trades, WR=46%, -307$ total). El 2022 bear market va generar senyals falsos.
- La tesi de capitulació funciona en bull/neutral però no en bear prolongat a META.

### GOOGL — REJECTED (4/8)
- MC=100%, MAE=1.2%, liq=2.0% → estructura de risc OK
- PERÒ: WR baseline = 56% (< 60% gate), EV = -4.2$
- Els trades guanyen poc quan guanyen i perden bastant quan perden.
  PF baseline = 1.32 massa baix per cobrir fees a 20x.

### AMZN — REJECTED (2/8)
- L'actiu D1 més dolent del screening: EV = -5.7$, liq = 6.5%, MAE = 1.69%
- 2022 amb 14 trades al 29% WR (-321$) destrueix qualsevol edge
- Volatilitat post-Amazon-is-e-commerce-dominant molt alta

---

## Conclusió principal: per què és específic a MSFT/NVDA/QQQ

El setup `capitulation_d1` funciona bé **específicament en actius que, quan cau -2%+ i
trenquen la BB lower en D1, el dia següent tienen una sessió controlada** (MAE < 1.5%).

Aquesta propietat és present en:
- **MSFT**: mega-cap, molt líquid, market makers mantenen preu, rebota ràpidament
- **QQQ** (índex): diversificació interna limita els swings adversos intraday
- **NVDA**: alta volatilitat general PERÒ en els dies post-capitulació específics,
  el rebot tendeix a ser net (semiconductors reaccionen fort als dips extrems)

**No és present en:**
- **AMD**: Alta beta, segueix NVDA però amb menys liquiditat institucional
- **META/GOOGL/AMZN**: Les Big Tech de consum/ads/cloud acostumen a tenir
  múltiples sessions baixes consecutives en drawdowns (no "V-shape recovery")
- **NFLX**: Molt similar a MSFT per estructura (MAE=1.4%), però les liquidacions
  marginals (7.1% vs 5% threshold) trenquen l'EV

**Insight estructural**: el setup identifica "moments de pànic institucional en
mega-cap tech de producció/software" on el smart money compra el close d'una
jornada extrema. No funciona en les FAANG de consum on el sell-off pot ser
fonamental (guidance miss, subscriber loss, etc.).

---

## Univers final recomanat per al paper probe

```
ACCEPTED_D1_ASSET (pillar): MSFT
WATCHLIST (diversificació temporal):  NVDA, QQQ
```

**Configuració del paper probe:**
- Asset primari: **MSFT** (única ACCEPTED_D1_ASSET)
- Secundaris opcionals: **NVDA** i **QQQ** si el senyal no dispara en MSFT
- Leverage: **20x**
- Setup: **capitulation_d1** (body < -2% + close < BB_lower(20,2))
- Durada: ≥ 4 setmanes de mercat actiu

**Valor esperat del portfolio 3 assets (paper):**
- MSFT: ~3.4 senyals/any → ~+12.7$/t
- NVDA: ~5.2 senyals/any → ~+6.0$/t
- QQQ:  ~3.6 senyals/any → ~+3.6$/t
- Total: ~12 senyals/any → EV combinat ~+7$/t weighted

---

## T6f és positiu malgrat 0 actius nous

El resultat de "tots REJECTED" és **informatiu i valuós**, no un fracàs:
1. **Confirma que l'edge no és genèric a tota la renda variable D1**
2. **Confirma que MSFT és la peça central** (no casualitat)
3. **Delimita clarament l'univers**: mega-cap tech de software/hardware, no consum/ads
4. **El paper probe pot dissenyar-se amb focus** en lloc d'un univers gran

L'exploració de T6 (T6 → T6f) ha cobert:
- 3 terrenys (crypto 1H, crypto 4H, equitats D1)
- 28+ setups
- 18+ assets individuals
- Conclusió: 1 ACCEPTED_D1_ASSET (MSFT), 2 WATCHLIST (NVDA, QQQ), 1 WATCHLIST crypto

L'exploració LAB és completada. El terreny és clar.
