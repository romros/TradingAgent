# Alquímia StrategyQuant Expert v1

Release congelada el 2026-08-05 per a StrategyQuant Build 143.2708.

## Què és

Un sistema de decisió i aprenentatge que ordena el flux SQ, conserva evidència,
detecta autoenganys i tradueix resultats històrics a preguntes de règim i economia
actual. És operatiu per dissenyar, revisar, rebutjar i escollir la següent prova.

No és un generador de beneficis, un senyal de trading ni una autorització de live.

## Acceptació congelada

- 76 tests o més;
- 5/5 casos sintètics de transferència;
- cas cec de cartera: rebuig verificat com a evidència de desplegament;
- benchmark difícil FTS5: Recall@5 i MRR@5 `0.9032258065`;
- abstenció `1.0`;
- cap embeddings ni Cache RAG necessaris;
- cap accés de trading live.

Executar el contracte principal:

```bash
python3 academia/tools/expert_release_gate.py \
  academia/packages/strategyquant/releases/alquimia-expert-v1.json
python3 -m unittest discover -s academia/tests -v
```

## Fronteres obertes, no defectes amagats

1. SL/PT estret s'executa, però falta un artifact supervivent que demostri
   estructuralment que només canvien stop i target.
2. Random vs Genetic no té resultat comparable: Build 143 no ofereix un límit
   exacte equivalent per Random i `pause/stop` deixa feina en cua.
3. SQCLI exporta ordres, però no s'ha provat exportació de codi i paritat completa
   amb un motor objectiu.
4. Paper trading i live queden fora de l'Acadèmia.

Qualsevol release posterior ha de conservar aquestes fronteres o aportar una prova
reproduïble que les tanqui. Eliminar-les del text no compta com a progrés.
