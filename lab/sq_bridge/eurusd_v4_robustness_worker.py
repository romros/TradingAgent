#!/usr/bin/env python3
"""Resume a passing EURUSD temporal Pareto through native SQ robustness."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.sq_robustness_stage_v4 import run_stage
from lab.sq_bridge.sqcli_transport import list_projects
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verified(value: object, digest: object, label: str,
              base: Path | None = None) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else ((base or Path.cwd()) / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def venue_max_leverage(cost_model: dict[str, Any]) -> float:
    """Derive a conservative current EURUSD cap from frozen Ostium evidence."""
    instrument = cost_model.get("instrument") or {}
    if (str(instrument.get("pair_id")), instrument.get("pair_from"),
            instrument.get("pair_to"), instrument.get("category")) \
            != ("2", "EUR", "USD", "forex"):
        raise ValueError("EURUSD_OSTIUM_INSTRUMENT_IDENTITY_INVALID")
    limits = cost_model.get("venue_limits") or {}
    leverage = limits.get("max_leverage") or {}
    overnight = limits.get("overnight_max_leverage") or {}
    values = [leverage.get(key) for key in ("min", "p50", "p95", "max")]
    overnight_values = [overnight.get(key) for key in ("min", "p50", "p95", "max")]
    if (not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                and value > 0 for value in values)
            or not isinstance(leverage.get("n"), int) or leverage["n"] < 30
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       and value == 0 for value in overnight_values)
            or not isinstance(overnight.get("n"), int) or overnight["n"] < 30):
        raise ValueError("EURUSD_OSTIUM_LEVERAGE_EVIDENCE_INSUFFICIENT")
    # overnightMaxLeverage is a stock day-trading override. Zero on a forex
    # pair means no special stock override; it must never replace maxLeverage.
    return float(min(values))


def _running(rows: list[dict]) -> list[str]:
    return sorted(str(row.get("projectName")) for row in rows
                  if row.get("runningStatus") not in {None, 0})


def _own_resumable(work_dir: Path, running: list[str]) -> bool:
    if len(running) != 1:
        return False
    names = []
    for path in work_dir.glob("*/mc_run/retest_preflight.json"):
        try:
            value = _load(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if value.get("decision") == "PASS_RETEST_PREFLIGHT":
            names.append(value.get("project_name"))
    return running[0] in names


def tick(*, temporal_worker_dir: Path, output_dir: Path,
         worker_config_path: Path,
         listing_fn: Callable[..., list[dict]] = list_projects,
         robustness_fn: Callable[..., dict] = run_stage) -> dict[str, Any]:
    temporal_receipt_path = temporal_worker_dir.resolve() / "temporal_worker_receipt.json"
    if not temporal_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_TEMPORAL_VALIDATION",
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    temporal_receipt = _load(temporal_receipt_path)
    campaign_id = temporal_receipt.get("campaign_id")
    if temporal_receipt.get("decision") == "REJECT_TEMPORAL_VALIDATION":
        return {"schema_version": 1, "decision": "REJECT_TEMPORAL_VALIDATION",
                "campaign_id": campaign_id, "candidate_ids": [],
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    if temporal_receipt.get("decision") != "PASS_TEMPORAL_VALIDATION":
        raise ValueError("unsupported temporal worker decision")
    temporal_path = _verified(
        temporal_receipt.get("temporal_artifact_path"),
        temporal_receipt.get("temporal_artifact_sha256"), "temporal artifact")
    temporal = _load(temporal_path)
    if (temporal.get("stage") != "temporal_validation"
            or temporal.get("decision") != "PASS"
            or temporal.get("campaign_id") != campaign_id
            or temporal.get("holdout_accessed") is not False
            or temporal.get("candidate_ids") != temporal_receipt.get("candidate_ids")):
        raise ValueError("temporal artifact does not match worker receipt")
    cost_path = _verified(
        temporal.get("cost_model_path"), temporal.get("cost_model_sha256"),
        "frozen cost model", temporal_path.parent)
    costs = _load(cost_path)
    if costs.get("decision") != "PASS_COSTS_FROZEN" or costs.get("costs_frozen") is not True:
        raise ValueError("robustness requires frozen costs")
    max_leverage = venue_max_leverage(costs)
    methodology_path = _verified(
        temporal.get("methodology_path"), temporal.get("methodology_sha256"),
        "frozen temporal methodology", temporal_path.parent)
    config = _load(worker_config_path.resolve())
    projects_root = Path(str(config.get("host_projects_root", ""))).resolve()
    if not projects_root.is_dir():
        raise ValueError("SQCLI projects root missing")
    work_dir = projects_root / "ALQ4_RUNTIME" / str(campaign_id) / "robustness"
    output_dir = output_dir.resolve()
    artifact_path = output_dir / "05_robustness.json"
    receipt_path = output_dir / "robustness_worker_receipt.json"
    if receipt_path.is_file():
        result = _load(receipt_path)
        artifact = _verified(result.get("robustness_artifact_path"),
                             result.get("robustness_artifact_sha256"),
                             "robustness artifact")
        if (result.get("campaign_id") != campaign_id
                or artifact != artifact_path
                or result.get("decision") not in {
                    "PASS_ROBUSTNESS", "REJECT_ROBUSTNESS"}):
            raise ValueError("completed robustness worker receipt invalid")
        return result
    running = _running(listing_fn(config["base_url"]))
    if running and not _own_resumable(work_dir, running):
        return {"schema_version": 1, "decision": "WAITING_FOR_SQCLI_IDLE",
                "campaign_id": campaign_id, "running_projects": running,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    artifact = robustness_fn(
        campaign_id=campaign_id, temporal_artifact_path=temporal_path,
        methodology_path=methodology_path, cost_model_path=cost_path,
        work_dir=work_dir, host_projects_root=projects_root,
        artifact_path=artifact_path, venue_max_leverage=max_leverage)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise ValueError("robustness stage returned an invalid decision")
    result = {
        "schema_version": 1,
        "decision": ("PASS_ROBUSTNESS" if artifact["decision"] == "PASS"
                     else "REJECT_ROBUSTNESS"),
        "campaign_id": campaign_id, "candidate_ids": artifact.get("candidate_ids", []),
        "evaluated_candidate_ids": sorted(
            (artifact.get("evaluated_candidate_robustness_metrics") or {}).keys()),
        "robustness_artifact_path": str(artifact_path),
        "robustness_artifact_sha256": _sha(artifact_path),
        "temporal_artifact_path": str(temporal_path),
        "temporal_artifact_sha256": _sha(temporal_path),
        "venue_max_leverage": max_leverage,
        "overnight_leverage_semantics": "zero_means_no_stock_day_trading_override_for_forex",
        "holdout_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(receipt_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temporal-worker-dir", type=Path,
                        default=campaign / "temporal-worker")
    parser.add_argument("--output-dir", type=Path, default=campaign / "robustness-worker")
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    args = parser.parse_args()
    print(json.dumps(tick(
        temporal_worker_dir=args.temporal_worker_dir, output_dir=args.output_dir,
        worker_config_path=args.worker_config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
