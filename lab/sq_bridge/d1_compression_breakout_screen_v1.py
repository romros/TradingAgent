#!/usr/bin/env python3
"""Evaluate the frozen multi-asset D1 compression-breakout family in R units."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREG = HERE / "d1_compression_breakout_preregistration_v1.json"
LOCK = HERE / "d1_compression_breakout_preregistration_v1.lock.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen() -> dict:
    lock = json.loads(LOCK.read_text())
    if digest(PREREG) != lock["preregistration_sha256"]:
        raise ValueError("preregistration hash mismatch")
    spec = json.loads(PREREG.read_text())
    if spec["status"] != "FROZEN_BEFORE_PERFORMANCE":
        raise ValueError("preregistration is not frozen")
    return spec


def load(path: Path) -> list[dict]:
    if "2025" in path.name:
        raise ValueError("2025 holdout filename refused")
    raw = list(csv.reader(path.open(newline="", encoding="utf-8-sig")))
    out = []
    for row in raw:
        if not row or row[0].lower() == "date":
            continue
        day = row[0].replace(".", "-")
        if day > "2024-12-31":
            raise ValueError("2025 holdout row refused")
        offset = 2 if len(row) > 1 and ":" in row[1] else 1
        values = list(map(float, row[offset:offset + 4]))
        out.append(dict(date=day, open=values[0], high=max(values[0], values[1], values[3]),
                        low=min(values[0], values[2], values[3]), close=values[3]))
    if not out or any(b["date"] <= a["date"] for a, b in zip(out, out[1:])):
        raise ValueError("source must contain increasing unique dates")
    return out


def rolling(rows: list[dict]) -> tuple[list[float | None], list[float | None], list[float | None]]:
    tr = []
    for i, row in enumerate(rows):
        prev = rows[i - 1]["close"] if i else row["close"]
        tr.append(max(row["high"] - row["low"], abs(row["high"] - prev), abs(row["low"] - prev)))
    def mean(values: list[float], n: int) -> list[float | None]:
        answer, total = [None] * len(values), 0.0
        for i, value in enumerate(values):
            total += value
            if i >= n:
                total -= values[i - n]
            if i >= n - 1:
                answer[i] = total / n
        return answer
    return mean(tr, 5), mean(tr, 20), mean([r["close"] for r in rows], 200)


def trades(rows: list[dict], ratio: float, breakout: int, hold: int,
           start: str, end: str) -> list[float]:
    atr5, atr20, sma200 = rolling(rows)
    eligible = [i for i, r in enumerate(rows) if start <= r["date"] <= end]
    if not eligible:
        return []
    result, position = [], None
    for i in eligible:
        row = rows[i]
        if position:
            position["held"] += 1
            if row["open"] <= position["stop"]:
                result.append((row["open"] - position["entry"]) / position["risk"]); position = None
            elif row["low"] <= position["stop"]:
                result.append(-1.0); position = None
            elif position["held"] >= hold:
                result.append((row["close"] - position["entry"]) / position["risk"]); position = None
        signal = i - 1
        if position is None and signal >= max(219, breakout):
            trend = (sma200[signal] is not None and sma200[signal - 20] is not None
                     and rows[signal]["close"] > sma200[signal] > sma200[signal - 20])
            compressed = (atr20[signal] and atr5[signal] is not None
                          and atr5[signal] / atr20[signal] <= ratio)
            prior_high = max(r["high"] for r in rows[signal - breakout:signal])
            if trend and compressed and rows[signal]["close"] > prior_high:
                risk = 2.0 * atr20[signal]
                position = {"entry": row["open"], "risk": risk,
                            "stop": row["open"] - risk, "held": 1}
                if row["low"] <= position["stop"]:
                    result.append(-1.0); position = None
    if position:
        row = rows[eligible[-1]]
        result.append((row["close"] - position["entry"]) / position["risk"])
    return result


def stats(values: list[float]) -> dict:
    gains, losses = sum(max(x, 0) for x in values), -sum(min(x, 0) for x in values)
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value; peak = max(peak, equity); drawdown = max(drawdown, peak - equity)
    return {"trades": len(values), "mean_r": sum(values) / len(values) if values else None,
            "net_r": sum(values), "profit_factor_r": gains / losses if losses else None,
            "maximum_drawdown_r": drawdown, "win_rate": sum(x > 0 for x in values) / len(values) if values else None}


def passes(period: dict, minimum: int, gates: dict) -> bool:
    pf = period["profit_factor_r"]
    return (period["trades"] >= minimum and period["mean_r"] is not None
            and period["mean_r"] >= gates["minimum_mean_r_each_validation_and_oos"]
            and pf is not None and pf >= gates["minimum_profit_factor_r_each_validation_and_oos"]
            and period["maximum_drawdown_r"] <= gates["maximum_drawdown_r_each_validation_and_oos"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = frozen()
    supplied = dict(item.split("=", 1) for item in args.asset)
    if set(supplied) != set(spec["assets"]):
        raise SystemExit("all and only frozen assets are required")
    periods, gates, grid = spec["temporal_contract"], spec["statistical_gates"], spec["grid"]
    report = {"schema_version": 1, "preregistration_sha256": digest(PREREG), "assets": {},
              "holdout_2025_accessed": False, "optimized": False}
    variant_assets: dict[str, list[str]] = {}
    for asset, name in supplied.items():
        path, rows = Path(name), load(Path(name))
        variants = {}
        for ratio, breakout, hold in itertools.product(grid["compression_ratio"], grid["breakout_days"], grid["maximum_holding_sessions"]):
            vid = f"c{ratio:g}_b{breakout}_h{hold}"
            result = {p: stats(trades(rows, ratio, breakout, hold, *periods[p])) for p in ("train", "validation", "oos")}
            combined = result["validation"]["trades"] + result["oos"]["trades"]
            ok = (result["train"]["mean_r"] is not None and result["train"]["mean_r"] >= 0
                  and passes(result["validation"], gates["minimum_validation_trades_per_asset"], gates)
                  and passes(result["oos"], gates["minimum_oos_trades_per_asset"], gates)
                  and combined >= gates["minimum_validation_oos_trades_per_asset"])
            variants[vid] = {"parameters": {"compression_ratio": ratio, "breakout_days": breakout,
                                              "maximum_holding_sessions": hold}, "periods": result, "asset_pass": ok}
            if ok:
                variant_assets.setdefault(vid, []).append(asset)
        report["assets"][asset] = {"source": str(path.resolve()), "source_sha256": digest(path), "variants": variants}
    report["cross_asset_passing_variants"] = {k: v for k, v in variant_assets.items()
                                               if len(v) >= gates["minimum_assets_passing_same_variant"]}
    report["family_density_pass"] = len(report["cross_asset_passing_variants"]) >= 2
    report["sqcli_authorized"] = report["family_density_pass"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"family_density_pass": report["family_density_pass"],
                      "cross_asset_passing_variants": report["cross_asset_passing_variants"]}, indent=2))


if __name__ == "__main__":
    main()
