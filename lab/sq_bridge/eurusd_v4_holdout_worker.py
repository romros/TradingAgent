#!/usr/bin/env python3
"""Release the sole EURUSD final holdout only after complete frozen coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candles
from lab.sq_bridge.sq_final_holdout_stage_v4 import run_stage
from lab.sq_bridge.sqcli_transport import list_projects_with_status
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


def _running(rows: list[dict]) -> list[str]:
    return sorted(str(row.get("projectName")) for row in rows
                  if row.get("runningStatus") not in {None, 0})


def _own_resumable(work_dir: Path, running: list[str]) -> bool:
    if len(running) != 1:
        return False
    names = []
    for path in work_dir.glob("*/supervised/retest_preflight.json"):
        try:
            value = _load(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if value.get("decision") == "PASS_RETEST_PREFLIGHT":
            names.append(value.get("project_name"))
    return running[0] in names


def tick(*, small_account_worker_dir: Path, output_dir: Path,
         worker_config_path: Path,
         listing_fn: Callable[..., list[dict]] = list_projects_with_status,
         holdout_fn: Callable[..., dict] = run_stage) -> dict[str, Any]:
    sizing_receipt_path = (
        small_account_worker_dir.resolve() / "small_account_worker_receipt.json")
    if not sizing_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_SMALL_ACCOUNT",
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    sizing_receipt = _load(sizing_receipt_path)
    campaign_id = sizing_receipt.get("campaign_id")
    if sizing_receipt.get("decision") == "REJECT_SMALL_ACCOUNT":
        return {"schema_version": 1, "decision": "REJECT_SMALL_ACCOUNT",
                "campaign_id": campaign_id, "candidate_ids": [],
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    if sizing_receipt.get("decision") != "PASS_SMALL_ACCOUNT":
        raise ValueError("unsupported small-account worker decision")
    sizing_path = _verified(
        sizing_receipt.get("small_account_artifact_path"),
        sizing_receipt.get("small_account_artifact_sha256"),
        "small-account artifact")
    sizing = _load(sizing_path)
    if (sizing.get("stage") != "small_account_economics"
            or sizing.get("decision") != "PASS"
            or sizing.get("campaign_id") != campaign_id
            or sizing.get("holdout_accessed") is not False
            or sizing.get("candidate_ids") != sizing_receipt.get("candidate_ids")
            or len(sizing.get("candidate_ids") or []) != 1):
        raise ValueError("small-account artifact does not match worker receipt")
    cost_path = _verified(
        sizing.get("cost_model_path"), sizing.get("cost_model_sha256"),
        "frozen cost model", sizing_path.parent)
    methodology_path = _verified(
        sizing.get("methodology_path"), sizing.get("methodology_sha256"),
        "frozen sizing methodology", sizing_path.parent)
    candidate_id = sizing["candidate_ids"][0]
    trace_path = _verified(
        (sizing.get("small_account_trace_paths") or {}).get(candidate_id),
        (sizing.get("small_account_trace_sha256") or {}).get(candidate_id),
        "selected small-account trace", sizing_path.parent)
    small_trace = _load(trace_path)
    temporal_trace_path = _verified(
        small_trace.get("temporal_trace_path"), small_trace.get("temporal_trace_sha256"),
        "selected temporal trace", trace_path.parent)
    temporal_trace = _load(temporal_trace_path)
    temporal_contract_path = _verified(
        temporal_trace.get("temporal_contract_path"),
        temporal_trace.get("temporal_contract_sha256"),
        "temporal split contract", temporal_trace_path.parent)
    temporal_contract = _load(temporal_contract_path)
    holdout_to = ((temporal_contract.get("segments") or {})
                  .get("final_holdout", {}).get("to"))
    if not isinstance(holdout_to, str):
        raise ValueError("final holdout boundary missing")

    config_path = worker_config_path.resolve()
    config = _load(config_path)
    portfolio_value = config.get("portfolio_artifact_path")
    if not isinstance(portfolio_value, str) or not portfolio_value:
        raise ValueError("portfolio construction path missing")
    portfolio_path = Path(portfolio_value)
    portfolio_path = (portfolio_path.resolve() if portfolio_path.is_absolute()
                      else (config_path.parent / portfolio_path).resolve())
    if not portfolio_path.is_file():
        return {"schema_version": 1,
                "decision": "WAITING_FOR_PORTFOLIO_CONSTRUCTION",
                "campaign_id": campaign_id, "candidate_ids": [candidate_id],
                "holdout_accessed": False, "holdout_evaluation_count": 0,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    portfolio = _load(portfolio_path)
    if portfolio.get("decision") == "REJECT":
        return {"schema_version": 1, "decision": "REJECT_PORTFOLIO_CONSTRUCTION",
                "campaign_id": campaign_id, "candidate_ids": [],
                "holdout_accessed": False, "holdout_evaluation_count": 0,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    portfolio_source = (portfolio.get("source_receipts") or {}).get(candidate_id)
    if (portfolio.get("stage") != "portfolio_construction"
            or portfolio.get("decision") != "PASS"
            or portfolio.get("holdout_accessed") is not False
            or candidate_id not in (portfolio.get("candidate_ids") or [])
            or not isinstance(portfolio_source, dict)
            or portfolio_source.get("campaign_id") != campaign_id
            or Path(str(portfolio_source.get("artifact_path", ""))).resolve()
                != sizing_path
            or portfolio_source.get("artifact_sha256") != _sha(sizing_path)):
        raise ValueError("portfolio construction does not authorize this candidate")
    candle_contract_path = _verified(
        config.get("small_account_candle_contract_path"),
        config.get("small_account_candle_contract_sha256"),
        "holdout candle contract", config_path.parent)
    candle_contract = _load(candle_contract_path)
    if verify_candles(candle_contract) != candle_contract:
        raise ValueError("holdout candle contract not reproducible")
    covered_to = str(candle_contract.get("last_common_timestamp_utc", ""))[:10]
    if covered_to < holdout_to:
        return {"schema_version": 1,
                "decision": "WAITING_FOR_HOLDOUT_CANDLE_COVERAGE",
                "campaign_id": campaign_id, "candidate_ids": [candidate_id],
                "required_through": holdout_to, "available_through": covered_to or None,
                "holdout_accessed": False, "holdout_evaluation_count": 0,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    candles_path = _verified(
        candle_contract.get("sq_candles_path"),
        candle_contract.get("sq_candles_sha256"), "holdout SQ candles")
    projects_root = Path(str(config.get("host_projects_root", ""))).resolve()
    if not projects_root.is_dir():
        raise ValueError("SQCLI projects root missing")
    work_dir = projects_root / "ALQ4_RUNTIME" / str(campaign_id) / "holdout"
    output_dir = output_dir.resolve()
    artifact_path = output_dir / "07_final_holdout_validation.json"
    final_path = output_dir / "holdout_worker_receipt.json"
    if final_path.is_file():
        result = _load(final_path)
        artifact = _verified(result.get("holdout_artifact_path"),
                             result.get("holdout_artifact_sha256"),
                             "final holdout artifact")
        if (result.get("campaign_id") != campaign_id
                or artifact != artifact_path
                or result.get("decision") not in {
                    "PASS_FINAL_HOLDOUT", "REJECT_FINAL_HOLDOUT"}):
            raise ValueError("completed holdout worker receipt invalid")
        return result
    running = _running(listing_fn(config["base_url"]))
    if running and not _own_resumable(work_dir, running):
        return {"schema_version": 1, "decision": "WAITING_FOR_SQCLI_IDLE",
                "campaign_id": campaign_id, "running_projects": running,
                "holdout_accessed": False, "holdout_evaluation_count": 0,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    artifact = holdout_fn(
        campaign_id=campaign_id, small_account_artifact_path=sizing_path,
        temporal_contract_path=temporal_contract_path, cost_model_path=cost_path,
        candles_path=candles_path, candle_timezone=candle_contract["sq_timezone"],
        candle_contract_path=candle_contract_path, source_timezone="Etc/UTC",
        work_dir=work_dir, projects_root=projects_root,
        artifact_path=artifact_path, methodology_path=methodology_path)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise ValueError("holdout stage returned an invalid decision")
    result = {
        "schema_version": 1,
        "decision": ("PASS_FINAL_HOLDOUT" if artifact["decision"] == "PASS"
                     else "REJECT_FINAL_HOLDOUT"),
        "campaign_id": campaign_id, "candidate_ids": [candidate_id],
        "holdout_artifact_path": str(artifact_path),
        "holdout_artifact_sha256": _sha(artifact_path),
        "portfolio_artifact_path": str(portfolio_path),
        "portfolio_artifact_sha256": _sha(portfolio_path),
        "holdout_accessed": True, "holdout_evaluation_count": 1,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small-account-worker-dir", type=Path,
                        default=campaign / "small-account-worker")
    parser.add_argument("--output-dir", type=Path, default=campaign / "holdout-worker")
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    args = parser.parse_args()
    print(json.dumps(tick(
        small_account_worker_dir=args.small_account_worker_dir,
        output_dir=args.output_dir, worker_config_path=args.worker_config),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
