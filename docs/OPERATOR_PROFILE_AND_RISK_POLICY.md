# Perfil de l'operador i política de risc d'Alquímia

**Data:** 2026-08-02
**Naturalesa:** hipòtesi de treball revisable, no diagnòstic ni assessorament personal

## Perfil observat

L'usuari encaixa millor com a **propietari d'un sistema quantitatiu** que com a
trader discrecional. Fortaleses observades: iniciativa, curiositat tècnica,
persistència, necessitat de control de tota la cadena, mentalitat de producte i
interès explícit per costos, paritat, història, règims, liquidació, checkpoints i
explicabilitat.

Tensió principal: vol risc controlat, però tendeix a veure el leverage màxim com
la via perquè 200 USDC siguin rendibles. Riscos a vigilar: ancoratge al leverage,
escalada de compromís, confiança excessiva en automatització, seducció pels grans
backtests i complexitat prematura.

## Perfil recomanat

**Operador quantitatiu sistemàtic de swing orientat a preservar capital.**

- Preferència per H4/D1 i trades de 12 hores a pocs dies.
- Execució automàtica; intervenció humana per pausa, degradació o incidents.
- Començar amb 2–3 estratègies; ampliar fins a 3–6 només amb evidència i baixa
  dependència/correlació.
- Revisió periòdica, no reacció emocional a cada trade.
- Recerca agressiva al LAB, paper prudent i operació real defensiva.

No orientar el sistema a scalping manual, notícies discrecionals o canvis de regla
després de pèrdues.

## Política canònica

```text
edge validat → stop/MAE → risc monetari → nocional → leverage necessari
```

Mai:

```text
leverage màxim del venue → mida màxima → buscar una justificació després
```

El leverage no crea edge. S'usa el màxim que continuï superant costos, marge,
liquidació, drawdown, estrès i risc conjunt; pot ser zero si no és viable.

## Defaults inicials per al pilot de 200 USDC

Aquests valors són guardrails experimentals i s'han de revisar quan es conegui la
situació financera i tolerància real de l'usuari:

- els 200 USDC han de ser capital de risc prescindible;
- risc per trade: 0,5–1% (1–2 USDC);
- risc simultani total: 2–3% (4–6 USDC);
- pausa automàtica a 10% de drawdown (20 USDC);
- revisió completa abans de 15% (30 USDC);
- mantenir reserva de marge; no comprometre tot el compte;
- no reposar capital durant la finestra d'avaluació per ocultar drawdown;
- cap live sense paritat, paper suficient i autorització explícita.

## Com mesurar l'èxit

L'èxit inicial no és multiplicar ràpidament 200 USDC. És demostrar que el sistema:

- pot rebutjar `NO_CANDIDATE` sense ampliar la cerca;
- conserva capital i evidència;
- executa igual que el backtest dins toleràncies;
- identifica costos, degradació i règims adversos;
- pausa abans que una hipòtesi fallida es converteixi en una pèrdua greu.

## Informació encara necessària

Abans de considerar aquesta política personalitzada cal saber si els 200 USDC són
plenament prescindibles, experiència real, horitzó, ingressos/estalvis, reacció a
una pèrdua del 10–30% i objectiu econòmic. Fins llavors el perfil és una política
conservadora del projecte, no una classificació definitiva de la persona.
