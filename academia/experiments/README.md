# Experiments d'aprenentatge

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
