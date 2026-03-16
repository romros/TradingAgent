# T6E_DECISIO_D1_ASSETS.md — Decisió final assets D1

Data: 2026-03-16
Gate aplicat: `D1_GATE_CRITERIA.md` (ACCEPTED_D1_ASSET)
Dades: T6d leverage sweep (10 assets × 6 leverages, yfinance 2013–2026)

---

## Resum executiu

**MSFT passa el gate ACCEPTED_D1_ASSET (8/8 criteris).**

**Decisió final: `PAPER_PROBE_AUTHORIZED`**

---

## Aplicació del gate als 4 assets

### Gate: 8 criteris, tots han de passar

| Criteri | Threshold | MSFT | NVDA | QQQ | SPY |
|---------|-----------|------|------|-----|-----|
| N | ≥ 35 | **41 ✓** | **68 ✓** | **40 ✓** | 23 ✗ |
| WR baseline | ≥ 60% | **78% ✓** | **63% ✓** | **63% ✓** | **74% ✓** |
| EV deployable @20x | ≥ +8$ | **+12.7$ ✓** | +6.0$ ✗ | +3.6$ ✗ | +3.3$ ✗ |
| PF deployable @20x | ≥ 1.8 | **3.46 ✓** | 1.61 ✗ | 1.53 ✗ | 1.46 ✗ |
| Liq rate @20x | ≤ 5% | **0.0% ✓** | 4.4% ✓ | 2.5% ✓ | 4.3% ✓ |
| WF anys positius | ≥ 70% | **10/12=83% ✓** | **11/13=85% ✓** | **7/8=88% ✓** | **7/8=88% ✓** |
| MC shuffle | ≥ 90% | **100% ✓** | **100% ✓** | **100% ✓** | **100% ✓** |
| MAE mediana | ≤ 1.5% | **0.75% ✓** | 1.55% ✗ | 1.32% ✓ | **1.04% ✓** |
| **PASS/TOTAL** | **8/8** | **8/8 ✓** | **5/8** | **6/8** | **4/8** |

---

## Classificació final

### MSFT → `ACCEPTED_D1_ASSET`

**Passa tots 8 criteris del gate D1.**

Mètriques clau:
- N=41, WR baseline=78%, PF@20x=3.46, EV@20x=+12.7$
- Liq@20x=**0%** (cap liquidació en 41 trades — excepcional)
- WF=10/12 anys positius (83.3%)
- MAE mediana=0.75% (molt confortabla a 20x amb liq_th=5%)
- MC shuffle=100%, CAGR simulat ~10%

Per què és el millor asset: la MAE extremament baixa (0.75%) reflecteix
que MSFT D1 té moviments intraday molt mesurats. Gairebé cap sessió baixa
>5% des de l'open — per tant, el leverage de 20x és segur en aquest asset
amb aquesta família de setup.

### NVDA → `WATCHLIST`

Falla 3 criteris: EV (+6.0$ < 8$), PF (1.61 < 1.8), MAE mediana (1.55% > 1.5%).

La MAE falla per molt poc (1.55% vs 1.5%). L'EV és real però no arriba al
threshold econòmic sol. Molt útil com a component de portfolio combinat
(N=68, el major de tots, WF 11/13=85%). Si l'EV pujés per efecte portfolio
(diversificació temporal), podria reconsiderar-se.

### QQQ → `WATCHLIST`

Falla 2 criteris: EV (+3.6$ << 8$), PF (1.53 < 1.8).

L'EV és massa baix per justificar operació individual. La correlació elevada
amb el mercat general (índex Nasdaq 100) i amb SPY indica que les seves
senyals coincidiran molt amb les de MSFT (ambdues activen en crashes de mercat).
Rol: **diversificació geogràfica/sectorial dins el portfolio**, no asset primari.

### SPY → `REJECTED`

Falla 4 criteris incloent el criteri dur de N (23 < 35).

Amb N=23 en 12 anys (1.9 t/any), la mida mostral és massa petita per qualsevol
decisió estadísticament fonamentada. Les mètriques semblen bones (WR 74%, MAE
mediana 1.04%) però amb N tan petit, un sol any negatiu (com 2024: 2t, 0% WR)
representa el 12.5% de la mostra. Inestable.

Nota: SPY i QQQ estan altament correlacionats (ambdós reflecteixen el mercat
US). Tenir els dos en portfolio afegeix poca diversificació. SPY es descarta.

---

## Perquè MSFT és excepcional entre D1

| Propietat | MSFT | Resta D1 | Per què importa |
|-----------|------|----------|-----------------|
| MAE mediana | **0.75%** | 1.0–1.6% | Leverage 20x segur (liq_th=5%) |
| Liq@20x | **0%** | 2.5–4.4% | Zero capital perdut per liquidació |
| WR baseline | **78%** | 62–74% | 4 de cada 5 trades guanyen |
| PF@20x | **3.46** | 1.46–1.61 | Per cada $ perdut → 3.46$ guanyats |
| WF | **10/12=83%** | 85–88% | Consistent, no un accident d'uns anys |
| EV@20x | **+12.7$** | +3.3–6.0$ | Únic que supera el gate econòmic |

La diferència entre MSFT i la resta no és estadística — és estructural.
MSFT D1 té moviments intraday petits (MAE baixa) però closes D1 grans
(quan cau -2%+ intradiari, el dia següent rebota amb força). Aquesta
asimetria és la base del setup i és molt consistent en MSFT.

---

## Autorització del paper probe

**Regla 4 del gate**: el paper probe mínim queda autoritzat si existeix ≥1 asset
`ACCEPTED_D1_ASSET` clar, o ≥2 assets `WATCHLIST` molt forts.

Condició complerta: **MSFT = ACCEPTED_D1_ASSET** (8/8 criteris).

### Abast del paper probe autoritzat

El paper probe cobrirà:
- Asset principal: **MSFT** (ACCEPTED_D1_ASSET)
- Assets secundaris opcionals: **NVDA** i **QQQ** (WATCHLIST — útils com a
  diversificació temporal si el senyal de MSFT no dispara)
- Setup: `capitulation_d1` (body < -2% + close < BB_lower(20,2))
- Leverage: **20x** (liq 0% per MSFT, dins liq<=5% per NVDA i QQQ)
- Durada mínima: **4 setmanes** de mercat actiu

### El que NO autoritza aquest estat

- BUILD complet de la plataforma
- Operació real amb capital
- Extensió a nous setups o famílies
- Inclusió de crypto (setup independent, no avaluat aquí)

---

## Decisió final

```
MSFT  = ACCEPTED_D1_ASSET  (8/8 criteris)
NVDA  = WATCHLIST          (5/8: falla EV, PF, MAE marginal)
QQQ   = WATCHLIST          (6/8: falla EV, PF)
SPY   = REJECTED           (4/8: N insuficient)

PAPER_PROBE_AUTHORIZED
  Asset primari: MSFT
  Leverage: 20x
  Durada: ≥4 setmanes
  Condició de revisió: after 4 setmanes → go/no-go real
```

---

## Pròxim pas

Si s'accepta aquesta decisió: definir la **tasca de paper probe mínim**, que ha
de cobrir com a mínim:
- Detecció de senyal automàtica (o manual) per MSFT D1
- Registre de fills i slippage esperat
- Comparació amb EV backtest (+12.7$) vs EV real paper
- Criteris de go/no-go per operació real al final de les 4 setmanes
