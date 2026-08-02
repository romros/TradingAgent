# Entrada de vídeos aportats per l'usuari — 2026-08-02

## Resultat

S'han rebut 13 enllaços i normalitzat 12 vídeos únics. `asA_PJYLYdw` estava
duplicat. S'han recuperat temporalment els CC dels 12 vídeos (101 minuts en
total), s'han revisat i convertit en notes transformadores amb timestamps. No
s'ha descarregat cap vídeo ni s'ha versionat cap transcripció completa.

L'endpoint públic oEmbed de YouTube ha permès verificar títol i autor. L'accés
directe automatitzat als subtítols ha estat bloquejat des d'aquest host; no
s'han usat cookies personals ni mecanismes d'evasió. Els 12 manifests queden en
estat `transformative_notes_extracted` i nivell `C_EXPLORATORY`: una nota pot
descobrir una prova o un risc, però no acredita les mètriques mostrades en vídeo.

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
de CC sense compte. Una consulta per cada vídeo va recuperar CC auto-generats en
castellà, ID, títol, idioma i durada dels 12. La qualitat té un defecte material:
moltes frases apareixen triplicades, malgrat que la pàgina promet text net. Les
condicions, actualitzades el 18-03-2026, no garanteixen disponibilitat, completitud
ni exactitud i limiten l'automatització massiva sota fair use.

Decisió: **adaptador exploratori d'un sol ús, no dependència de producció**. És
acceptable per aquesta entrada petita i curada, amb revisió i eliminació posterior;
no és acceptable com a canal únic, benchmark de qualitat o ingestió massiva.

## Auditoria de vies de transcripció

| Via | Resultat en aquest host | Privacitat/operació | Decisió |
|---|---|---|---|
| YouTube `Show transcript` | Via oficial per vídeos amb captions; el navegador cloud rep anti-bot | Sense tercer de transcripció, però manual i dependent de la UI | Preferida quan sigui accessible |
| `yt-dlp` / `youtube-transcript-api` | 0/12 per bloqueig IP de YouTube | Eines locals, reproduïbles; instal·lar-les no canvia la IP | Mantenir com a primera via, no servei permanent |
| PinchTab en Docker | Carrega la pàgina però no supera l'anti-bot | Efímer i aïllat; afegir navegador no resol la xarxa | No adoptar per CC |
| `youtube-transcript.ai` | 12/12, timestamps útils; triplicació sistemàtica | Tercer independent, sense SLA ni garantia; prohibeix abusar l'automatització | Només fallback petit i revisat |
| MacParakeet | No provat: requereix macOS i descarrega l'àudio via `yt-dlp` | Transcripció local i codi obert, però no resol aquest host Linux ni el bloqueig de descàrrega | No aplicable aquí |
| Altres formularis/API comercials | No provats: cap guany després del 12/12 | Sovint processen URL/transcripció en tercers i afegeixen compte, crèdits o IA | No enviar dades ni incorporar sense necessitat |

## Resultat de la revisió

Els 12 vídeos ja tenen notes. Els insights amb més valor són: inspeccionar els
defaults heretats; registrar el contracte real de cada crosscheck; no abaixar un
gate perquè passen pocs candidats; considerar fus horari, sessió, gaps, marge i
benefici net per trade; separar edge cru de filtres afegits; i retirar una família
quan el mecanisme econòmic que generava l'edge ha canviat.

Els números i afirmacions de pantalla no s'han promogut perquè el canal alternatiu
només proporciona àudio/CC i no evidència visual. Les fonts originals atribuïdes a
llibres o tercers queden pendents d'identificació abans de pujar de nivell.

## Gate per convertir un vídeo en aprenentatge

Per cada afirmació candidata: timestamp, què diu l'àudio, què mostra la pantalla,
versió/configuració visible, contrast amb font primària, prova local si canvia una
decisió i estat final (`captured`, `corroborated`, `tested` o `contradicted`).

Cap títol promocional (`funciona`, `guanyadora`, `rentable`, `secreta`) es tracta
com a evidència. Fins completar aquest gate, els manifests només serveixen per
descobrir i prioritzar les fonts.

## Referències de l'auditoria d'eines

- YouTube Help, `View video transcripts`: https://support.google.com/youtube/answer/15930243?hl=en
- `youtube-transcript.ai`, API: https://youtube-transcript.ai/youtube-transcript-api
- `youtube-transcript.ai`, terms: https://youtube-transcript.ai/terms
- MacParakeet, privacy: https://macparakeet.com/privacy/
