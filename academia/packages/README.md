# Paquets de domini

Cada subdirectori conté un `package.json` declaratiu. El nucli del catàleg no
coneix StrategyQuant: filtra pel camp `domain` i carrega paquets sense canviar
l'esquema. `strategyquant` és el primer paquet, no una dependència del nucli.
