# T8d-v / T8e: Smoke test validació operativa

**Via canònica (T8e):**

```bash
./scripts/run.sh smoke
```

Artifacts a `data/smoke_artifacts/`.

**Manual (equivalent):**

```bash
docker compose up -d
sleep 8
curl -s http://localhost:8090/health
curl -s http://localhost:8090/quick-status
curl -s -X POST http://localhost:8090/scan
ls -la data/probe_snapshots/
docker compose down
```
