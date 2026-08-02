# Desplegament Docker futur

No hi ha cap servei instal·lat o activat. El catàleg actual funciona amb Python 3
i SQLite de la biblioteca estàndard. Quan hi hagi una API, el contenidor haurà de:

- executar-se com a usuari no-root i amb filesystem arrel de només lectura;
- muntar manifests de només lectura i la base regenerable en un volum separat;
- publicar per defecte només a `127.0.0.1`;
- tenir versions/digests fixats, healthcheck i límits de CPU/memòria;
- no muntar Docker socket, directoris de trading, cookies ni secrets;
- separar una tasca efímera d'indexació del servei de consulta;
- mantenir embeddings, crawlers i workers fora de la composició per defecte.

No s'afegeix encara `Dockerfile` ni `compose.yaml`: sense servidor ni consumidor
serien artefactes especulatius impossibles de validar. Aquest és el contracte que
haurà de satisfer l'ADR de desplegament quan aparegui el primer consumidor.
