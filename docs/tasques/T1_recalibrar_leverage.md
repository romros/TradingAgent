# TASCA — Recalibrar leverage MVP amb liquidació simulada

## 0) Referències canòniques
- `AGENTS_ARQUITECTURA.md`: §6 Sizing i regles operatives, §9 Fases
- `docs/ESTAT.md`: ALERTA Leverage 100x no viable
- `lab/studies/mc_walkforward_capitulation.py`
- `lab/studies/stress_test_capitulation.py`

## Estat: TANCAT ✅

## Resultat

**Leverage MVP: 20x** (runner-up: 15x)

| Lev | Liq% | WR | PF | EV/trade | 250$→ | MaxDD | Anys +/- |
|-----|------|-----|-----|----------|-------|-------|----------|
| 10x | 5% | 56% | 1.3 | +2.0$ | 560$ | 28% | 3+/6- |
| **15x** | **9%** | **59%** | **1.4** | **+4.3$** | **924$** | **23%** | **5+/5-** |
| **20x** | **14%** | **59%** | **1.4** | **+5.6$** | **1.114$** | **37%** | **5+/5-** |
| 30x | 24% | 58% | 1.5 | +9.2$ | 1.596$ | 28% | 5+/5- |
| 50x | 38% | 50% | 1.7 | +16.4$ | 2.369$ | 17% | 8+/2- |
| 100x | 68% | 21% | 0.7 | -7.1$ | 10$ | 98% | 0+/3- |

### Criteri de decisió
Max EV amb liquidació ≤20% i MaxDD ≤60%

### Artifacts
- Script: `lab/studies/leverage_recalibration.py`
- Dades: `lab/out/leverage_recalibration.json`
- AGENTS_ARQUITECTURA.md §6 i §11 actualitzats
- docs/ESTAT.md actualitzat
