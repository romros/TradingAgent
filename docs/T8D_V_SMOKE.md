# T8d-v: Smoke test validació operativa

Executar per verificar T8d amb config NDXUSD:

```bash
# 1. Arrencar
docker compose up -d
sleep 8

# 2. Comprovar contenidor
docker compose ps
# Esperat: STATUS "Up X seconds (healthy)"

# 3. Logs startup
docker compose logs | grep -E "agent_started|daily_scheduler_registered"
# Esperat: agent_started ... assets=MSFT,NVDA,NDXUSD
# Esperat: daily_scheduler_registered next_run_utc=...

# 4. API
curl -s http://localhost:8090/health | jq .
# Esperat: {"status":"ok","mode":"paper","assets":["MSFT","NVDA","NDXUSD"]}

curl -s http://localhost:8090/quick-status | jq .
# Esperat: ok, probe_ok, trades, validation, live_readiness

# 5. Scan real
curl -s -X POST http://localhost:8090/scan | jq .

# 6. Snapshot
ls -la data/probe_snapshots/
# Esperat: 1 fitxer YYYY-MM-DD.md

# 7. Aturar
docker compose down
```
