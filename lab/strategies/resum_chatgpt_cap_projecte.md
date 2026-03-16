# Resum per ChatGPT — Cap de Projecte TradingAgent

Copia tot el text i enganxa'l a ChatGPT perquè faci de project manager.
Actualitzat: 2026-03-16 (post-T4)

---

## ESTAT DEL PROJECTE

**Fase: LAB — recerca de setups**
**Repo:** github.com/romros/TradingAgent (6 commits a main)
**Gate de producció:** BUILD només si cas econòmic suficient (AGENTS §9)

---

## TASQUES TANCADES

### T1 — Leverage recalibrat amb liquidació simulada ✅

El backtest original (WR 68%, 250$→18.000$) no simulava liquidació d'Ostium. Amb lev 100x i MAE mediana 1.50%, el 61% dels trades es liquidarien.

Backtest refet amb liquidació real:

| Lev | Liq% | WR | PF | EV/trade | 250$→ | MaxDD | Anys +/- |
|-----|------|-----|-----|----------|-------|-------|----------|
| 15x | 9% | 59% | 1.4 | +4.3$ | 924$ | 23% | 5+/5- |
| **20x ← decidit** | **14%** | **59%** | **1.4** | **+5.6$** | **1.114$** | **37%** | **5+/5-** |
| 30x | 24% | 58% | 1.5 | +9.2$ | 1.596$ | 28% | 5+/5- |
| 100x | 68% | 21% | 0.7 | -7.1$ | 10$ | 98% | 0+/3- |

**Decisió: leverage MVP = 20x.** EV real: +5.6$/trade × 18t/any = ~100$/any amb 250$.

### T2 — Documents alineats, gate de producció ✅

- AGENTS_ARQUITECTURA.md §9: gate explícit ("no BUILD sense rendibilitat suficient")
- Fases reordenades: LAB → GO/NO-GO → BUILD → PAPER → LIVE
- README reflecteix fase LAB

### T3 — Contracte canònic del LAB ✅

3 estructures definides a `lab/contracts/models.py`:

- **SetupSpec**: descripció declarativa d'un setup (nom, tesi, condicions, features, scoring)
- **SetupValidationResult**: mètriques completes (WR, PF, MFE/MAE, liq per leverage, MC, WF, yearly)
- **OpportunityEstimate**: estimació temps real (MFE/MAE 4H/1H, liq_risk, score, confiança)

Marc temporal: **4H context / 1H execution**
Cicle de vida: CANDIDATE → ACCEPTED | WATCHLIST | REJECTED
Documentació: `lab/docs/SETUPS_CONTRACTE.md`
Exemple complet: Capitulation Scalp omplert amb dades reals (5/5 tests PASS)

### T4 — Inventari i catàleg del LAB ✅

16 fitxers inventariats. Resultat:

| Setup | Family | Status | Motiu |
|-------|--------|--------|-------|
| **Capitulation Scalp 1H** | capitulation | **WATCHLIST** | Edge real (MC 3/3 PASS), EV modest amb liq 20x. 5+/5- anys |
| Markov HMM Regime | pattern | **REJECTED** | HMM falla 2026 (no detecta bear enmig de -43%) |
| Markov trigrams | pattern | **REJECTED** | Overfitting amb qualsevol nombre d'estats |

**Conclusió T4**: El LAB té 1 setup real (WATCHLIST) i 2 morts (Markov). L'evolució investigadora ha estat sana (Markov → HMM → Indicadors simples → Capitulation). El setup sol no justifica BUILD — cal més peces.

Documents creats:
- `lab/docs/LAB_INVENTARI.md` — inventari complet amb categoria/estat/acció per fitxer
- `lab/docs/SETUPS_CATALOG.md` — catàleg orientat a decisió amb vista setup×asset×tf×status

---

## ON SOM ARA

### El que tenim
- 1 setup WATCHLIST amb edge real però EV modest
- Contracte canònic definit i funcional
- Metodologia de validació provada (MC + WF + stress + liq)
- Arquitectura productiva definida (però no construïda — gate actiu)

### El que NO tenim
- Prou edge per justificar BUILD
- Diversitat de setups (1 sola família: capitulation)
- Portfolio combinat que millori l'EV agregat
- Setups no-crypto (D1 equitats, XAU, etc.)

---

## ROADMAP LAB (T5-T9)

| Tasca | Objectiu | Depèn de |
|-------|----------|----------|
| **T5** | Harness comú de validació (unificar backtest+liq+MFE/MAE+fees) | T3, T4 |
| **T6** | Matriu setup × asset × tf — explorar nous setups | T5 |
| **T7** | Funció d'oportunitat per agents de risc/exit | T6 |
| **T8** | Portfolio candidat — avaluar conjunt | T6, T7 |
| **T9** | Decisió BUILD_AUTHORIZED o LAB_CONTINUES | T8 |

---

## QUÈ NECESSITO DE TU (ChatGPT)

Ets el **cap de projecte**. Amb T1-T4 tancades:

1. **Valida el roadmap T5-T9**: és l'ordre correcte? Falta alguna cosa?

2. **Reflexiona sobre el catàleg**: amb 1 WATCHLIST i 2 REJECTED, quines línies d'investigació recomanaries per T6? (noves famílies? nous assets? portfolio approach?)

3. **Defineix criteri go/no-go concret**: quin EV/trade mínim, quin WR mínim, quants setups actius fan falta per autoritzar BUILD? Necessitem un número, no un principi.

4. **Detalla T5**: si estàs d'acord que T5 és la següent tasca, ajuda'm a definir-la amb la plantilla (què ha de fer el harness exactament, quines mètriques, quin format de sortida).

Respon en català. Continua sent honest.
