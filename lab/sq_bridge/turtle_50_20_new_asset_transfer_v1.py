#!/usr/bin/env python3
"""Transfer the frozen Turtle 50/20 rule to three untouched assets."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "turtle_50_20_new_asset_transfer_preregistration_v1.json"
LOCK = HERE / "turtle_50_20_new_asset_transfer_preregistration_v1.lock.json"


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    rows = []
    with Path(path).open(newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        if first.lower().startswith("date,"):
            for row in csv.DictReader(handle):
                day = dt.date.fromisoformat(row["date"])
                if day.year >= 2025: raise ValueError("2025 row refused")
                rows.append((day, float(row["open"]), float(row["close"])))
        else:
            for row in csv.reader(handle):
                if not row: continue
                day = dt.date.fromisoformat(row[0].replace(".", "-"))
                if day.year >= 2025: raise ValueError("2025 row refused")
                rows.append((day, float(row[2]), float(row[5])))
    return sorted(rows)


def trades(rows):
    closes = [x[2] for x in rows]; result = []; entry = None
    for i in range(50, len(rows) - 1):
        if entry is None and closes[i] > max(closes[i-50:i]):
            entry = (i + 1, rows[i+1][1])
        elif entry is not None and i >= entry[0] and closes[i] < min(closes[i-20:i]):
            result.append({"entry": str(rows[entry[0]][0]), "exit": str(rows[i+1][0]),
                           "return": rows[i+1][1] / entry[1] - 1})
            entry = None
    return result


def subset(values, start, end):
    return [x for x in values if start <= dt.date.fromisoformat(x["entry"])
            and dt.date.fromisoformat(x["exit"]) <= end]


def metrics(values):
    returns = [x["return"] for x in values]
    if not returns: return {"trades": 0}
    mean = sum(returns) / len(returns)
    sd = math.sqrt(sum((x-mean)**2 for x in returns) / (len(returns)-1)) if len(returns)>1 else 0
    gains = sum(max(x, 0) for x in returns); losses = sum(max(-x, 0) for x in returns)
    equity = peak = 1.; dd = 0.
    for value in returns:
        equity *= 1 + value; peak = max(peak, equity); dd = max(dd, 1-equity/peak)
    return {"trades": len(returns), "mean_return": mean, "total_return": equity-1,
            "profit_factor": gains/losses if losses else None,
            "t_stat": mean/(sd/math.sqrt(len(returns))) if sd else None,
            "max_drawdown": dd}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]: raise ValueError("lock mismatch")
    parent_path = HERE.parents[1] / spec["parent_result"]
    if sha(parent_path) != spec["parent_result_sha256"]: raise ValueError("parent mismatch")
    paths = dict(value.split("=", 1) for value in args.asset)
    if set(paths) != set(spec["new_assets"]): raise ValueError("frozen universe required")
    all_trades = {asset: trades(load(path)) for asset, path in paths.items()}
    periods = {}; pooled_new = []
    for name, bounds in spec["periods"].items():
        start, end = map(dt.date.fromisoformat, bounds)
        by_asset = {asset: subset(values, start, end) for asset, values in all_trades.items()}
        pool = sorted((x for values in by_asset.values() for x in values), key=lambda x: x["exit"])
        periods[name] = {"pooled": metrics(pool), "by_asset": {a: metrics(v) for a,v in by_asset.items()}}
        if name != "train": pooled_new += pool
    parent = json.loads(parent_path.read_text())
    # The immutable parent exposes aggregate metrics but not individual trades;
    # reconstruct its sufficient statistics from the original exact rule output
    # is impossible. Combine t-stat conservatively by treating each parent trade
    # as its reported mean plus variance implied by its reported t-stat.
    pm = parent["decision"]["combined_validation_oos"]
    new_returns = [x["return"] for x in pooled_new]
    n0, m0, t0 = pm["trades"], pm["mean_return"], pm["t_stat"]
    ss0 = (m0 * math.sqrt(n0) / t0) ** 2 * (n0 - 1)
    n = n0 + len(new_returns); mean = (n0*m0 + sum(new_returns))/n
    ss = ss0 + sum((x-mean)**2 for x in new_returns) + n0*(m0-mean)**2
    combined_t = mean / math.sqrt((ss/(n-1))/n)
    gains0 = pm["profit_factor"] / (1 + pm["profit_factor"]) * (abs(m0)*n0*(1+pm["profit_factor"])/max(abs(pm["profit_factor"]-1),1e-12))
    losses0 = gains0 / pm["profit_factor"]
    gains = gains0 + sum(max(x,0) for x in new_returns); losses = losses0 + sum(max(-x,0) for x in new_returns)
    positive = sum((periods["validation"]["by_asset"][a].get("total_return",0) + periods["oos_2024"]["by_asset"][a].get("total_return",0)) > 0 for a in paths)
    nm = metrics(pooled_new); gates = spec["gates"]
    passed = (nm["trades"] >= gates["new_assets_combined_validation_oos_trades_gte"]
              and (nm["profit_factor"] or 0) >= gates["new_assets_combined_validation_oos_profit_factor_gte"]
              and positive >= gates["new_assets_positive_gte"]
              and combined_t >= gates["all_assets_combined_validation_oos_t_stat_gte"]
              and gains/losses >= gates["all_assets_combined_validation_oos_profit_factor_gte"])
    result = {"schema_version":1,"decision":"PASS_TRANSFER_EDGE" if passed else "REJECT_TRANSFER",
              "preregistration_sha256":sha(SPEC),"source_sha256":{a:sha(p) for a,p in paths.items()},
              "periods":periods,"new_assets_combined_validation_oos":nm,"new_positive_assets":positive,
              "all_assets_combined_validation_oos":{"trades":n,"mean_return":mean,"profit_factor":gains/losses,"t_stat":combined_t},
              "optimized":False,"holdout_2025_accessed":False,"paper_authorized":False,"live_authorized":False}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__": main()
