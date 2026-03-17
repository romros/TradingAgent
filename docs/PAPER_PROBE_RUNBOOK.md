# PAPER_PROBE_RUNBOOK — TradingAgent T7

## Arrencar el paper probe (T8d: forma canònica)

```bash
# Forma canònica única: Docker Compose
docker compose up -d

# Comprovar que està viu
docker compose ps
# STATUS ha de ser "Up X seconds (healthy)"

# Consulta ràpida "com va?"
curl http://localhost:8090/quick-status
```

**Alternativa sense Docker** (desenvolupament):

```bash
mkdir -p data
export PROBE_ASSETS="MSFT,NVDA,NDXUSD"
export DB_PATH=data/paper_probe.db
pip install -r requirements.txt
uvicorn apps.agent.app:app --host 0.0.0.0 --port 8090
```

**Scheduler automàtic**: el scan diari s'executa sol a les 21:00 UTC (post-close US). Variables: `SCHEDULER_ENABLED=true`, `SCHEDULER_HOUR_UTC=21`.

## Scan manual

```bash
# Via API
curl -X POST http://localhost:8090/scan

# Via script Python directe
cd /mnt/volume-SQ/dev/TradingAgent
python -c "
from packages.shared import config
from packages.strategy.capitulation_d1 import CapitulationD1Strategy
from packages.market.data_feed import YFinanceD1Feed
from packages.execution.paper import PaperExecutor
from packages.portfolio.tracker import PortfolioTracker
from packages.runtime.engine import DailyEngine

engine = DailyEngine(
    assets=config.ASSETS,
    strategy=CapitulationD1Strategy(config.BODY_THRESH, config.BB_PERIOD, config.BB_STD),
    feed=YFinanceD1Feed(),
    executor=PaperExecutor(config.LEVERAGE, config.COL_PCT, config.COL_MAX, config.COL_MIN, config.FEE),
    tracker=PortfolioTracker(config.DB_PATH),
    db_path=config.DB_PATH,
)
print(engine.run())
"
```

## Veure l'estat

```bash
# Consulta ràpida "com va?" (T8d) — curt i útil
curl http://localhost:8090/quick-status

# Salut i mode
curl http://localhost:8090/health

# Estat complet (capital, PnL, trades, últim scan per asset)
curl http://localhost:8090/status

# Resum compacte per verificació diària
curl http://localhost:8090/probe-summary

# Validació paper vs backtest (T7b)
curl http://localhost:8090/validation

# Historial temporal (T7c): scans, validacions, equity curve, drawdown
curl http://localhost:8090/probe-history

# Qualitat del data feed (yfinance)
curl http://localhost:8090/data-quality

# Auditoria BrokerageService (T8a pre-live)
curl http://localhost:8090/bs-audit
# Requereix BS_BASE_URL (default http://localhost:8081) i BrokerageService en marxa

# Validació proxy QQQ (yf) vs NASDAQUSD/NDXUSD (BS) (T8b)
curl http://localhost:8090/proxy-validation
# Correlació returns, classificació aligned|warning|diverged|insufficient_data

# Decision Gate Live Readiness (T8c)
curl http://localhost:8090/live-readiness
# status: LIVE_READY | LIVE_SHADOW_READY | LIVE_NOT_READY; reasons; metrics

# Snapshot diari (T7d) — genera fitxer Markdown a data/probe_snapshots/YYYY-MM-DD.md
curl -X POST http://localhost:8090/snapshot
# Retorna {path, status: ok|warning|error, missing_sections: []}
# S'executa automàticament al final de cada POST /scan

# Senyals detectats
curl http://localhost:8090/signals
curl http://localhost:8090/signals?asset=MSFT&limit=20

# Trades
curl http://localhost:8090/trades
curl http://localhost:8090/trades?status=settled&limit=50
```

## Checklist diari de verificació (T7a)

Executar cada dia després del scan (post-close):

1. **Scan executat avui?**
   ```bash
   curl -s http://localhost:8090/status | jq '.last_scan_utc'
   ```
   Ha de mostrar timestamp d'avui (UTC).

2. **Estat per asset (MSFT, NVDA, NDXUSD)?**
   ```bash
   curl -s http://localhost:8090/status | jq '.last_scan.assets'
   ```
   Cada asset ha de tenir `status: "ok"` o `"warning"`. Si `"error"` → investigar (feed, xarxa).

