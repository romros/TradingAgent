# Famílies d'estratègies basades en evidència

**Actualitzat:** 2026-08-12
**Propòsit:** decidir què mereix pressupost d'SQCLI abans de generar regles.

Aquest document no afirma que una anomalia publicada sigui executable ni que
continuï funcionant. Ordena hipòtesis segons qualitat i transferibilitat de
l'evidència. Tota família ha de passar costos, validation i OOS propis.

## Resum executiu

| Prioritat | Família | Evidència | Actius més naturals | Adequació actual |
|---|---|---|---|---|
| A | Tendència / time-series momentum | Molt àmplia, multi-actiu i multirègim | Índexs, futurs, FX, commodities; també accions líquides | Primera família D1 |
| A | Momentum relatiu | Àmplia, però requereix univers | Cohort d'accions/ETFs | Quan tinguem ≥4 actius certificats |
| B | Gap/overnight → reversió intradia | Repetida en accions; dependent de friccions | AAPL, GOOGL, MSFT, TSLA, CAT | Després de certificar open i M1 |
| B | Post-earnings drift | Històrica, però costos i degradació importen | Accions líquides amb calendari point-in-time | Fase posterior amb dades d'earnings |
| B/C | Volatilitat/ruptura condicionada | Mecanisme plausible; evidència variable | Actius direccionals i dies d'informació | Testar amb filtre de règim |
| C | Opening-range breakout genèric | Mixta i específica del mercat | Futurs/índexs; menys clara en accions | No generar massivament sense pretest |
| C | Reversió curtíssima genèrica | Molt sensible a spread, impacte i turnover | Univers molt líquid | Baixa prioritat per capital petit |

## 1. Tendència i time-series momentum — prioritat A

La regla conceptual és comprar un actiu amb retorn passat positiu i vendre o
evitar-lo quan és negatiu, normalitzant el risc per volatilitat. L'evidència més
forta és de carteres diversificades de futurs/forwards, no d'una única acció.

Fonts:

- Hurst, Ooi i Pedersen, *A Century of Evidence on Trend-Following Investing*:
  https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- Daniel i Moskowitz, *Momentum Crashes*:
  https://www.nber.org/papers/w20439

Traducció a SQ:

- D1 long/short separats;
- lookbacks lents i combinacions simples de retorn, canal o mitjana;
- stops i sizing ATR;
- filtre de volatilitat/règim preregistrat;
- no més de 2–3 condicions i cap calendari arbitrari inicial.

Falsificadors: expectativa negativa fora de train, dependència d'un sol bull
market, col·lapse en rebots després de pànic, o rendiment que només apareix amb
leverage. Momentum pot patir crashes quan el mercat rebota violentament després
d'una caiguda amb volatilitat elevada.

## 2. Momentum relatiu — prioritat A quan hi hagi univers

No pregunta si Apple puja en absolut, sinó quins membres d'un univers mostren
més força relativa. Necessita diversos actius disponibles al mateix instant i
és metodològicament millor com a cartera que com a estratègia isolada.

Univers inicial possible: CAT/JPM/JNJ/KO més AAPL/GOOGL/MSFT/TSLA. Cal evitar
que quatre mega-caps tecnològiques comptin com quatre fonts independents.

Traducció a la cadena:

- SQ pot descobrir regles deterministes per actiu;
- Python ha de fer el ranking cross-sectional i la restricció de cartera;
- rebalanceig setmanal o mensual abans que diari per reduir turnover;
- el holdout és comú a tota la cohort.

## 3. Overnight/gap i reversió intradia — prioritat B

Diversos estudis documenten retorn overnight positiu i retorn intradia molt
més baix, i una relació de reversió després de moviments overnight. No és una
invitació a comprar sempre al tancament: shortability, gap, spread d'obertura i
informació nova poden dominar el resultat.

Fonts:

