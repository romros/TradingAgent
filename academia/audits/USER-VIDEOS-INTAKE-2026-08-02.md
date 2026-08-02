# Entrada de vídeos aportats per l'usuari — 2026-08-02

## Resultat

S'han rebut 13 enllaços i normalitzat 12 vídeos únics. `asA_PJYLYdw` estava
duplicat. No s'ha descarregat cap vídeo ni s'ha versionat cap transcripció.

L'endpoint públic oEmbed de YouTube ha permès verificar títol i autor. L'accés
automatitzat al contingut i als subtítols ha estat bloquejat des d'aquest host;
no s'han usat cookies personals ni mecanismes d'evasió. Per tant, tots els vídeos
queden en estat `metadata_captured_content_pending` i nivell `C_EXPLORATORY`.

S'han provat dues vies independents i efímeres: `yt-dlp` 2024.04.09 i
`youtube-transcript-api` 1.2.4. Totes dues han rebut el bloqueig anti-bot/IP de
YouTube per als 12 identificadors. L'API específica adverteix que autenticar-se
amb cookies pot acabar bloquejant el compte; aquesta via es descarta. Instal·lar
l'eina permanentment no solucionaria el bloqueig de xarxa.

## Pilot Docker i endpoint alternatiu

Un Chrome real en `pinchtab/pinchtab:0.14.0`, amb perfil en `tmpfs`, port només a
loopback, media/imatges bloquejats i allowlist de YouTube, va carregar metadades
però va mostrar el mateix anti-bot. No va exposar el botó de transcripció.

La cerca web va localitzar `youtube-transcript.ai`, que declara un endpoint públic
de CC sense compte. El pilot d'una sola consulta per vídeo va recuperar CC
auto-generats en castellà dels dos vídeos prioritaris i va verificar ID, títol i
durada (10:11 i 6:43). La qualitat té un defecte material: moltes frases apareixen
triplicades. Decisió: **adaptador exploratori d'un sol ús, no dependència**. Les
transcripcions completes no es guarden; només notes transformadores amb timestamp.

Els dos manifests revisats passen a `transformative_notes_extracted`. Els altres
deu continuen `metadata_captured_content_pending`.

## Ordre de revisió proposat

1. Builder complet i introducció a SQ.
2. Robustesa/Monte Carlo i Walk Forward Matrix.
3. Revisió d'una estratègia un any després, per connectar backtest i realitat.
4. Configuracions predeterminades, comprovant versió i defaults heretats.
5. Casos d'or, EURUSD, intradia, gaps, gas natural i swing com a hipòtesis, mai
   com a proves de rendibilitat.

## Gate per convertir un vídeo en aprenentatge

Per cada afirmació candidata: timestamp, què diu l'àudio, què mostra la pantalla,
versió/configuració visible, contrast amb font primària, prova local si canvia una
decisió i estat final (`captured`, `corroborated`, `tested` o `contradicted`).

Cap títol promocional (`funciona`, `guanyadora`, `rentable`, `secreta`) es tracta
com a evidència. Fins completar aquest gate, els manifests només serveixen per
descobrir i prioritzar les fonts.
