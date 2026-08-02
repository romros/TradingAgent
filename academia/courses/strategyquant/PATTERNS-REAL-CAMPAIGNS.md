# Patrons de quatre campanyes reals d'Alquímia

Aquestes quatre campanyes no demostren quina estratègia guanyarà. Sí que
demostren quatre maneres diferents de no deixar-nos enganyar.

| Senyal que sembla bo | Què revela el gate | Diagnòstic | Acció |
|---|---|---|---|
| EURUSD H4: PF temporal 1,25 | PF 0,51 amb costos base | edge no capturable | canviar edge o fricció |
| FX H4: PF dev 1,22 | PF validació 0,48 | no es reprodueix temporalment | abandonar les sis famílies |
| SPY D1: PF test 3,13 | una sola operació al test | mostra no informativa | obtenir més observacions i OOS nou |
| XAUUSD H4: +16,38% total | OOS -1,00%, PF 0,96 | dependència del règim inicial | hipòtesi de règim ex ante |

## Insight transversal

La mida del número atractiu no decideix res sense saber **d'on surt**. L'agent
ha de preguntar, en aquest ordre: es repeteix en el temps, sobreviu costos,
té prou observacions independents i està repartit entre períodes? El primer
“no” determina la decisió i evita executar proves més cares.

Amb només quatre campanyes no podem estimar freqüències universals ni declarar
cap patró `verified`. Els quatre són `tested`: provenen d'experiments reals,
però encara no han estat reproduïts en campanyes independents equivalents.

## Cinquè patró: una execució sense errors pot executar la pregunta equivocada

La seqüència R1/R2 de SQX 143 aporta un aprenentatge diferent del rendiment:

- R1 va completar-se, però 0/40 artifacts contenien el canal que definia la idea;
- R2 va imposar l'arquitectura i 40/40 contenien `EnterAtStop`, `Highest` i `Lowest`;
- una primera passada MC va heretar un crosscheck no previst i es va invalidar;
- «costos 2x» només havia duplicat slippage, amb spread zero i comissió apagada.

Per tant, absència d'errors és només el gate zero. Abans d'aprendre res del
resultat cal demostrar que intenció, configuració i artifacts executats són
equivalents. Aquest patró és `tested` en una seqüència local, encara no
`verified` entre versions o entorns.
