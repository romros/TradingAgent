#!/usr/bin/env python3
"""Aplica gates Alquimia a CSV train/validacio i produeix supervivents auditables."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def _load(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    result = {row["Strategy Name"]: row for row in rows}
    if len(result) != len(rows): raise ValueError(f"Noms duplicats a {path}")
    return result

def _number(row: dict, column: str) -> float: return float(row[column])

def evaluate(train_csv: Path, validation_csv: Path, methodology_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text()); gate = methodology["temporal_validation"]
    train, validation = _load(train_csv), _load(validation_csv)
    if set(train) != set(validation):
        raise ValueError("Train i validacio han de contenir exactament els mateixos candidats")
    decisions = []
    for name in sorted(train):
        tr, va = train[name], validation[name]
        train_expectancy = _number(tr, "R Expectancy (IS)")
        validation_expectancy = _number(va, "R Expectancy (IS)")
        decay = ((train_expectancy - validation_expectancy) / train_expectancy * 100
                 if train_expectancy > 0 else float("inf"))
        metrics = {"trades": int(_number(va, "# of trades (IS)")),
            "profit_factor": _number(va, "Profit factor (IS)"),
            "r_expectancy": validation_expectancy, "expectancy_decay_pct": round(decay, 8),
            "drawdown_pct_normalized": round(_number(va, "Drawdown (IS)") / 10000 * 100, 8)}
        checks = {"minimum_trades": metrics["trades"] >= gate["minimum_trades_oos"],
            "minimum_profit_factor": metrics["profit_factor"] >= gate["minimum_oos_profit_factor"],
            "expectancy_decay": decay <= gate["maximum_train_oos_expectancy_decay_pct"],
            "maximum_drawdown": metrics["drawdown_pct_normalized"] <= gate["maximum_oos_drawdown_pct"],
            "positive_expectancy": validation_expectancy > 0}
        decisions.append({"strategy": name, "passed": all(checks.values()), "metrics": metrics, "checks": checks})
    survivors = [row["strategy"] for row in decisions if row["passed"]]
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "input_count": len(decisions), "survivor_count": len(survivors), "survivors": survivors,
        "decisions": decisions, "train_sha256": hashlib.sha256(train_csv.read_bytes()).hexdigest(),
        "validation_sha256": hashlib.sha256(validation_csv.read_bytes()).hexdigest()}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True); parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v1.json"))
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = evaluate(args.train, args.validation, args.methodology)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("input_count", "survivor_count", "survivors")}, indent=2))

if __name__ == "__main__": main()
