# Resum per ChatGPT — Cap de Projecte TradingAgent

Actualitzat: 2026-03-16 (post-T6)

---

## ESTAT: LAB — crypto 1H esgotat, cal pivot

**Repo:** github.com/romros/TradingAgent
**Gate de producció:** BUILD només si cas econòmic suficient (AGENTS §9)

### Tasques tancades (T1-T6)

| Tasca | Resultat |
|-------|----------|
| T1 | Leverage 20x (100x descartada, 61% liquidacions) |
| T2 | Gate de producció establert |
| T3 | Contracte canònic: SetupSpec, ValidationResult, OpportunityEstimate |
| T4 | Inventari: 1 WATCHLIST (Capitulation), 2 REJECTED (Markov) |
| T5 | Harness de validació: pipeline 7 passes, smoke PASS |
| **T6** | **6 setups explorats: 4 REJECTED, 1 WATCHLIST (N=11). Crypto 1H esgotat** |

---

## T6: Què ha passat

### 3 famílies × 2 hipòtesis testejades

| Setup | Family | N | WR | MC shuffle | MC edge | WF | Status |
|-------|--------|---|-----|-----------|---------|-----|--------|
| capitulation_scalp (ref) | capitulation | 361 | 68% | 100% | +24.6pp | 8/10 | WATCHLIST |
| bb_squeeze_breakout | breakout | 1105 | 38% | **0%** | -5.6pp | 3/10 | **REJECTED** |
| atr_low_big_candle | breakout | 137 | 37% | **0%** | -6.0pp | 4/10 | **REJECTED** |
| sweep_reclaim | mean_reversion | 11365 | 43% | **0%** | -0.3pp | 1/10 | **REJECTED** |
| hammer | pattern | 9307 | 41% | **0%** | -2.6pp | 1/10 | **REJECTED** |
| trend_rsi_dip | momentum | 11 | 73% | 100% | +29.7pp | 3/4 | WATCHLIST |
| pullback_ema20 | momentum | 11967 | 42% | **0%** | -0.8pp | 1/10 | **REJECTED** |

### L'insight dur

**Patrons clàssics de TA no funcionen a crypto 1H amb fees d'Ostium:**
- Breakout, hammer, pullback, sweep → tots WR 37-43% (pitjor que random!)
- MC shuffle = 0% per tots (cap simulació profitable)
- Les fees de 3.36$/trade destrueixen qualsevol petit edge

**L'únic que funciona**: condicions extremes (crash -3%+ amb BB lower + drop 3H). Però és rar (18 trades/any) i l'EV amb liquidació és modest (+4-5.6$/trade).

**Trend RSI dip** mostra edge (MC 100%, +29.7pp) però N=11 és massa poc.

---

## LA PREGUNTA PER AL PM

El LAB crypto 1H s'ha esgotat. Tenim:
- 1 setup real (Capitulation, WATCHLIST, EV modest)
- 0 setups nous viables a crypto 1H
- El harness funciona i mata ràpid el que no serveix

### 3 opcions

**Opció A: Pivot de terreny**
- Explorar TF 4H o D1 (menys fees relatives al move)
- Explorar assets no-crypto (equitats D1 via yfinance — ja parcialment validat a SQRunner: NVDA, Nasdaq, MSFT mostraven edge a D1)
- El harness ja està preparat per qualsevol TF/asset

**Opció B: Construir igualment**
- Acceptar que Capitulation sol dona ~100$/any amb 250$
- Construir el bot com a **infraestructura reutilitzable** (V2 multi-strategy)
- El valor no és el rendiment actual sinó la plataforma

**Opció C: Tancar LAB**
- L'edge real no justifica l'esforç
- Centrar recursos en altres projectes

---

## QUÈ NECESSITO DE TU

1. **Decisió**: A, B o C? (o combinació)

2. **Si A**: quins actius i TF exploraries primer? El harness ja funciona — només cal generar trades amb nous signal generators

3. **Si B**: confirma que vale la pena +100$/any amb 250$ com a learning investment per la infraestructura

4. **Criteri per tancar**: quants cicles d'exploració més (T6b, T6c...) abans de decidir definitivament?

Respon en català. Sigues directe.
