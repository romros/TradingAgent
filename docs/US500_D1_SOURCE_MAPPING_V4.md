# US500 D1 — mapping SQ/Dukascopy a Ostium per Alquímia v4

## Decisió

`PASS_D1_SOURCE_MAPPING`, exclusivament per recerca D1 sobre la sessió regular
09:30–16:00 de Nova York. No autoritza rendiment, SQCLI, paper ni live.

El mapping M15 anterior queda per sota del mínim v4 de correlació (0,98946 <
0,99). No es relaxa el llindar. Per a la línia US500+VIX s'utilitzarà D1 perquè
el VIX oficial disponible és un tancament diari i només pot afectar la sessió
posterior.

## Contracte congelat abans del resultat

- 390 minuts esperats per sessió;
- només es considera completa una font amb cobertura ≥95% aquell dia;
- es retallen simètricament només les cues temporals sense solapament;
- els forats interns es conserven i redueixen la cobertura;
- mínim 60 sessions completes alineades;
- cobertura comuna ≥95%;
- correlació de retorns close-to-close ≥0,99;
- coincidència de direcció ≥95%;
- diferència absoluta p95 del close ≤15 bps;
- cap rendiment ni regla d'estratègia consultats.

## Resultat observat

| Mesura | Resultat | Gate |
|---|---:|---:|
| Sessions completes alineades | 77 | ≥60 |
| Cobertura comuna | 97,468% | ≥95% |
| Correlació retorn D1 | 0,998814 | ≥0,99 |
| Direcció coincident | 100% | ≥95% |
| Diferència close p95 | 10,343 bps | ≤15 bps |

El tram comú és 16/03/2026–08/07/2026. Les cues addicionals d'Ostium no es
compten com absències del proxy; dins del tram comú, dos dies incomplets del
proxy sí que romanen al denominador. Tots els inputs queden fixats per SHA-256 a
l'artefacte.

## Reproducció

```bash
python -m lab.sq_bridge.spx_d1_source_parity_v4 \
  --reference lab/out/market_sources/sp_m1_dukas_utc_2026_extended.parquet \
  --ostium /ruta/ostium/SPXUSD/America_New_York/2026/{03,04,05,06,07}.csv \
  --output lab/sq_bridge/evidence/spxusd_d1_sq_ostium_parity_v4.json
```

Implementació: `lab/sq_bridge/spx_d1_source_parity_v4.py`. Evidència:
`lab/sq_bridge/evidence/spxusd_d1_sq_ostium_parity_v4.json`.

## Següent gate

La regla US500+VIX continua sense definir. Primer han de completar-se tres dies
open/midday/close de costos reals d'Ostium. Després es podrà formular una única
hipòtesi D1 de baixa rotació, amb VIX de la sessió anterior, i executar-la sota
la cadena v4.
