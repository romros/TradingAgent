# Evidència i autoritat

Prioritzar: (1) artifacts/experiments reproduïbles de la build objectiu, (2)
documentació oficial amb data/build, (3) papers primaris, (4) practicants
reproduïbles, (5) vídeos/fòrums només per generar hipòtesis.

Estats: `captured` → `corroborated` → `tested` → `verified`. Conservar també
`contradicted` i `obsolete`.

Una font oficial prova què documenta el producte, no que una tècnica garanteixi
edge. Un fixture sintètic prova cablejat, no mercat. Un backtest prova comportament
sota supòsits concrets, no futur.

Per `.sqx` locals, executar `academia/tools/import_sqx_evidence.py`. No llegir només
el fitness: comprovar hash, finestra, `IsRetester`, resultats especials, instrument i
costos. En carteres, separar agregat i components. En WFM, `futurePeriod=true` és una
projecció de paràmetres i no rendiment observat.

Executar `academia/tools/audit_sq_artifacts.py ROOT` abans de declarar una capacitat
provada. Una tasca o opció configurada no equival a un artifact de resultat.

White (2000) tracta data snooping; Bailey i López de Prado (2014), selecció múltiple.
No implementar estadístics fins tenir intents i retorns reals i una decisió que ho
necessiti.
