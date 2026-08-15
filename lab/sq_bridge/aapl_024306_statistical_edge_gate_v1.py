#!/usr/bin/env python3
"""Final statistical research-edge gate for frozen SQ candidate 0.24306."""
import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "aapl_024306_statistical_edge_preregistration_v1.json"
LOCK = HERE / "aapl_024306_statistical_edge_preregistration_v1.lock.json"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def returns(path):
    result = []
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            opening = float(row["Open price"].replace(",", "."))
            closing = float(row["Close price"].replace(",", "."))
            result.append(closing/opening-1 if row["Type"] == "Buy" else opening/closing-1)
    return result


def metrics(values):
    mean = sum(values)/len(values)
    sd = math.sqrt(sum((x-mean)**2 for x in values)/(len(values)-1))
    gains = sum(max(x,0) for x in values); losses = sum(max(-x,0) for x in values)
    return {"trades":len(values),"mean_return":mean,"profit_factor":gains/losses,
            "t_stat":mean/(sd/math.sqrt(len(values)))}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--validation-orders",type=Path,required=True)
    parser.add_argument("--oos-orders",type=Path,required=True); parser.add_argument("--validation-audit",type=Path,required=True)
    parser.add_argument("--oos-audit",type=Path,required=True); parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(); spec=json.loads(SPEC.read_text()); lock=json.loads(LOCK.read_text())
    if sha(SPEC)!=lock["preregistration_sha256"]: raise ValueError("lock mismatch")
    validation, oos=returns(args.validation_orders), returns(args.oos_orders); combined=validation+oos
    rng=random.Random(spec["robustness_tests"]["bootstrap_seed"]); n=spec["robustness_tests"]["bootstrap_iterations"]
    bootstrap_positive=sum(sum(rng.choice(combined) for _ in combined)>0 for _ in range(n))/n
    delete_three=sorted(combined,reverse=True)[3:]
    va=json.loads(args.validation_audit.read_text())["results"]["1000"]
    oo=json.loads(args.oos_audit.read_text())["results"]["1000"]
    stress_compounded=(1+va["stress"]["return_pct"]/100)*(1+oo["stress"]["return_pct"]/100)-1
    vm,om,cm=metrics(validation),metrics(oos),metrics(combined); g=spec["robustness_tests"]
    checks={"validation_trades":vm["trades"]>=g["validation_trades_gte"],"oos_trades":om["trades"]>=g["oos_trades_gte"],
            "each_period_positive":vm["mean_return"]>0 and om["mean_return"]>0,
            "combined_t_stat":cm["t_stat"]>=g["gross_combined_one_sided_t_stat_gte"],
            "combined_profit_factor":cm["profit_factor"]>=g["gross_combined_profit_factor_gte"],
            "bootstrap":bootstrap_positive>=g["bootstrap_probability_mean_positive_gte"],
            "delete_three":sum(delete_three)/len(delete_three)>0,
            "oos_tiered":oo["tiered"]["return_pct"]>0 and oo["tiered"]["profit_factor"]>=g["oos_tiered_profit_factor_gte"],
            "combined_stress":stress_compounded>0}
    passed=all(checks.values())
    result={"schema_version":1,"decision":"PASS_STATISTICAL_RESEARCH_EDGE" if passed else "REJECT_STATISTICAL_EDGE",
            "candidate":spec["candidate"],"preregistration_sha256":sha(SPEC),
            "source_sha256":{"validation_orders":sha(args.validation_orders),"oos_orders":sha(args.oos_orders),
                             "validation_audit":sha(args.validation_audit),"oos_audit":sha(args.oos_audit)},
            "validation_gross":vm,"oos_gross":om,"combined_gross":cm,"bootstrap_probability_mean_positive":bootstrap_positive,
            "delete_three_largest_winners":{"trades":len(delete_three),"mean_return":sum(delete_three)/len(delete_three)},
            "oos_tiered":oo["tiered"],"combined_stress_compounded_return":stress_compounded,"checks":checks,
            "holdout_2025_accessed":False,"paper_authorized":False,"live_authorized":False}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))


if __name__=="__main__": main()
