#!/usr/bin/env python3
"""Gate temporal per una etapa que rep els supervivents exactes de l'anterior."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from temporal_gate import _load, _number

def evaluate(baseline_csv: Path, stage_csv: Path, input_gate: Path, methodology_path: Path) -> dict:
    baseline, stage=_load(baseline_csv),_load(stage_csv); previous=json.loads(input_gate.read_text())
    expected=set(previous["survivors"])
    if set(stage)!=expected: raise ValueError("L'etapa no conte exactament els supervivents esperats")
    if not expected.issubset(baseline): raise ValueError("Supervivents absents al baseline")
    limits=json.loads(methodology_path.read_text())["temporal_validation"]; decisions=[]
    for name in sorted(expected):
        before, current=baseline[name],stage[name]
        prior_exp=_number(before,"R Expectancy (IS)"); current_exp=_number(current,"R Expectancy (IS)")
        decay=(prior_exp-current_exp)/prior_exp*100 if prior_exp>0 else float("inf")
        metrics={"trades":int(_number(current,"# of trades (IS)")),
            "profit_factor":_number(current,"Profit factor (IS)"),"r_expectancy":current_exp,
            "expectancy_decay_pct":round(decay,8),
            "drawdown_pct_normalized":round(_number(current,"Drawdown (IS)")/10000*100,8)}
        checks={"minimum_trades":metrics["trades"]>=limits["minimum_trades_oos"],
            "minimum_profit_factor":metrics["profit_factor"]>=limits["minimum_oos_profit_factor"],
            "positive_expectancy":current_exp>0,
            "expectancy_decay":decay<=limits["maximum_train_oos_expectancy_decay_pct"],
            "maximum_drawdown":metrics["drawdown_pct_normalized"]<=limits["maximum_oos_drawdown_pct"]}
        decisions.append({"strategy":name,"passed":all(checks.values()),"metrics":metrics,"checks":checks})
    survivors=[row["strategy"] for row in decisions if row["passed"]]
    return {"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),
        "input_count":len(expected),"survivor_count":len(survivors),"survivors":survivors,"decisions":decisions,
        "baseline_sha256":hashlib.sha256(baseline_csv.read_bytes()).hexdigest(),
        "stage_sha256":hashlib.sha256(stage_csv.read_bytes()).hexdigest(),
        "input_gate_sha256":hashlib.sha256(input_gate.read_bytes()).hexdigest()}

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline",type=Path,required=True); parser.add_argument("--stage",type=Path,required=True)
    parser.add_argument("--input-gate",type=Path,required=True); parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--methodology",type=Path,default=Path(__file__).with_name("methodology_v1.json")); args=parser.parse_args()
    result=evaluate(args.baseline,args.stage,args.input_gate,args.methodology); args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("input_count","survivor_count","survivors")},indent=2))

if __name__=="__main__": main()
