# Construcció de cartera Alquímia v4

## Objectiu

La validació individual no és suficient: dues estratègies poden superar tots
els gates i representar pràcticament la mateixa exposició. La porta de cartera
selecciona entre quatre i vuit estratègies abans d'obrir el holdout final.

El contracte queda preregistrat a `methodology_v4.json`:

- mínim 4 i màxim 8 estratègies;
- màxim 12 candidates individuals d'entrada;
- una candidata per hipòtesi dirigida;
- correlació absoluta màxima de PnL diari net d'estrès: 0,70;
- Jaccard màxim de dates de sortida: 0,80;
- almenys 30 dates de sortida a la unió de cada parella;
- màxim dues posicions simultànies;
- risc de stop simultani màxim del 3% del compte;
- capital simultani compromès màxim del 60%, preservant un 40% de reserva;
- màxima cardinalitat i, després, expectativa, profit factor i identificador.

Si no existeix cap subconjunt de quatre candidates que compleixi totes les
restriccions, la decisió és `REJECT`. No es relaxen els llindars després de veure
els resultats.

## Evidència utilitzada

Cada candidata ha d'arribar d'un artefacte `small_account_economics` amb `PASS`,
exactament 200 USDC, costos Ostium congelats i un trace schema 2 reproduïble.
El trace conserva ara entrada i sortida UTC, stop inicial reconstruït i PnL net
d'estrès. La correlació alinea la unió de dates i posa zero quan una estratègia
no tanca cap operació aquell dia.

No s'accedeix al holdout final, ni s'autoritza paper o live.

Els mateixos límits es tornen a calcular abans de cada ordre paper amb
`portfolio_entry_admission_v4.py`. Una instrucció de sizing no pot avançar si
la projecció crea una tercera posició, supera el 3% de risc de stop, compromet
més del 60% de l'equity actual o repeteix una candidata ja activa. Aquesta
funció és pura: retorna `PASS` o `BLOCK`, però no envia cap ordre.

## Manifest de campanya

```json
{
  "schema_version": 1,
  "portfolio_id": "alquimia-v4-small-account-portfolio",
  "holdout_accessed": false,
  "small_account_branches": [
    {
      "hypothesis_id": "d1_breakout_long",
      "campaign_id": "eurusd-d1-alquimia-v4",
      "artifact_path": "/ruta/06_small_account_economics.json",
      "artifact_sha256": "..."
    }
  ]
}
```

Execució determinista:

```bash
PYTHONPATH=. .venv/bin/python -m lab.sq_bridge.portfolio_construction_v4 \
  --manifest /ruta/portfolio_manifest.json \
  --output /ruta/portfolio_construction.json
```

El manifest definitiu només es crearà quan hagin acabat totes les branques de
compte petit. La integració del worker de holdout ha de comprovar que la seva
candidata i el hash exacte del seu artefacte consten en aquesta selecció.
