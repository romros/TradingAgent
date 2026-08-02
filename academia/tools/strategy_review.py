#!/usr/bin/env python3
"""Revisor educatiu simple: converteix evidència mínima en una decisió pràctica."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def review(candidate: dict) -> dict:
    red: list[str] = []
    amber: list[str] = []

    required = {
        "id", "trades", "minimum_trades", "costs_included", "attempt_budget",
        "attempts_observed", "holdout_peeks", "wfm_passed_cells", "wfm_total_cells",
        "wfm_largest_connected_region", "max_run_profit_share", "drawdown_acceptable",
    }
    missing = sorted(required - candidate.keys())
    if missing:
        return {
            "candidate": candidate.get("id", "unknown"), "decision": "DESCARTAR",
            "reason": "Falten dades mínimes per revisar el candidat.",
            "main_risk": "resultat no auditable", "next_step": f"Completar: {', '.join(missing)}",
        }

    if candidate["holdout_peeks"] > 0:
        red.append("el holdout ja ha influït en el desenvolupament")
    if candidate["attempts_observed"] > candidate["attempt_budget"]:
        red.append("s'ha superat el pressupost d'intents")
    if not candidate["costs_included"]:
        red.append("el resultat no inclou costos")
    if candidate["trades"] < candidate["minimum_trades"]:
        amber.append("hi ha menys trades que el mínim declarat")
    if candidate["wfm_passed_cells"] == 0:
        red.append("cap cel·la WFM supera els criteris")
    elif candidate["wfm_largest_connected_region"] < 2:
        amber.append("el resultat WFM depèn de cel·les aïllades")
    if candidate["max_run_profit_share"] > 0.50:
        amber.append("més de la meitat del benefici depèn d'un sol run")
    if not candidate["drawdown_acceptable"]:
        red.append("el drawdown supera el límit declarat")

    if red:
        return {
            "candidate": candidate["id"], "decision": "DESCARTAR",
            "reason": "; ".join(red[:2]) + ".", "main_risk": red[0],
            "next_step": "No buscar més combinacions; revisar la hipòtesi o reservar dades noves.",
            "evidence": "paper_white_data_snooping_2000#abstract:data-snooping",
        }
    if amber:
        next_step = (
            "Executar una prova amb més observacions sense canviar regles."
            if candidate["trades"] < candidate["minimum_trades"]
            else "Provar la regió veïna preregistrada i revisar la concentració per run."
        )
        return {
            "candidate": candidate["id"], "decision": "PROVA DIRIGIDA",
            "reason": "; ".join(amber[:2]) + ".", "main_risk": amber[0],
            "next_step": next_step,
            "evidence": "sq_official_walk_forward_values_20190101#section:concentration",
        }
    return {
        "candidate": candidate["id"], "decision": "CONTINUAR",
        "reason": "Supera els controls mínims i la WFM mostra una regió connectada sense concentració excessiva.",
        "main_risk": "la validació històrica no garanteix rendiment futur",
        "next_step": "Fer una única prova en el holdout final intacte, sense reajustar després.",
        "evidence": "sq_official_walk_forward_matrix_20150506#section:interpretation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    print(json.dumps([review(item) for item in candidates], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
