# D1_GATE_CRITERIA.md — Gate específic per setups D1 per asset

Creat: 2026-03-16 (T6e)

---

## Motivació: per què el gate general no s'aplica a D1

El gate general del LAB exigeix `N >= 120` i `trades/any >= 12`. Aquests criteris
estan calibrats per setups d'alta freqüència (1H, 4H) on un any pot generar
desenes de senyals per asset.

Per setups D1 de baixa freqüència (`capitulation_d1`), la realitat estructural és:
- Freqüència: **3–5 esdeveniments/asset/any** (dips extrems de mercat)
- Amb 12 anys de dades: **N màxim assolible ≈ 40–70 per asset**
- Per arribar a N=120 caldria **30+ anys de dades** — impossible a la pràctica

Això no és un problema de qualitat del setup. És un **límit de freqüència del terreny**.

Aplicar el gate general als setups D1 per asset equivaldria a descartar
un mètode per haver-lo testat en pocs casos, quan la baixa freqüència és
precisament la propietat que el fa estadísticament net (poca soroll, senyals extrems).

**El gate D1 per asset adapta els criteris de volum al terreny real,
mantenint els criteris de qualitat iguals o més estrictes.**

---

## Gate D1 per asset — Definició formal

### ACCEPTED_D1_ASSET

Estat intermedi entre `WATCHLIST` i `ACCEPTED` general. Significa:
- Prou evidència per sortir del LAB pur
- Prou qualitat per justificar un paper probe mínim
- **No** equival a autorització de BUILD complet

| Criteri | Threshold | Justificació |
|---------|-----------|--------------|
| **N** | **≥ 35** | Mínima robustesa per 10+ anys D1 (vs 120 general, impossible per baixa freq.) |
| **WR baseline** | **≥ 60%** | Edge suficient per cobrir fees a leverage moderat |
| **EV deployable** | **≥ +8$/trade** | Cas econòmic clar (idèntic al gate general) |
| **PF deployable** | **≥ 1.8** | Relació guany/pèrdua robusta (més exigent que gate general 1.30) |
| **Liq rate** | **≤ 5%** al leverage operatiu | Protecció capital (25% del 20% col·lateral) |
| **WF** | **≥ 70%** anys positius | Estabilitat temporal robusta (idèntic al general) |
| **MC shuffle** | **≥ 90%** sims profitables | Edge estadísticament real |
| **MAE mediana** | **≤ 1.5%** | Amplitud adversa controlada a leverage moderat |

**Tots 8 criteris han de passar simultàniament.**

### WATCHLIST (D1)

Quan el setup mostra edge real i MC/WF robustos però no arriba als thresholds
d'ACCEPTED_D1_ASSET. Útil per portfolio combinat. No autoritza paper probe sol.

Condicions per WATCHLIST D1:
- N ≥ 20
- MC shuffle ≥ 90%
- WF ≥ 60% anys positius
- EV deployable > 0
- Falla com a màxim 2 criteris del gate ACCEPTED_D1_ASSET

### REJECTED (D1)

- MC shuffle < 90% (no hi ha edge estadístic)
- O WF < 60% anys positius
- O EV deployable ≤ 0
- O N < 20

---

## Comparativa de gates

| Criteri | Gate general | Gate D1 per asset | Diferència |
|---------|-------------|-------------------|------------|
| N mínim | 120 | **35** | ↓ Adaptat a freq. baixa |
| Trades/any | ≥ 12 | **≥ 3** | ↓ Adaptat a D1 |
| EV/trade | ≥ +8$ | **≥ +8$** | = Idèntic |
| PF deployable | ≥ 1.30 | **≥ 1.8** | ↑ Més exigent |
| Liq rate | ≤ 15% | **≤ 5%** | ↑ Més exigent |
| WR | ≥ 55% | **≥ 60%** | ↑ Més exigent |
| WF | ≥ 70% | **≥ 70%** | = Idèntic |
| MC shuffle | ≥ 90% | **≥ 90%** | = Idèntic |
| MAE mediana | — | **≤ 1.5%** | + Criteri nou |

**Resum**: N i freqüència s'adapten a la baixa (realitat del terreny), però
tots els criteris de qualitat del setup es mantenen igual o s'endureixen.
Això garanteix que no estem "rebaixant el llistó" sinó "canviant l'escala".

---

## Aplicabilitat

Aquest gate s'aplica **únivocament** a:
- Setups D1 per asset individual
- Família `capitulation_d1` (body < -2% + close < BB_lower)
- Assets amb dades disponibles ≥ 10 anys

**No s'aplica a:**
- Setups multi-asset combinats (usar gate general adaptat)
- Setups intraday (1H, 4H)
- Portfolios (criteris de portfolio separats)

---

## Guardrail anti-cherry-picking

**Qualsevol adaptació futura d'aquest gate ha d'estar motivada exclusivament
per la freqüència estructural del timeframe, no pel desig de "salvar" un resultat
concret.**

Si en una revisió futura es vol modificar un threshold, cal:
1. Justificar amb la distribució de freqüència del setup (no amb els números d'un asset)
2. Aplicar el canvi a tots els assets simultàniament
3. Documentar el canvi amb data i motiu en aquest fitxer
