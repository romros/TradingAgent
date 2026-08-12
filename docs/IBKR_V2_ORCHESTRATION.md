# Orquestració autònoma IBKR-v2

## Carrils

1. **SQCLI:** una sola cerca activa, al màxim segur, sempre amb projecte nou,
   pressupost congelat, watchdog i classificació `IDEA_ONLY` o promocionable.
2. **Dades:** descàrrega reprenable i certificació mecànica per actiu/any, amb
   concurrència moderada perquè no competeixi materialment amb SQ.
3. **Anàlisi:** quan SQ acaba, inventariar idees, agrupar-les per mecanisme i
   decidir `EXPLOIT_GENETIC`, `CHANGE_FAMILY`, `CHANGE_TIMEFRAME` o `REJECT`.

## Política de continuació

- Random permissiu mesura densitat; no promociona.
- Genètica només si apareixen diverses idees simples de la mateixa família.
- Un zero d'acceptació per manca de trades fa canviar timeframe, família o
  longitud de dades; no augmenta cegament els intents.
- Validation i OOS externs no participen en la generació.
- Cap resultat passa a paper/live des d'aquest procés.
- Cada procés conserva manifest, journal, heartbeat i resultat final.

## Ordre actual

1. Acabar `AAPL D1 RANDOM IDEA HARVEST`.
2. Si hi ha idees: revisar estructures i obrir genètica per família.
3. Si no n'hi ha: no repetir AAPL D1 genèric; prioritzar CAT amb més història o
   AAPL H4/H1 preregistrat.
4. Estendre CAT any per any fins al 2025, certificant cada checkpoint.
5. Abans de SQ promocionable sobre CAT: provar ajustos corporatius, congelar
   particions externes i fer round-trip D1 d'SQ.
