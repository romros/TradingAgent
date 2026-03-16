# Resum per ChatGPT — Cap de Projecte TradingAgent

Copia tot el text i enganxa'l a ChatGPT perquè faci de project manager.

---

## CONTEXT: On som

Estem construint **TradingAgent**, un bot de trading automatitzat en Python que consumeix el nostre BrokerageService (ja en producció) per operar a Ostium (DEX crypto, perpetual futures).

### El que JA està fet

1. **Projecte creat** amb estructura completa:
   - `apps/agent/` — FastAPI app
   - `packages/{runtime,brokerage,market,strategy,risk,execution,portfolio,shared}/`
   - `lab/` — exploració i validació
   - `testing/` — tests unitaris i integració
   - 3 MDs: AGENTS_ARQUITECTURA.md, docs/ESTAT.md, README.md + CLAUDE.md

2. **Estratègia validada: Capitulation Scalp 1H**
   - LONG crypto (ETH, BTC, SOL) després d'un crash extrem en 1H
   - Condicions: body < -3% + close < BB lower(20,2) + drop 3h < -5% + hora no US afternoon
   - 361 trades en 8.6 anys, WR 68%, PF 2.5

3. **Monte Carlo — 3/3 PASS**:
   - Shuffle: 100% de 10.000 sims profitables
   - Random Entry: edge +15-35pp per sobre P95 aleatori (estadísticament significatiu)
   - Parameter Perturbation: 50/50 variants profitables (body ±0.5%, drop ±1%, BB ±3, mult ±0.3)

4. **Walk-Forward — PASS**:
   - Expanding: 7/9 anys positius
   - Rolling 3y: 5/7 anys positius
   - Anys negatius: 2023 (-155$) i 2024 (-206$) — N baix, pèrdues petites

5. **Paper mode**: 2 pèrdues consecutives → mode paper fins que 1 senyal guanyi. Arregla 2023.

### PROBLEMA DESCOBERT: Leverage 100x no viable

El stress test ha revelat que:
- **MAE mediana = 1.50%** (el preu baixa 1.5% de mitjana abans de rebotar)
- **Amb leverage 100x, liquidació a 1%** → el 61% dels trades serien liquidats per Ostium
- El backtest anterior NO simulava la liquidació — els resultats eren optimistes

**Distribució de liquidacions per leverage:**
| Leverage | Liq threshold | % trades liquidats |
|----------|--------------|-------------------|
| 100x | 1.0% | 61% |
| 50x | 2.0% | 40% |
| 30x | 3.3% | 26% |
| 20x | 5.0% | 15% |
| 10x | 10.0% | 5% |

**Kelly criterion**: f* = 47% → sizing actual 20% està dins de Kelly.

### Altres resultats del stress test

- **Worst streak P95**: 7 pèrdues consecutives
- **Paper mode threshold 2**: conservador (P90 streak = 6), podria ser 3
- **Fee sensitivity**: l'estratègia sobreviu fins a fees de 10$ (WR 64%, PF 2.6)
- **MC equity curves**: 77% sims profitables (amb sizing compounding adaptatiu)
- **Max DD P95**: alt (100%) — algunes sims arriben a 0 pel compounding agressiu

---

## EL QUE FALTA FER

### Immediat (blocker)

1. **Refer backtest amb liquidació simulada** a leverage 20x, 30x, 50x
   - Simular que si MAE >= 1/leverage, el trade es tanca amb pèrdua = collateral
   - Trobar el leverage òptim (max rendiment sense liquidacions excessives)
   - Probablement 20-30x serà el sweet spot

2. **Decidir sizing final**: 20% capital amb lev 20x = nominal menor
   - 40$ col × 20x = 800$ nominal (vs 4.000$ amb 100x)
   - Un move de +2.8% (avg win) = +22.4$ brut - 3.36$ fee = +19$ net
   - Un move de -2.1% (avg loss) = -16.8$ brut - 3.36$ fee = -20$ net
   - Amb WR 68%: EV = 0.68 × 19 - 0.32 × 20 = +6.5$/trade
   - 361 trades / 8.6 anys × 6.5$ = +273$/any amb 250$ capital
   - Modest però real i sense liquidacions

### MVP (després de recalibrar leverage)

Ordre d'implementació:
1. `packages/shared/models.py` — dataclasses (Candle, Signal, Trade, AgentState)
2. `packages/portfolio/db.py` — SQLite schema (4 taules)
3. `packages/market/indicators.py` — BB, RSI, drop, vol_rel
4. `packages/strategy/capitulation_scalp.py` — evaluate() → Signal | None
5. `packages/brokerage/client.py` — httpx async cap al BS
6. `packages/execution/{base,paper,live}.py` — IExecutor + 2 implementacions
7. `packages/risk/manager.py` — state machine + sizing
8. `packages/portfolio/tracker.py` — registra signals, trades, equity
9. `packages/runtime/engine.py` — poll_loop + close_loop
10. `apps/agent/{app,routes}.py` — FastAPI endpoints

### V1 (robustesa)

- recovery.py (startup reconciliation)
- pending_actions taula
- reconcile loop formal
- contract tests live executor
- quality gating estricte

### V2 (creixement)

- Multi-strategy (Portfolio D: NVDA dilluns, etc.)
- AI Agent orchestrator (Claude API)
- Web UI

---

## ARQUITECTURA CLAU

- **2 loops**: poll_loop (5min) + close_loop (30s)
- **Paper mode automàtic**: 2 losses → paper → 1 win paper → real
- **1 posició max** simultània
- **Sense SL** (el rebot necessita espai — per això cal baixar leverage)
- **Exit = close de la candle 1H** (hold exactament 1 hora)
- **SQLite**: signals, trades, equity_snapshots, agent_state
- **BrokerageService**: gateway :8081, POST async (202 + operation_id)

---

## QUÈ NECESSITO DE TU (ChatGPT)

Actua com a **cap de projecte**. Ajuda'm a:

1. **Prioritzar**: confirma que l'ordre és correcte (recalibrar leverage primer, després MVP)
2. **Roadmap**: crea un pla de 4 setmanes (leverage fix → MVP → paper testing → go live)
3. **Risk register**: llista de riscos tècnics i operatius amb mitigacions
4. **Definition of Done**: criteris per passar de cada fase a la següent
5. **Weekly check**: cada dilluns, revisa amb mi l'estat i ajusta el pla

Respon en català.