- Cooper, Cliff i Gulen, *Return Differences between Trading and Non-Trading
  Hours*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Berkman et al., *Dispersion of Opinions, Limits to Arbitrage, and Overnight
  Returns*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1214564
- Bahcivan, Dam i Gonenc, *Dark Side of the Day* (revisió 2026):
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4335622

Traducció a SQ:

- gap normalitzat per ATR i direccions separades;
- entrada després d'observar l'open, mai al preu teòric anterior;
- sortida intradia i `max_time` curt;
- separar gap amb/ sense earnings quan existeixin dades point-in-time;
- costos d'obertura i slippage d'estrès obligatoris.

És especialment rellevant per TSLA i mega-caps volàtils, però també és on és
més fàcil inventar fills impossibles. Necessita M1 certificat, no només D1.

## 4. Post-earnings announcement drift — prioritat B posterior

El mercat pot incorporar gradualment sorpreses de beneficis, però l'efecte net
depèn molt de costos, timing exacte i de com es calcula la sorpresa. Un
calendari actual descarregat avui no és suficient: cal saber què era publicat i
quan, sense revisions futures.

Fonts:

- Ng, Rusticus i Verdi, *Implications of Transaction Costs for PEAD*:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1024185
- Battalio i Mendenhall, *PEAD: Timing and Liquidity Costs*:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=937257

No és una família inicial d'SQ pur perquè necessita dades externes d'esdeveniment
i sorpreses point-in-time. Pot ser un context determinista que habiliti una
regla SQ, no una decisió lliure d'un model.

## 5. Breakouts i opening range — prioritat condicionada

Hi ha evidència positiva d'ORB en crude-oil futures, però un estudi de NASDAQ
no troba base suficient per atribuir poder predictiu als breakouts simples.
Això impedeix elevar “ORB” a regla universal.

Fonts:

- *Assessing the profitability of intraday opening range breakout strategies*:
  https://doi.org/10.1016/j.frl.2012.09.001
- *Is the simple trading range break-out rule profitable from the NASDAQ
  index?*: https://doi.org/10.1108/BIJ-12-2016-0197

Regla del projecte: fer primer un screen determinista petit per actiu i règim.
Només si hi ha densitat estable de variants es dona pressupost genètic d'SQ.

## 6. Quins actius tenen millor encaix per a nosaltres

No hi ha un “millor actiu” universal. Per capital petit interessen liquiditat,
fraccionament, costos baixos, moviment suficient i dades fiables.

Ordre de recerca proposat:

1. CAT per validar tota la cadena de dades i D1 sense reutilitzar història.
2. AAPL i TSLA, perquè ja hi ha recursos locals auditables i perfils de
   volatilitat diferents.
3. GOOGL i MSFT amb font Dukascopy nova; el MSFT antic queda prohibit.
4. JPM/JNJ/KO per reduir concentració tecnològica.
5. ETFs small-cap, internacional i sectorial només com a recerca teòrica fins
   aclarir PRIIPs/executabilitat.

Per evidència, una cartera multi-actiu de tendència és més defensable que
apostar tot a una estratègia sobre Tesla. Per potencial oportunista, els gaps
de mega-caps són interessants, però s'han de provar amb fills i costos d'obertura
molt conservadors.

## 7. Embut d'SQ derivat de l'evidència

1. `D1_TREND_SIMPLE`: random search acotada, long/short separats.
2. `D1_PULLBACK_IN_TREND`: només si la primera confirma règim direccional.
3. `D1_RELATIVE_MOMENTUM`: quan quatre o més actius comparteixin historial.
4. `M30/H1_GAP_REVERSION`: només amb M1 i open NYSE certificats.
5. `EVENT_EARNINGS`: només amb calendari i sorpresa point-in-time.

No començar amb milers de combinacions d'indicadors. Cada família tindrà una
hipòtesi econòmica, complexitat limitada, costos triplicats, stop rule i holdout
congelat abans de veure performance.
