# Alquímia dashboard

Panell local, de només lectura, per seguir SQCLI i la recerca IBKR.

```bash
python3 -m lab.dashboard.server --host 127.0.0.1 --port 8765
```

Obre `http://127.0.0.1:8765`. L'API `GET /api/status` agrega els heartbeats,
registre v2, preflights i futurs rebuts de `data/ibkr_sq_v2`, a més de les
mètriques del contenidor. Exclou deliberadament candidats v1. No inicia, atura
ni modifica SQCLI, i no autoritza paper ni live.
