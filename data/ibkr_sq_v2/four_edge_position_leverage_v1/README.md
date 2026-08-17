# Four-edge position-only leverage v1

Directori autocontingut de l'auditoria nativa 2x de CAT, MSFT, JPM i SGLN.

- `input/`: quatre SQX amb money management de pressupost fix 1.000 USD.
- `Portfolio-1786963153297.sqx`: prova v1; pesos 25%, no-op verificat.
- `Portfolio-1786963273774.sqx`: resultat v2; pesos 50%, exposició objectiu 200%.
- `orders-{cat,msft,jpm,sgln}-floor1000.csv`: ordres exportades per membre.
- `orders-floor1000-v2.csv`: export `data=main` del compost; només conté CAT i
  es conserva com a prova de la limitació de l'exportador, no per auditar.
- `net_audit_v2.json`: resultat net canònic amb costos, FX i finançament.
- `same_assets_buy_hold_v1.json`: comparació congelada amb buy-and-hold dels
  mateixos quatre actius, normal i a exposició 2x.

Les regles congelades i la interpretació són a
`docs/POSITION_ONLY_LEVERAGE_AUDIT_V2.md`. Cap artefacte autoritza paper o LIVE.
