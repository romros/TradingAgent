#!/usr/bin/env python3
"""Build a source-bound robustness trace from SQ exports and observed trades."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path

from lab.sq_bridge.sq_temporal_trace_v4 import rebuild_from_trace as rebuild_temporal
from lab.sq_bridge.sqcli_supervised_mc_exports import verify_export_receipt
from lab.sq_bridge.sqx_extract import extract as extract_sqx


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: str, label: str) -> float:
    try:
        result = float(value.strip().replace(" ", "").replace(",", "."))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{label} MC no numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} MC invalid")
    return result


def _variant_aggregate(path: Path, notional: float) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        required = {"Type", "Open time", "Open price", "Close time", "Close price"}
        if required - set(reader.fieldnames or ()):
            raise ValueError("CSV MC sense columnes de retorn")
        rows = list(reader)
    gross, long_days, short_days = 0.0, 0.0, 0.0
    for row in rows:
        direction = row["Type"].strip().lower()
        if direction not in {"buy", "sell", "long", "short"}:
            raise ValueError("direccio MC invalida")
        side = "long" if direction in {"buy", "long"} else "short"
        entry = _number(row["Open price"], "entrada")
        exit_price = _number(row["Close price"], "sortida")
        if entry <= 0 or exit_price <= 0:
            raise ValueError("preu MC invalid")
        try:
            from pandas import Timestamp
            opened, closed = Timestamp(row["Open time"]), Timestamp(row["Close time"])
            days = (closed - opened).total_seconds() / 86400
        except (TypeError, ValueError) as exc:
            raise ValueError("timestamp MC invalid") from exc
        if days <= 0:
            raise ValueError("durada MC no positiva")
        sign = 1 if side == "long" else -1
        gross += notional * sign * (exit_price - entry) / entry
        if side == "long":
            long_days += days
        else:
            short_days += days
    return {"gross_pnl_usdc": gross, "trade_count": len(rows),
            "long_holding_days": long_days, "short_holding_days": short_days}


def _all_base_trades(temporal: dict) -> list[dict]:
    return [*temporal["train_trades"],
            *(trade for window in temporal["oos_windows"]
              for trade in window["trades"])]


def derive(*, candidate_id: str, temporal_trace_path: Path,
           mc_export_receipt_path: Path, cost_model_path: Path,
           tested_leverage: float, venue_max_leverage: float,
           monte_carlo_runs: int = 1000, random_seed: int = 20260811,
           maximum_parameter_perturbation_pct: int = 10,
           evaluation_notional_usdc: float = 200) -> dict:
    if (not candidate_id or evaluation_notional_usdc != 200
            or monte_carlo_runs != 1000 or random_seed < 0
            or maximum_parameter_perturbation_pct != 10):
        raise ValueError("contracte de robustesa v4 no canonic")
    temporal_raw = json.loads(temporal_trace_path.read_text())
    temporal = rebuild_temporal(temporal_raw)
    if temporal != temporal_raw or temporal.get("candidate_id") != candidate_id:
        raise ValueError("trace temporal de robustesa no reproduible")
    exports = verify_export_receipt(mc_export_receipt_path)
    native = exports["runs"]
    materialization = json.loads(
        Path(exports["materialization_manifest_path"]).read_text())
    native_contract = materialization["native_contract"]
    native_sqx = Path(materialization["source_sqx_path"])
    native_sqx_contract = extract_sqx(native_sqx)
    retest_receipt = json.loads(
        Path(temporal["supervised_retest_receipt_path"]).read_text())
    retest_manifest = json.loads(Path(retest_receipt["manifest_path"]).read_text())
    expected_range = (f'{retest_manifest["date_from"].replace("-", ".")} - '
                      f'{retest_manifest["date_to"].replace("-", ".")}')
    if (exports["simulation_count"] != 1000
            or native_contract.get("method") != "RandomizeStrategyParameters"
            or native_contract.get("probability_pct") != 10
            or native_contract.get("max_change_pct") != 10
            or native_contract.get("date_range") != expected_range
            or native_contract.get("symbol")
                != native_sqx_contract.get("market", {}).get("symbol")
            or native_contract.get("timeframe")
                != native_sqx_contract.get("market", {}).get("timeframe")
            or native_sqx_contract.get("strategy_name") != candidate_id
            or native_sqx_contract.get("strategy_xml_sha256")
                != retest_receipt.get("retest_output_strategy_xml_sha256")):
        raise ValueError("MC natiu no lliga amb candidat, periode i metode")
    base = _all_base_trades(temporal)
    if len(base) < 30:
        raise ValueError("robustesa requereix almenys 30 trades pre-holdout")
    for trade in base:
        mae = trade.get("maximum_adverse_excursion_pct")
        if (not isinstance(mae, (int, float)) or isinstance(mae, bool)
                or not math.isfinite(mae) or mae < 0):
            raise ValueError("MAE temporal absent per robustesa")
    rng = random.Random(random_seed)
    bootstrap = []
    for index in range(monte_carlo_runs):
        sampled = [rng.choice(base) for _ in base]
        worst = max(sampled, key=lambda row: row["maximum_adverse_excursion_pct"])
        bootstrap.append({
            "run_id": f"run-{index:04d}",
            "gross_pnl_usdc": sum(
                evaluation_notional_usdc * row["gross_return_pct"] / 100
                for row in sampled),
            "trade_count": len(sampled),
            "long_holding_days": sum(row["holding_days"] for row in sampled
                                     if row["side"] == "long"),
            "short_holding_days": sum(row["holding_days"] for row in sampled
                                      if row["side"] == "short"),
            "maximum_adverse_excursion_pct": worst["maximum_adverse_excursion_pct"],
            "maximum_adverse_excursion_side": worst["side"],
            # SQ exports MAE magnitude but not its intratrade timestamp. Using
            # the full holding duration makes the carry buffer conservative.
            "maximum_adverse_excursion_holding_days": worst["holding_days"],
        })
    variants = []
    for row in native:
        aggregate = _variant_aggregate(Path(row["orders_csv_path"]),
                                       evaluation_notional_usdc)
        variants.append({
            "variant_id": row["run_id"],
            "maximum_perturbation_pct": maximum_parameter_perturbation_pct,
            **aggregate,
        })
    stress = [{"gross_return_pct": row["gross_return_pct"],
               "side": row["side"], "holding_days": row["holding_days"]}
              for row in base]
    return {
        "schema_version": 1,
        "trace_type": "robustness_simulation_trace",
        "source": "sq_native_parameter_mc_plus_observed_trade_bootstrap",
        "candidate_id": candidate_id,
        "capital_usdc": 200,
        "evaluation_notional_usdc": 200,
        "holdout_accessed": False,
        "tested_leverage": tested_leverage,
        "venue_max_leverage": venue_max_leverage,
        "liquidation_model": "ostium_threshold_cost_buffered",
        "cost_stress_multiplier": 2,
        "cost_model_sha256": _sha(cost_model_path),
        "monte_carlo_method": "iid_observed_trade_bootstrap_with_replacement",
        "monte_carlo_seed": random_seed,
        "monte_carlo_runs": bootstrap,
        "parameter_variant_method": "strategyquant_RandomizeStrategyParameters",
        "parameter_probability_pct": 10,
        "parameter_variants": variants,
        "stress_trades": stress,
        "temporal_trace_path": str(temporal_trace_path.resolve()),
        "temporal_trace_sha256": _sha(temporal_trace_path),
        "mc_export_receipt_path": str(mc_export_receipt_path.resolve()),
        "mc_export_receipt_sha256": _sha(mc_export_receipt_path),
        "cost_model_path": str(cost_model_path.resolve()),
    }


def rebuild_from_trace(trace: dict) -> dict:
    try:
        temporal = Path(trace["temporal_trace_path"])
        exports = Path(trace["mc_export_receipt_path"])
        costs = Path(trace["cost_model_path"])
    except (KeyError, TypeError) as exc:
        raise ValueError("fonts de robustesa absents") from exc
    for path, key in ((temporal, "temporal_trace_sha256"),
                      (exports, "mc_export_receipt_sha256"),
                      (costs, "cost_model_sha256")):
        if not path.is_file() or _sha(path) != trace.get(key):
            raise ValueError("font de robustesa manipulada")
    return derive(
        candidate_id=trace.get("candidate_id", ""), temporal_trace_path=temporal,
        mc_export_receipt_path=exports, cost_model_path=costs,
        tested_leverage=trace.get("tested_leverage"),
        venue_max_leverage=trace.get("venue_max_leverage"),
        monte_carlo_runs=len(trace.get("monte_carlo_runs", [])),
        random_seed=trace.get("monte_carlo_seed"),
        maximum_parameter_perturbation_pct=10,
        evaluation_notional_usdc=trace.get("evaluation_notional_usdc"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--temporal-trace", required=True, type=Path)
    parser.add_argument("--mc-export-receipt", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--tested-leverage", required=True, type=float)
    parser.add_argument("--venue-max-leverage", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = derive(
        candidate_id=args.candidate_id, temporal_trace_path=args.temporal_trace,
        mc_export_receipt_path=args.mc_export_receipt,
        cost_model_path=args.cost_model, tested_leverage=args.tested_leverage,
        venue_max_leverage=args.venue_max_leverage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_id": args.candidate_id,
                      "monte_carlo_runs": len(result["monte_carlo_runs"]),
                      "parameter_variants": len(result["parameter_variants"])}, indent=2))


if __name__ == "__main__":
    main()
