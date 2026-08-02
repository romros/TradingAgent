# Cartera, exportació i operacions

- Cartera i paritat: llegir `academia/courses/strategyquant/03-PORTFOLIO-EXPORT.md`.
- Automatització i monitoratge: llegir
  `academia/courses/strategyquant/04-AUTOMATION-MONITORING-EXTENSIONS.md`.

No combinar components amb expectativa negativa. Tractar pesos com paràmetres
optimitzats. Exigir paritat trade a trade abans de confiar en un export. Custom
Projects encadena gates congelats amb límits; Automatic Retest pot pausar però no
reoptimitzar; snippets i grid necessiten un gap i pressupost explícits.

Per automatitzar la GUI local, preferir els endpoints interns de SQ (`/project/start`,
`/project/pause`, `/project/resume`, `/project/stop`) amb el mateix formulari
comprimit que usa la interfície. Reservar PinchTab efímer per inspecció i accions
que SQCLI/API no exposin. L'API interna és específica del build: verificar-la en
un runtime copy-on-write i no convertir-la en servei permanent.

La paritat no és «el codi compila». Exportar ordres SQ i ordres del motor destí,
i executar `academia/tools/compare_order_parity.py` amb toleràncies declarades.
Qualsevol diferència de senyal, temps, preu o mida és una fallada a explicar.
