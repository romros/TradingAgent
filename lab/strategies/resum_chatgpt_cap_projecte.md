# Resum per ChatGPT — Cap de Projecte TradingAgent

Copia tot el text i enganxa'l a ChatGPT perquè faci de project manager.

---

## CONTEXT: On som (actualitzat post-T1)

Estem construint **TradingAgent**, un bot de trading automatitzat en Python que consumeix el nostre BrokerageService (ja en producció) per operar a Ostium (DEX crypto, perpetual futures).

**Repo:** github.com/romros/TradingAgent

### El que JA està fet

1. **Projecte creat** amb estructura completa:
   - `apps/agent/` — FastAPI app
   - `packages/{runtime,brokerage,market,strategy,risk,execution,portfolio,shared}/`
   - `lab/` — exploració i validació
   - `testing/` — tests unitaris i integració
   - 3 MDs: AGENTS_ARQUITECTURA.md, docs/ESTAT.md, README.md + CLAUDE.md
   - Plantilla de tasca: `docs/plantilla_tasca.md`

2. **Estratègia validada: Capitulation Scalp 1H**
   - LONG crypto (ETH, BTC, SOL) després d'un crash extrem en 1H
   - Condicions: body < -3% + close < BB lower(20,2) + drop 3h < -5% + hora no US afternoon
   - 361 trades en 8.6 anys (dades Binance 1H)

3. **Monte Carlo — 3/3 PASS**:
   - Shuffle: 100% de 10.000 sims profitables
   - Random Entry: edge +15-35pp per sobre P95 aleatori (estadísticament significatiu)
   - Parameter Perturbation: 50/50 variants profitables (body ±0.5%, drop ±1%, BB ±3, mult ±0.3)

4. **Walk-Forward — PASS**:
   - Expanding: 7/9 anys positius
   - Rolling 3y: 5/7 anys positius

5. **Paper mode**: 2 pèrdues consecutives → mode paper fins que 1 senyal guanyi

### T1 TANCAT: Leverage recalibrat amb liquidació simulada

**Problema**: el backtest original (WR 68%, 250$→18.000$) no simulava la liquidació d'Ostium. Amb leverage 100x i MAE mediana 1.50%, el 61% dels trades serien liquidats abans del rebot.

**Solució**: backtest refet amb liquidació real (si MAE >= 1/leverage → pnl = -collateral):

| Lev | Liq% | WR | PF | EV/trade | 250$→ | MaxDD | Anys +/- |
|-----|------|-----|-----|----------|-------|-------|----------|
| 10x | 5% | 56% | 1.3 | +2.0$ | 560$ | 28% | 3+/6- |
| **15x** | **9%** | **59%** | **1.4** | **+4.3$** | **924$** | **23%** | **5+/5-** |
| **20x ← MVP** | **14%** | **59%** | **1.4** | **+5.6$** | **1.114$** | **37%** | **5+/5-** |
| 30x | 24% | 58% | 1.5 | +9.2$ | 1.596$ | 28% | 5+/5- |
| 50x | 38% | 50% | 1.7 | +16.4$ | 2.369$ | 17% | 8+/2- |
| 100x | 68% | 21% | 0.7 | -7.1$ | 10$ | 98% | 0+/3- |

**Decisió: leverage MVP = 20x**
- Criteri: max EV amb liquidació ≤20% i MaxDD ≤60%
- Runner-up: 15x (MaxDD 23%, més conservador)
- EV real: +5.6$/trade × 18 trades/any = ~100$/any amb 250$
- Sizing: 20% capital, lev 20x → nominal ~800$ per trade
- AGENTS_ARQUITECTURA.md §6 i §11 actualitzats

### Reflexió important sobre els números

L'estratègia **funciona** (edge real demostrat per MC), però amb liquidació simulada els resultats són **modestos**:
- 250$ → 1.114$ en 8.6 anys (x4.5, no x50 com pensàvem)
- 5 anys positius, 5 negatius (de 10)
- EV +5.6$/trade amb 14% de liquidacions

La pregunta és: **val la pena construir un bot per +100$/any amb 250$?**
Possibles respostes:
- Sí, si es veu com a **infraestructura** reutilitzable per futures estratègies (multi-strategy V2)
- Sí, si s'escala amb **més capital** (2.500$ → ~1.000$/any)
- No, si l'objectiu és rendiment a curt termini

---

## EL QUE FALTA FER

### MVP (leverage ja decidit, contracte alineat)

Ordre d'implementació:
1. `packages/shared/models.py` — dataclasses (Candle, Signal, Trade, AgentState)
2. `packages/portfolio/db.py` — SQLite schema (4 taules)
3. `packages/market/indicators.py` — BB, RSI, drop, vol_rel
4. `packages/strategy/capitulation_scalp.py` — evaluate() → Signal | None
5. `packages/brokerage/client.py` — httpx async cap al BS
6. `packages/execution/{base,paper,live}.py` — IExecutor + 2 implementacions
7. `packages/risk/manager.py` — state machine + sizing (leverage 20x)
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
- **Leverage: 20x** (decidit T1, amb liquidació simulada)
- **Sizing**: col = min(max(capital × 20%, 15$), 60$), lev 20x
- **Paper mode automàtic**: 2 losses → paper → 1 win paper → real
- **1 posició max** simultània
- **Sense SL** (el rebot necessita espai — per això lev 20x, no 100x)
- **Exit = close de la candle 1H** (hold exactament 1 hora)
- **SQLite**: signals, trades, equity_snapshots, agent_state
- **BrokerageService**: gateway :8081, POST async (202 + operation_id)

---

## QUÈ NECESSITO DE TU (ChatGPT)

Actua com a **cap de projecte**. Tens la tasca T1 tancada (leverage). Ara:

1. **Reflexiona**: amb els números reals (x4.5 en 8.6 anys, 5+/5- anys), val la pena construir l'MVP? O millor invertir el temps en buscar una estratègia amb millor edge?

2. **Si avancem amb MVP**: crea un **roadmap de 4 setmanes** (MVP → paper testing → go live) amb tasques concretes per setmana

3. **Risk register**: actualitza amb el risc de "liquidació intrabar" que hem descobert

4. **Definition of Done**: criteris per dir "MVP llest per paper testing"

5. **Alternativa**: si consideres que l'EV és massa baix, proposa un pla B (millorar l'estratègia? canviar d'asset? canviar d'exchange amb menys fees?)

Respon en català. Sigues honest — prefereixo una recomanació dura que no pas optimisme buit.
