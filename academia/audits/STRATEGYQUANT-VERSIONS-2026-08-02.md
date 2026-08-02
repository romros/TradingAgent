# Auditoria de versions StrategyQuant

Build objectiu declarada per l'acadèmia: **143.2708**. Aquesta auditoria no
inspecciona ni executa la instal·lació; classifica què es pot afirmar des de fonts.

| Coneixement | Build/font | Ús a 143.2708 |
|---|---|---|
| Databanks, Data settings, Cross-checks, WFO/WFM | docs 2015–2019, build no declarada | concepte útil; UI, noms i defaults pendents de prova local |
| Portfolio Master | introduït des de 138 segons documentació | probablement disponible; verificar mòdul/llicència |
| Portfolio Composer | introduït a 141 | documentat com anterior a target; verificar disponibilitat |
| AlgoWizard reescrit i AI | nota oficial Build 143 | aplicable a família 143; detalls pendents de 143.2708 |
| Robustesa StockPicker/Single Asset nova | nota oficial Build 143 | no generalitzar a altres motors |
| Automatic Retest multi-combinació | secció “Update from version 144” | **no assumir disponible** a 143.2708 |
| Build 142 com a “referència” | vídeo de practicant | opinió exploratòria, no política d'Alquímia |

## Regla per a l'agent

Abans de recomanar un botó, camp o tasca concreta:

1. filtrar fonts per `sq_version`;
2. si la font no declara build, presentar el concepte i advertir de la UI;
3. si la font és posterior a 143.2708, marcar `future/not-target`;
4. només una captura/log o prova local pot convertir disponibilitat en `verified`.

Conclusió: el coneixement metodològic és utilitzable, però gran part de la
documentació operativa encara és `captured`, no verificada contra 143.2708.
