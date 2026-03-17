# Scripts — TradingAgent

**Propòsit:** Validació canònica Docker-only. Cap prova compta si s'executa al host.

---

## Canònics (T8e)

| Script | Funció |
|--------|--------|
| `run.sh` | Wrapper de proves: component, integration, smoke, soak |
| `run_all.sh` | Pipeline complet: component → integration → smoke → soak |
| `run_tests.sh` | Delegació a run.sh component (unit/integration/all) |

---

## Ús

```bash
# Validació completa (recomanat)
./scripts/run_all.sh

# Per tipus
./scripts/run.sh component    # scripts Python purs testing/unit (0-network)
./scripts/run.sh integration  # scripts Python purs testing/integration (si existeix)
./scripts/run.sh smoke        # servei arrencat, /health, /quick-status, POST /scan, snapshot
./scripts/run.sh soak         # servei viu N minuts (SOAK_MINUTES=2 per defecte)

# Tests unitaris
./scripts/run_tests.sh unit
./test.sh                    # equival a run.sh component
./test.sh testing/unit/test_paper_probe.py  # fitxer concret
```

---

## Variables

| Variable | Default | Descripció |
|----------|---------|------------|
| `PROBE_URL` | http://localhost:8090 | URL del probe |
| `SOAK_MINUTES` | 2 | Minuts de soak |
| `ARTIFACTS_DIR` | data/smoke_artifacts, data/soak_artifacts | Directori d'artifacts |

---

## Artifacts

- **Smoke:** `data/smoke_artifacts/{ts}_health.json`, `_quick_status.json`, `_scan.json`, `_snapshot.md`, `_ps.txt`
- **Soak:** `data/soak_artifacts/{ts}_soak.log`

---

## Regles

1. Cap prova compta com a validació operativa si s'executa al host.
2. `run_all.sh` és la via canònica de validació completa.
3. Smoke i soak proven el sistema realment arrencat dins Docker.
