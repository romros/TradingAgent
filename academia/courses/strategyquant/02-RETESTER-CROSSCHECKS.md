# Tram 2 — Retester i cross-checks

## Resultat d'aprenentatge

Convertir candidats del Builder en un embut de falsació. Retester no serveix per
buscar una configuració que torni a guanyar, sinó per canviar una hipòtesi del
backtest i observar si la lògica es trenca.

## Ordre de batalla

| Etapa | Pregunta | Prova | Cost relatiu | Si falla |
|---:|---|---|---|---|
| 1 | El backtest ràpid era aproximació? | precisió superior | baix/mitjà | descartar artifacte |
| 2 | Hi ha prou observacions? | trades, concentració, subtrams | baix | no inferir edge |
| 3 | L'equity depèn de sort/ordre? | MC trades: shuffle/skip | baix | descartar o més dades |
| 4 | Sobreviu execució realista? | spread/slippage/comissió/swap | mitjà | no optimitzar |
| 5 | Depèn del paràmetre exacte? | MC retest de paràmetres | alt | descartar pic estret |
| 6 | Depèn de barres exactes? | starting bar/history perturbation | alt | descartar fragilitat |
| 7 | El mecanisme transfereix? | símbols, TF i règims justificats | alt | limitar o descartar |
| 8 | Reoptimitzar té sentit? | WFO/WFM preregistrada | molt alt | no pescar cel·les |

Només supervivents passen a la següent etapa. Executar 100 retests complets sobre
cada generat pot multiplicar per 100 el cost; no aporta rigor si el candidat ja
fallava precisió o costos.

## Configuració que ha de quedar registrada

- artifact i hash d'entrada;
- motor, dades, precisió i data parts;
- valor base i distribució de cada pertorbació;
- nombre de simulacions i seed si existeix;
- mètrica, percentil i llindar preregistrats;
- candidats entrants, sortints i motiu de cada descart;
- temps/còmput i nombre total de backtests.

Abans d'executar, fer una llista exacta dels crosschecks actius i rebutjar-ne
qualsevol d'heretat. En el cas local SQX 143, una passada de Monte Carlo de
paràmetres també va executar manipulació de trades; es va invalidar i repetir
amb només el crosscheck previst. Conservar els resultats fallits per diagnosticar
és correcte; desactivar els gates per conservar-los no ho és.

El contracte del test ha de coincidir en tres llocs: metodologia escrita,
condicions d'acceptació configurades i resultats executats. Per Monte Carlo,
registrar simulacions demanades i membres produïts per separat: un paquet pot
incloure el resultat base, de manera que membres no equival automàticament a
simulacions.

## Interpretació correcta

- Precisió: una diferència gran indica dependència del model intrabar, sobretot
  amb stop/limit. No és simplement «pitjor rendiment».
- MC trades: reordena o omet trades existents; estima seqüència i drawdown, però
  no descobreix nous trades ni simula canvi de mercat.
- MC retest: torna a executar amb paràmetres, dades o costos alterats; és més car
  i respon sensibilitat del model.
- Mercats addicionals: han de compartir un mecanisme plausible. Exigir benefici
  idèntic a qualsevol símbol és tan arbitrari com ignorar-los tots.
- OOS: després de mirar-lo i canviar una decisió ja és desenvolupament.
- Costos: evitar etiquetes com «2x» soles. Enumerar valor base i estressat de
  spread, slippage, comissió, swap/rollover i impacte. Si només canvia slippage,
  la conclusió queda limitada a slippage.

## Regla de decisió

Cada candidat acaba amb una de tres sortides:

- `CONTINUAR`: no hi ha fallada material i queda una prova final intacta.
- `PROVA DIRIGIDA`: una ambigüitat concreta es resol amb una sola prova nova.
- `DESCARTAR`: falla precisió, costos, concentració o sensibilitat; no es busca
  una nova combinació sobre les mateixes dades per rescatar-lo.

## Exercici

Usar `experiments/examples/retester-learning-exercise.json`. La resposta correcta
descarta A abans de MC car, envia B a sensibilitat de paràmetres i impedeix usar
el holdout consultat de C com a confirmació final.

Fonts: `sq_official_cross_checks_20190226`,
`sq_official_monte_carlo_retests_20190301` i
`sq_official_data_settings_20190109`. Cas local:
`sq_local_sqx143_contract_drift_20260802`.
