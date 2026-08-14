# Alquímia dashboard

Panell local, de només lectura, per seguir SQCLI, la recerca IBKR i la cartera
shadow SXR8 + CAT 0.168.

```bash
python3 -m lab.dashboard.server --host 127.0.0.1 --port 8765
```

Obre `http://127.0.0.1:8765`. L'API `GET /api/status` agrega els heartbeats,
registre v2, preflights i futurs rebuts de `data/ibkr_sq_v2`, a més de les
mètriques del contenidor. També llegeix els ledgers shadow per mostrar posicions
hipotètiques, però mai els modifica. No inicia, atura ni modifica SQCLI, i no
autoritza paper ni live.
