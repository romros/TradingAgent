#!/usr/bin/env python3
"""Tradueix observacions Alquímia a decisions de realitat sense inventar camps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def assess_observation(observation: dict) -> dict:
    campaign = observation.get("campaign_id", "unknown")
    insight = observation.get("assessment", {}).get("insight_code")
    facts = observation.get("observations", {})
    decision = "INCOMPLET"
    verified = False
    reason = "No hi ha prou camps normalitzats per arribar al gate de realitat."
    missing = ["manifest de règims", "economia actual", "estat del holdout"]

    if insight == "TEMPORAL_PASS_COST_FAIL":
        cost = facts.get("cost_base", {})
        metrics = cost.get("metrics", {})
        verified = cost.get("passed") is False and metrics.get("net_expectancy_usdc", 0) < 0
        reason = "L'expectativa neta és negativa amb els costos base observats."
    elif insight == "TEMPORAL_FAIL":
        validation = facts.get("validation", {})
        bootstrap = validation.get("bootstrap_mean_pnl_95pct_usd", [None, None])
        verified = validation.get("expectancy_usd", 0) < 0 and len(bootstrap) == 2 and bootstrap[1] is not None and bootstrap[1] < 0
        reason = "La validació té expectativa negativa i tot l'interval bootstrap queda sota zero."
    elif insight == "LOW_SAMPLE_OR_VALIDATION_FAIL":
        anomaly = facts.get("economic_anomaly", {})
        verified = anomaly.get("final_test_trades", 0) <= 1
        reason = "El profit factor final depèn d'un sol trade i no estima un edge transferible."
    elif insight == "OOS_REGIME_FAIL":
        oos = facts.get("official_base_oos", {})
        verified = oos.get("compound_return_pct", 0) < 0 and oos.get("profit_factor", 1) <= 1
        reason = "L'OOS oficial és negatiu i té profit factor no superior a 1."
    elif insight == "IS_ONLY_AND_COST_MISMATCH":
        verified = facts.get("oos_present") is False
        reason = "Només hi ha descoberta IS i els costos configurats no coincideixen."
        missing = ["validació temporal", "OOS", "costos reconciliats", "règims", "economia actual"]
    elif insight == "EDGE_PERSISTS_BUT_DECAYS":
        verified = facts.get("holdout_opened") is False and facts.get("oos", {}).get("profit", 0) > 0
        reason = "El signe persisteix fora de train, però encara falten normalització, règims i economia actual."
        missing = ["resultats normalitzats", "règims", "mida mínima", "marge i liquidació", "costos actuals"]
    elif insight == "PORTFOLIO_AGGREGATE_HIDES_COMPONENT_ASSUMPTIONS":
        zero_slippage = facts.get("result_slippage") == 0
        identity_warning = bool(facts.get("component_label_warning"))
        verified = zero_slippage and identity_warning
        reason = "La cartera usa slippage zero i conté una incoherència d'identitat de component."

    rejection_insights = {"TEMPORAL_PASS_COST_FAIL", "TEMPORAL_FAIL", "LOW_SAMPLE_OR_VALIDATION_FAIL", "OOS_REGIME_FAIL", "PORTFOLIO_AGGREGATE_HIDES_COMPONENT_ASSUMPTIONS"}
    if insight in rejection_insights and verified:
        decision = "DESCARTAR"
        missing = []
    elif insight in rejection_insights and not verified:
        reason = "L'etiqueta de rebuig no queda sostinguda pels camps observats; cal revisar l'artifact."
        missing = ["mètriques que provin el rebuig declarat"]

    return {
        "campaign_id": campaign,
        "family": observation.get("family", "unknown"),
        "decision": decision,
        "insight_code": insight,
        "metric_consistency_verified": verified,
        "reason": reason,
        "missing_before_reality_gate": missing,
        "source_artifacts": observation.get("source_artifacts", []),
        "next_step": (
            observation.get("assessment", {}).get("next_test", "No continuar amb el candidat.")
            if decision == "DESCARTAR"
            else f"Completar només: {', '.join(missing)}."
        ),
        "limits": "No obre holdout, paper trading ni live.",
    }


def render_markdown(results: list[dict]) -> str:
    lines = ["# Acceptació real del pont SQ → realitat", "", "| Campanya | Decisió | Comprovació | Motiu |", "|---|---|---|---|"]
    for result in results:
        check = "sí" if result["metric_consistency_verified"] else "no"
        lines.append(f"| {result['campaign_id']} | {result['decision']} | {check} | {result['reason']} |")
    lines.extend(["", "## Límit", "", "Aquest informe comprova decisions sobre observacions importades. No reobre artifacts externs ni autoritza trading.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path, nargs="+")
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    results = [assess_observation(json.loads(path.read_text(encoding="utf-8"))) for path in args.observations]
    print(render_markdown(results) if args.markdown else json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
