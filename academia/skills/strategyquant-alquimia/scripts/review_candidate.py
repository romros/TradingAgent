#!/usr/bin/env python3
import json
import sys


def review(c):
    red, amber = [], []
    if c.get("holdout_peeks", 1): red.append("holdout contaminat")
    if c.get("attempts_observed", 1) > c.get("attempt_budget", 0): red.append("pressupost superat")
    if not c.get("costs_included"): red.append("costos absents")
    if not c.get("drawdown_acceptable"): red.append("drawdown inacceptable")
    if c.get("wfm_passed_cells", 0) == 0: red.append("WFM sense passes")
    if c.get("trades", 0) < c.get("minimum_trades", 1): amber.append("pocs trades")
    if c.get("wfm_largest_connected_region", 0) < 2: amber.append("pic WFM aïllat")
    if c.get("max_run_profit_share", 1) > .5: amber.append("benefici concentrat")
    if red:
        decision, reason, step = "DESCARTAR", red[0], "Revisar hipòtesi; no buscar més variants."
    elif amber:
        decision, reason, step = "PROVA DIRIGIDA", amber[0], "Resoldre només aquest risc sense canviar regles."
    else:
        decision, reason, step = "CONTINUAR", "controls mínims superats", "Una prova al holdout final intacte."
    return {"decision": decision, "reason": reason, "next_step": step}


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        print(json.dumps(review(json.load(handle)), ensure_ascii=False, indent=2))