3. **0 senyals vs error?**
   - `last_scan.status == "ok"` i `assets.*.status == "ok"` → scan correcte, cap senyal avui.
   - `last_scan.status == "error"` → algun asset ha fallat (veure `last_scan.assets` i `last_scan.errors`).

4. **Trades oberts i tancats?**
   ```bash
   curl -s http://localhost:8090/status | jq '.trades'
   ```
   - `open_count`: trades pendents (pending_entry / pending_settlement)
   - `settled_count`, `wins`, `losses`, `pnl_total`, `winrate_pct`

5. **Logs del scan**
   Si s'executa amb `uvicorn`, els logs mostraran:
   - `scan_completed asset=X status=ok signal=false candles=...`
   - `settlement_completed trades_open=N trades_settled=M pnl_total=...`
   - `validation_completed trades=N winrate=X ev=Y status=aligned|warning|diverged`

6. **probe_ok** (determinista)
   - `True` si: últim scan < 48h, cap asset amb status=error, almenys 1 scan registrat
   - `False` altrament

7. **winrate_confidence**
   - `low` si settled_count < 3 (winrate_pct = null)
   - `ok` si settled_count >= 3

8. **Snapshot diari (T7d)**
   - Després del scan, es genera automàticament `data/probe_snapshots/YYYY-MM-DD.md`
   - Conté: trade_summary, last_scan, validation, data_quality, proxy_validation, bs_audit, live_readiness
   - Manual: `curl -X POST http://localhost:8090/snapshot`
   - Log esperat: `daily_snapshot_written path=... status=ok`

## Smoke test (T7a + T8d + T8e)

**Via canònica (Docker-only):**

```bash
./scripts/run.sh smoke
# Artifacts: data/smoke_artifacts/
```

**Validació completa:**

```bash
./scripts/run_all.sh
# component → integration → smoke → soak
```

Esperat: `/status` mostra `probe_ok`, `last_scan` amb `assets`; `/validation` retorna `paper_metrics`, `validation.status`; `/probe-history` retorna `scan_runs`, `validation_runs`, `equity_curve`, `drawdown`; `/data-quality` retorna `status` per asset (ok/warning/error); `/bs-audit` retorna `available`, `data_quality`, `comparison` (aligned/warning/diverged) per asset; `/proxy-validation` retorna `status` (aligned|warning|diverged|insufficient_data), `correlation`, `avg_delta_pct`, `samples`; `/live-readiness` retorna `status` (LIVE_READY|LIVE_SHADOW_READY|LIVE_NOT_READY), `reasons`, `metrics`; `POST /snapshot` genera fitxer a `data/probe_snapshots/YYYY-MM-DD.md` i retorna `{path, status, missing_sections}`.

## Estats de trade

| Estat | Significat |
|-------|-----------|
| `pending_entry` | Senyal detectat, esperant candle T+1 (open) |
| `pending_settlement` | Entrat a open(T+1), esperant close(T+1) |
| `settled` | Tancat normalment (pnl pot ser + o -) |
| `liq_settled` | Liquidat (MAE >= 1/leverage = 5%) → pnl = -collateral - fee |

## Interpretació dels resultats

- **pnl**: guany/pèrdua neta en dòlars (inclou fee)
- **pnl_pct**: rendibilitat sobre el collateral (%)
- **liq_triggered**: si MAE >= 5%, la posició es liquida totalment
- **collateral**: capital arriscat = min(max(capital×20%, 15$), 60$)
- **nominal**: collateral × 20 (leverage 20x)

Exemple amb capital=250$:
- collateral = min(max(50$, 15$), 60$) = 50$
- nominal = 50$ × 20 = 1.000$
- Si close +3%: pnl = 1.000$ × 3% - 5.38$ = +24.62$
- Si MAE >= 5%: pnl = -50$ - 5.38$ = -55.38$

## Criteri de sortida T7 (quan decidir si GO/NO-GO)

El paper probe és considerat vàlid per passar a GO-LIVE si:

1. **Durada**: mínim 4 setmanes de funcionament
2. **Senyals**: >= 3 senyals registrats (mínim estadístic)
3. **Coherència**: win rate i PnL/trade dins del rang del backtest:
   - WR esperat: ~59% (±10%)
   - EV/trade esperat: ~+5.6$ (pot ser negatiu si < 5 trades)
   - Liq rate esperada: ~14%
4. **Integritat**: cap error de fetch > 20% dels scans
5. **Decisió**: revisió manual del projecte confirmant GO-LIVE
