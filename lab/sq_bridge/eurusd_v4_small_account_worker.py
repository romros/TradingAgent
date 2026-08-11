#!/usr/bin/env python3
"""Resume passing EURUSD robustness through exact 200-USDC sizing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candles
from lab.sq_bridge.sq_small_account_stage_v4 import run_stage
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


def tick(*, robustness_worker_dir: Path, output_dir: Path,
         worker_config_path: Path,
         small_account_fn: Callable[..., dict] = run_stage) -> dict[str, Any]:
    robustness_receipt_path = (
        robustness_worker_dir.resolve() / "robustness_worker_receipt.json")
    if not robustness_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_ROBUSTNESS",
                "paper_authorized": False, "live_authorized": False}
    receipt = _load(robustness_receipt_path)
    campaign_id = receipt.get("campaign_id")
    if receipt.get("decision") == "REJECT_ROBUSTNESS":
        return {"schema_version": 1, "decision": "REJECT_ROBUSTNESS",
                "campaign_id": campaign_id, "candidate_ids": [],
                "paper_authorized": False, "live_authorized": False}
    if receipt.get("decision") != "PASS_ROBUSTNESS":
        raise ValueError("unsupported robustness worker decision")
    robustness_path = _verified(
        receipt.get("robustness_artifact_path"),
        receipt.get("robustness_artifact_sha256"), "robustness artifact")
    robustness = _load(robustness_path)
    if (robustness.get("stage") != "robustness"
            or robustness.get("decision") != "PASS"
            or robustness.get("campaign_id") != campaign_id
            or robustness.get("holdout_accessed") is not False
            or robustness.get("candidate_ids") != receipt.get("candidate_ids")):
        raise ValueError("robustness artifact does not match worker receipt")
    cost_path = _verified(
        robustness.get("cost_model_path"), robustness.get("cost_model_sha256"),
        "frozen cost model", robustness_path.parent)
    methodology_path = _verified(
        robustness.get("methodology_path"), robustness.get("methodology_sha256"),
        "frozen robustness methodology", robustness_path.parent)
    config_path = worker_config_path.resolve()
    config = _load(config_path)
    candle_contract_path = _verified(
        config.get("small_account_candle_contract_path"),
        config.get("small_account_candle_contract_sha256"),
        "small-account candle contract", config_path.parent)
    candle_contract = _load(candle_contract_path)
    if verify_candles(candle_contract) != candle_contract:
        raise ValueError("small-account candle contract not reproducible")
    if (candle_contract.get("decision") != "PASS_CANDLE_PARITY"
            or candle_contract.get("symbol") != "EURUSD"
            or candle_contract.get("timeframe") != "D1"
            or candle_contract.get("performance_accessed") is not False):
        raise ValueError("small-account EURUSD candle contract invalid")
    candles_path = _verified(
        candle_contract.get("sq_candles_path"),
        candle_contract.get("sq_candles_sha256"), "SQ sizing candles")

    output_dir = output_dir.resolve()
    artifact_path = output_dir / "06_small_account_economics.json"
    final_path = output_dir / "small_account_worker_receipt.json"
    if final_path.is_file():
        result = _load(final_path)
        artifact = _verified(result.get("small_account_artifact_path"),
                             result.get("small_account_artifact_sha256"),
                             "small-account artifact")
        if (result.get("campaign_id") != campaign_id
                or artifact != artifact_path
                or result.get("decision") not in {
                    "PASS_SMALL_ACCOUNT", "REJECT_SMALL_ACCOUNT"}):
            raise ValueError("completed small-account worker receipt invalid")
        return result
    artifact = small_account_fn(
        campaign_id=campaign_id, robustness_artifact_path=robustness_path,
        methodology_path=methodology_path, cost_model_path=cost_path,
        candles_path=candles_path,
        candle_timezone=candle_contract["sq_timezone"],
        candle_contract_path=candle_contract_path,
        work_dir=output_dir / "traces", artifact_path=artifact_path)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise ValueError("small-account stage returned an invalid decision")
    result = {
        "schema_version": 1,
        "decision": ("PASS_SMALL_ACCOUNT" if artifact["decision"] == "PASS"
                     else "REJECT_SMALL_ACCOUNT"),
        "campaign_id": campaign_id, "candidate_ids": artifact.get("candidate_ids", []),
        "evaluated_candidate_ids": sorted(
            (artifact.get("evaluated_candidate_small_account_metrics") or {}).keys()),
        "small_account_artifact_path": str(artifact_path),
        "small_account_artifact_sha256": _sha(artifact_path),
        "robustness_artifact_path": str(robustness_path),
        "robustness_artifact_sha256": _sha(robustness_path),
        "capital_usdc": 200,
        "selected_leverage": artifact.get("selected_leverage"),
        "holdout_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robustness-worker-dir", type=Path,
                        default=campaign / "robustness-worker")
    parser.add_argument("--output-dir", type=Path,
                        default=campaign / "small-account-worker")
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    args = parser.parse_args()
    print(json.dumps(tick(
        robustness_worker_dir=args.robustness_worker_dir,
        output_dir=args.output_dir, worker_config_path=args.worker_config),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
