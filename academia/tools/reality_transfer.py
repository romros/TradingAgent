#!/usr/bin/env python3
"""Porta mínima entre un backtest històric i una hipòtesi executable avui."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {"candidate_id", "instrument", "venue", "generation_period", "sealed_period", "mechanism", "normalization", "regime_results", "current_execution"}


def assess(case: dict) -> dict:
    missing = sorted(REQUIRED - case.keys())
    if missing:
        return _result(case, "DESCARTAR", "Falta evidència mínima de transferència.", "evidència incompleta", f"Completar: {', '.join(missing)}")

    red: list[str] = []
    amber: list[str] = []
    sealed = case["sealed_period"]
    norm = case["normalization"]
    execution = case["current_execution"]
    regimes = case["regime_results"]

    if sealed.get("used_in_development"):
        red.append("el període final ja ha influït en el desenvolupament")
    if not case["mechanism"].get("hypothesis") or not case["mechanism"].get("falsifier"):
        red.append("no hi ha mecanisme falsable")
    if norm.get("price_distances") == "fixed":
        amber.append("les distàncies fixes no escalen amb preu o volatilitat")
    if norm.get("position_risk") == "fixed_notional":
        amber.append("el risc fix nocional no escala amb el compte")
    if not execution.get("liquidation_checked"):
        red.append("no s'ha comprovat liquidació o marge")
    if execution.get("net_expectancy", 0) <= 0:
        red.append("l'expectativa és no positiva amb costos actuals")
    if execution.get("minimum_position_notional", float("inf")) > execution.get("account_equity", 0):
        amber.append("la mida mínima supera el capital del compte")

    positive = [r for r in regimes if r.get("trades", 0) > 0 and r.get("net_expectancy", 0) > 0]
    comparable = [r for r in positive if r.get("comparable_to_current")]
    if len(positive) < 2:
        red.append("el benefici no apareix en almenys dos règims")
    if not comparable:
        red.append("cap règim comparable a l'actual és positiu")
    old_bull = [r for r in positive if "secular_bull" in r.get("tags", []) and str(r.get("id", "")) <= "2011-12"]
    if positive and len(old_bull) == len(positive):
        red.append("el benefici depèn exclusivament del cicle alcista antic")

    if red:
        return _result(case, "DESCARTAR", "; ".join(red[:2]) + ".", red[0], "Reformular la hipòtesi; no optimitzar el candidat per salvar-lo.")
    if amber:
        return _result(case, "PROVA DIRIGIDA", "; ".join(amber[:2]) + ".", amber[0], "Executar una sola prova preregistrada amb risc normalitzat i especificació actual del venue.")
    return _result(case, "CONTINUAR", "La lògica és positiva en règims diversos i comparables i conserva expectativa neta amb condicions actuals.", "canvi de règim no observat", "Executar una vegada el període final segellat i no reajustar després.")


def _result(case: dict, decision: str, reason: str, risk: str, next_step: str) -> dict:
    return {"candidate": case.get("candidate_id", "unknown"), "decision": decision, "reason": reason, "main_risk": risk, "next_step": next_step}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(json.loads(args.case.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
