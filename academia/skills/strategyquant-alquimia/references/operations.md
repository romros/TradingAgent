# Cartera, exportació i operacions

- Cartera i paritat: llegir `academia/courses/strategyquant/03-PORTFOLIO-EXPORT.md`.
- Automatització i monitoratge: llegir
  `academia/courses/strategyquant/04-AUTOMATION-MONITORING-EXTENSIONS.md`.

No combinar components amb expectativa negativa. Tractar pesos com paràmetres
optimitzats. Exigir paritat trade a trade abans de confiar en un export. Custom
Projects encadena gates congelats amb límits; Automatic Retest pot pausar però no
reoptimitzar; snippets i grid necessiten un gap i pressupost explícits.

En una comparació de cartera de 3 contra 6 actius, congelar primer el mateix
univers elegible. No declarar que 3 supera 6 si la cartera de 6 estava bloquejada
per dades. Permetre una mostra de 3 actius com a pilot de cablejat, etiquetada
`PILOT_NOT_COMPARATIVE`; no usar-la per escollir actius ni canviar l'univers.
Modelar compounding sobre equity realitzada i demostrar per separat que el leverage
només redueix collateral: amb risc i stop fixats no crea edge ni benefici.

Per automatitzar la GUI local, preferir els endpoints interns de SQ (`/project/start`,
`/project/pause`, `/project/resume`, `/project/stop`) amb el mateix formulari
comprimit que usa la interfície. Reservar PinchTab efímer per inspecció i accions
que SQCLI/API no exposin. L'API interna és específica del build: verificar-la en
un runtime copy-on-write i no convertir-la en servei permanent.

La paritat no és «el codi compila». Exportar ordres SQ i ordres del motor destí,
i executar `academia/tools/compare_order_parity.py` amb toleràncies declarades.
Qualsevol diferència de senyal, temps, preu o mida és una fallada a explicar.

Quan `History` es munta read-only, comprovar abans d'executar que existeix el
fitxer del timeframe derivat (`H4.dat`, `D1.dat`, etc.). Si falta, no fer writable
tot l'històric: copiar només el directori del símbol a `academia/runtime/`, muntar
aquest fill com a overlay writable i mantenir el pare read-only. Verificar que SQ
crea el fitxer derivat abans d'interpretar el resultat. Un projecte aturat a
`running_status=50`, zero intents i CPU gairebé inactiva és incidència operativa,
no una prova que la família falli.
