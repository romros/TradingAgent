#!/usr/bin/env python3
"""Retorna una sola acció per a un risc observat."""

import argparse
import json

ACTIONS = {
    "LOW_SAMPLE": "Ampliar el període o univers sense canviar les regles.",
    "PROFIT_CONCENTRATION": "Descompondre per run, any i símbol; no optimitzar.",
    "PARAMETER_PEAK": "Executar una graella veïna petita preregistrada.",
    "COST_FAIL": "Aturar l'afinament i buscar més edge brut o menor fricció.",
    "PRECISION_FAIL": "Retestar els mateixos trades amb precisió superior.",
    "TEMPORAL_FAIL": "Rebutjar la família o formular una hipòtesi de règim ex ante.",
    "HOLDOUT_PEEKED": "Reservar dades noves; reclassificar el holdout com desenvolupament.",
    "TEMPORAL_PASS_COST_FAIL": "Aturar l'afinament i buscar més edge brut o menor fricció.",
}


def recommend(risk: str) -> dict:
    return {"risk": risk, "next_test": ACTIONS.get(risk, "Recollir la dada mínima que falta abans de provar res."), "single_action": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("risk")
    args = parser.parse_args()
    print(json.dumps(recommend(args.risk), ensure_ascii=False, indent=2))
