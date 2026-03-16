# PAPER_PROBE_RUNBOOK — TradingAgent T7

## Arrencar el paper probe

```bash
# Crear directori de dades
mkdir -p data

# Variables d'entorn (opcionals, tots tenen defaults)
export PROBE_ASSETS="MSFT,NVDA,QQQ"
export LEVERAGE=20
export CAPITAL_INITIAL=250.0
export COL_PCT=0.20
export COL_MAX=60.0
export COL_MIN=15.0
export FEE=5.38
export BODY_THRESH=-0.02
export BB_PERIOD=20
export BB_STD=2.0
export DB_PATH=data/paper_probe.db
export DATA_LOOKBACK_DAYS=365

# Arrencar FastAPI
pip install fastapi uvicorn yfinance
uvicorn apps.agent.app:app --host 0.0.0.0 --port 8090
```

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
# Salut i mode
curl http://localhost:8090/health

# Estat complet (capital, PnL, trades)
curl http://localhost:8090/status

# Senyals detectats
curl http://localhost:8090/signals
curl http://localhost:8090/signals?asset=MSFT&limit=20

# Trades
curl http://localhost:8090/trades
curl http://localhost:8090/trades?status=settled&limit=50
```

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
