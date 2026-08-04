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
        return _result(case, "INCOMPLET", "Falta evidència mínima de transferència.", ["evidència incompleta"], f"Completar: {', '.join(missing)}")

    red: list[str] = []
    amber: list[str] = []
    sealed = case["sealed_period"]
    norm = case["normalization"]
    execution = case["current_execution"]
    regimes = case["regime_results"]
    economics = _economics(execution)

    if execution.get("evidence_complete") is False:
        return _result(
            case,
            "INCOMPLET",
            "Les condicions d'execució actuals encara contenen placeholders o valors no verificats.",
            ["economia actual no verificada"],
            "Mesurar costos, mida mínima, marge, liquidació i expectativa neta amb data i venue.",
            economics,
        )

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
    if economics["required_leverage"] > 1:
        safe = execution.get("max_safe_leverage")
        if safe is None:
            amber.append("la mida mínima exigeix palanquejament però no hi ha cap límit segur justificat")
        elif economics["required_leverage"] > safe:
            red.append("la mida mínima exigeix més palanquejament que el límit segur")

    positive = [r for r in regimes if r.get("trades", 0) > 0 and r.get("net_expectancy", 0) > 0]
    comparable = [r for r in positive if r.get("comparable_to_current")]
    if len(positive) < 2:
        red.append("el benefici no apareix en almenys dos règims")
    if not comparable:
        red.append("cap règim comparable a l'actual és positiu")
    old_bull = [r for r in positive if "secular_bull" in r.get("tags", []) and str(r.get("id", "")) <= "2011-12"]
    if positive and len(old_bull) == len(positive):
        red.append("el benefici depèn exclusivament del cicle alcista antic")

    if sealed.get("executed") and sealed.get("passed") is False:
        red.append("el període final segellat ha fallat")
    if sealed.get("executed") and "passed" not in sealed:
        amber.append("el període final consta executat però falta el seu resultat")

    if red:
        return _result(case, "DESCARTAR", "; ".join(red[:2]) + ".", red, "Reformular la hipòtesi; no optimitzar el candidat per salvar-lo.", economics)
    if amber:
        return _result(case, "PROVA DIRIGIDA", "; ".join(amber[:2]) + ".", amber, "Executar una sola prova preregistrada que resolgui el primer buit.", economics)
    if sealed.get("executed") and sealed.get("passed"):
        return _result(case, "PREPARAR PAPER TRADING", "Mecanisme, règims, economia actual i període final segellat han passat els gates declarats.", ["degradació futura o divergència d'execució"], "Traduir la regla, provar paritat d'ordres i iniciar paper trading amb criteris de retirada.", economics)
    return _result(case, "OBRIR HOLDOUT", "La lògica és positiva en règims diversos i comparables i conserva expectativa neta amb condicions actuals.", ["el període final encara pot falsar-la"], "Executar una vegada el període final segellat i no reajustar després.", economics)


def _economics(execution: dict) -> dict:
    equity = execution.get("account_equity", 0)
    minimum = execution.get("minimum_position_notional", 0)
    result = {
        "account_equity": equity,
        "minimum_position_notional": minimum,
        "required_leverage": round(minimum / equity, 4) if equity > 0 else None,
    }
    risk_pct = execution.get("risk_per_trade_pct")
    if risk_pct is not None and equity > 0:
        result["risk_per_trade_amount"] = round(equity * risk_pct / 100, 4)
    expectancy = execution.get("net_expectancy_per_trade_account")
    trades = execution.get("expected_trades_per_year")
    if expectancy is not None and trades is not None:
        result["estimated_net_per_year"] = round(expectancy * trades, 4)
        result["estimated_net_per_year_pct"] = round(expectancy * trades / equity * 100, 4) if equity > 0 else None
    return result


def _result(case: dict, decision: str, reason: str, risks: list[str], next_step: str, economics: dict | None = None) -> dict:
    return {
        "candidate": case.get("candidate_id", "unknown"),
        "decision": decision,
        "reason": reason,
        "failed_or_open_gates": risks,
        "main_risk": risks[0],
        "economics": economics,
        "next_step": next_step,
        "limits": "Decisió de recerca, no autorització de trading real.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(json.loads(args.case.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
