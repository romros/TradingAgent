# Experiments d'aprenentatge

`pending/` conserva preregistres i traça històrica: el nom del directori no implica
que tots siguin feina pendent. L'única cua operativa vigent es declara a
`../CURRENT.md`, i l'estat quantitatiu canònic és el catàleg del paquet
StrategyQuant. No executar un manifest només perquè sigui dins `pending/`.

Una afirmació de configuració SQ es verifica aquí amb:

- hipòtesi preregistrada;
- versió SQ i hash del projecte;
- dades, símbol, timeframe i períodes;
- canvi únic respecte del control;
- comanda SQCLI;
- log i artifacts;
- resultat i limitacions;
- decisió de promoció de la claim.

Els experiments educatius no comparteixen resultats quantitatius amb les campanyes
d'Alquímia llevat que el protocol de la campanya ho autoritzi explícitament.
## Importar aprenentatge extern

`tools/import_campaign.py` normalitza una extracció curta, comprova que cada
artifact existeix i en desa el SHA-256. No copia resultats, trades ni datasets.
El JSON d'entrada ha de seguir la forma de `campaign-observation.schema.json`,
però els elements de `source_artifacts` només necessiten `path` i `role`.

`tools/campaign_preflight.py` avalua una fitxa de pre-registre abans de generar.
Un `ready=true` només autoritza l'etapa barata; mai el holdout ni trading. La
fitxa d'exemple és deliberadament incompleta i ha de fallar fins que períodes,
costos i protocol quedin realment congelats.
