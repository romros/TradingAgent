# Earnings gap continuation D1

Estat: **REJECT / lead estadístic insuficient**. No és una estratègia
consolidada i no autoritza shadow, paper ni live.

## Regla congelada

- Univers final preregistrat: AAPL, AMZN, CAT, DE, GOOG, JNJ, JPM, KO, META,
  MSFT, NFLX, NVDA, PEP, TSLA, UNP i XOM.
- Esdeveniment: acceptació punt-en-el-temps d'un 8-K Item 2.02 de la SEC.
- Senyal long: gap d'obertura de la sessió de reacció `>=3%`, close per sobre
  de l'open i `CLV=(close-low)/(high-low) >=0,75`.
- Entrada: open de la sessió següent. Sortida: open cinc sessions després.
- Economia estadística: 2.000 USD per observació, accions senceres, mínim
  1 USD per ordre i 10 bps per costat.
- No s'ha optimitzat cap llindar ni la durada després de veure performance.

## Resultat

La primera mostra d'onze actius semblava atractiva fora de train (8 trades,
PF 2,99), però no arribava al mínim de 20 observacions. Es va ampliar, abans
de consultar-ne el rendiment, amb cinc equities líquides que ja tenien dades
canòniques. La regla va romandre byte-a-byte equivalent.

Amb els setze actius:

- Train 2017–2021: 17 trades, retorn mitjà +0,056%, PF 1,024, compost −2,97%
  i DD 22,65%.
- Validació 2022–2023: 12 trades, mitjana +1,729%, PF 2,513.
- 2024: 5 trades, mitjana +1,904%, PF 2,991.
- Validació+2024: 17 trades, PF 2,637, t=1,327, 3/3 anys i 8 actius positius.

La decisió continua sent rebuig perquè només hi ha 17 observacions recents
contra el mínim congelat de 20 i perquè el train és econòmicament fràgil. El
bon tram recent és una hipòtesi per a futura confirmació transversal, no
evidència suficient per incorporar-la a una cartera.

## Traçabilitat

- Preregistre original: `lab/sq_bridge/earnings_gap_continuation_preregistration_v1.json`
- Expansió congelada: `lab/sq_bridge/earnings_gap_continuation_preregistration_v2.json`
- Calendari SEC: `data/ibkr_sq_v2/earnings_gap_continuation_v1/sec_calendar_preflight_v2.json`
- Resultat final: `data/ibkr_sq_v2/earnings_gap_continuation_v1/screen_v2_expanded.json`

Els períodes 2022–2024 no són un holdout verge perquè la família PEAD anterior
ja els havia consultat. Per reprendre aquesta idea cal un nou univers declarat
abans de mirar resultats o dades futures; queda prohibit rescatar-la excloent
TSLA/NFLX o ajustant gap, CLV o durada retrospectivament.
