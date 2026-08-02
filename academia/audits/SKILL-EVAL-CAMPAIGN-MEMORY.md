# Prova del skill contra la memòria de campanyes

## Preguntes provades

1. Podem afinar l'EURUSD H4 que passava temporalment?
2. Val la pena posar més leverage a la quasi-candidata FX intradia?
3. Un PF 3,13 al test justifica continuar la reversió D1?
4. Podem recuperar sq_0423850 ajustant-la al període 2019-2025?
5. Què fem amb una família nova sense evidència pròpia?

## Resultat esperat i comprovat

Els quatre casos coneguts retornen `DESCARTAR`, una evidència normalitzada, què
no s'ha de repetir i una sola direcció següent. La família desconeguda retorna
`PROVA DIRIGIDA`, declara que falta evidència i no pren prestats els resultats
d'una altra família.

Exemple reproduïble:

```bash
python3 academia/tools/campaign_advisor.py xauusd_h4_bollinger_long
```

Sortida essencial:

```text
DECISIÓ: DESCARTAR
RISC PRINCIPAL: OOS_REGIME_FAIL
SEGÜENT PAS: Només reobrir amb hipòtesi de règim ex ante i OOS nou.
EVIDÈNCIA: academia/experiments/observations/sq-0423850-xau-h4-2026-08.json
```

## Límit

Aquesta prova comprova enrutament, format i disciplina de memòria; no demostra
que un model de llenguatge interpreti bé qualsevol pregunta. Caldrà un conjunt
cec de preguntes humanes més ampli abans de declarar el skill `verified`.
