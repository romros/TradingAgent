#!/usr/bin/env python3
"""Freeze a mature EURUSD preflight and run its deterministic screen once."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lab.sq_bridge.evidence_chain import verify as verify_chain
from lab.sq_bridge.eurusd_d1_market_preflight_v4 import compose
from lab.sq_bridge.eurusd_v4_screen_bootstrap import bootstrap
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


RECEIPT = "screen_trigger_receipt.json"
JOURNAL = "screen_trigger_journal.json"
SNAPSHOT_LABELS = ("coverage", "mapping", "sq_resource", "costs")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _copy_atomic(source: Path, destination: Path, expected_sha256: str) -> None:
    if destination.is_file():
        if _sha(destination) != expected_sha256:
            raise ValueError(f"frozen snapshot changed: {destination}")
        return
    if _sha(source) != expected_sha256:
        raise ValueError(f"source changed before it could be frozen: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _validate_preflight(path: Path, methodology_path: Path) -> dict[str, Any]:
    preflight, methodology = _load(path), _load(methodology_path)
    campaign_id = preflight.get("campaign_id")
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(path.resolve())}
    errors = validate_stage_artifact(
        "market_preflight", preflight, receipt, methodology,
        campaign_id, "alquimia_native")
    if (preflight.get("decision") != "PASS"
            or preflight.get("next_stage_authorized") != "hypothesis_screen"
            or errors):
        raise ValueError(f"preflight does not authorize screen: {errors}")
    return preflight


def _snapshot_plan(preflight_path: Path, source_path: Path,
                   methodology_path: Path, output_dir: Path) -> dict[str, Any]:
    preflight = _validate_preflight(preflight_path, methodology_path)
    sources: dict[str, dict[str, str]] = {}
    receipts = preflight.get("input_receipts") or {}
    for label in SNAPSHOT_LABELS:
        receipt = receipts.get(label) or {}
        path = Path(str(receipt.get("path", ""))).resolve()
        digest = receipt.get("sha256")
        if (not path.is_file() or not isinstance(digest, str)
                or _sha(path) != digest):
            raise ValueError(f"live preflight input invalid: {label}")
        sources[label] = {"source_path": str(path), "sha256": digest,
                          "snapshot_path": str((output_dir / "frozen" /
                                                f"{label}.json").resolve())}
    for label, path in (("canonical_source", source_path),
                        ("methodology", methodology_path)):
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"screen input missing: {label}")
        suffix = ".csv" if label == "canonical_source" else ".json"
        sources[label] = {"source_path": str(path), "sha256": _sha(path),
                          "snapshot_path": str((output_dir / "frozen" /
                                                f"{label}{suffix}").resolve())}
    return {
        "schema_version": 1, "phase": "PREPARED",
        "campaign_id": preflight["campaign_id"],
        "live_preflight_path": str(preflight_path.resolve()),
        "live_preflight_sha256": _sha(preflight_path),
        "sources": sources, "sqcli_started": False,
        "paper_authorized": False, "live_authorized": False,
    }


def _resume(journal_path: Path, output_dir: Path) -> dict[str, Any]:
    journal = _load(journal_path)
    if (journal.get("schema_version") != 1
            or journal.get("phase") not in {"PREPARED", "SNAPSHOTTED"}
            or journal.get("sqcli_started") is not False):
        raise ValueError("invalid or terminal screen trigger journal")
    sources = journal.get("sources")
    if not isinstance(sources, dict) or set(sources) != {
            *SNAPSHOT_LABELS, "canonical_source", "methodology"}:
        raise ValueError("screen trigger source inventory invalid")
    for value in sources.values():
        _copy_atomic(Path(value["source_path"]), Path(value["snapshot_path"]),
                     value["sha256"])

    frozen = output_dir / "frozen"
    config_path = frozen / "preflight_config.json"
    config = {
        "schema_version": 1, "preflight_composer": "eurusd_d1_v4",
        "campaign_id": journal["campaign_id"], "ostium_pair_id": "EUR/USD",
        **{label: f"{label}.json" for label in SNAPSHOT_LABELS},
    }
    if config_path.exists() and _load(config_path) != config:
        raise ValueError("frozen preflight config changed")
    write_atomic(config_path, config)
    frozen_preflight_path = frozen / "market_preflight.json"
    frozen_preflight = compose(config_path)
    if frozen_preflight.get("decision") != "PASS":
        raise ValueError("frozen inputs no longer compose a PASS preflight")
    if frozen_preflight_path.exists() and _load(frozen_preflight_path) != frozen_preflight:
        raise ValueError("frozen preflight changed")
    write_atomic(frozen_preflight_path, frozen_preflight)
    journal["phase"] = "SNAPSHOTTED"
    journal["frozen_preflight_path"] = str(frozen_preflight_path.resolve())
    journal["frozen_preflight_sha256"] = _sha(frozen_preflight_path)
    write_atomic(journal_path, journal)

    run_dir = output_dir / "run"
    result = bootstrap(
        preflight_path=frozen_preflight_path,
        source_path=Path(sources["canonical_source"]["snapshot_path"]),
        cost_model_path=Path(sources["costs"]["snapshot_path"]),
        methodology_path=Path(sources["methodology"]["snapshot_path"]),
        output_dir=run_dir)
    receipt = {
        "schema_version": 1,
        "decision": ("PASS_SCREEN_TRIGGER" if result["decision"]
                     == "PASS_SQ_BRANCHES_READY" else "REJECT_SCREEN_TRIGGER"),
        "campaign_id": journal["campaign_id"],
        "journal_path": str(journal_path.resolve()),
        "journal_sha256_before_completion": _sha(journal_path),
        "frozen_preflight_path": str(frozen_preflight_path.resolve()),
        "frozen_preflight_sha256": _sha(frozen_preflight_path),
        "methodology_path": sources["methodology"]["snapshot_path"],
        "methodology_sha256": sources["methodology"]["sha256"],
        "bootstrap_path": str((run_dir / "bootstrap.json").resolve()),
        "bootstrap_sha256": _sha(run_dir / "bootstrap.json"),
        "selected_hypothesis_ids": result["selected_hypothesis_ids"],
        "sqcli_started": False, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(output_dir / RECEIPT, receipt)
    journal["phase"] = "COMPLETED"
    journal["receipt_sha256"] = _sha(output_dir / RECEIPT)
    write_atomic(journal_path, journal)
    return receipt


def verify_completed(output_dir: Path) -> dict[str, Any]:
    receipt_path = output_dir.resolve() / RECEIPT
    receipt = _load(receipt_path)
    if receipt.get("decision") not in {"PASS_SCREEN_TRIGGER", "REJECT_SCREEN_TRIGGER"}:
        raise ValueError("invalid screen trigger decision")
    methodology_path = Path(str(receipt.get("methodology_path", "")))
    preflight_path = Path(str(receipt.get("frozen_preflight_path", "")))
    bootstrap_path = Path(str(receipt.get("bootstrap_path", "")))
    if (not methodology_path.is_file()
            or _sha(methodology_path) != receipt.get("methodology_sha256")
            or not preflight_path.is_file()
            or _sha(preflight_path) != receipt.get("frozen_preflight_sha256")
            or not bootstrap_path.is_file()
            or _sha(bootstrap_path) != receipt.get("bootstrap_sha256")):
        raise ValueError("completed screen trigger source hash mismatch")
    _validate_preflight(preflight_path, methodology_path)
    result = _load(bootstrap_path)
    selected = result.get("selected_hypothesis_ids")
    if (selected != receipt.get("selected_hypothesis_ids")
            or result.get("sqcli_started") is not False
            or set((result.get("branches") or {})) != set(selected or [])
            or result.get("preflight_sha256") != _sha(preflight_path)):
        raise ValueError("completed bootstrap identity mismatch")
    methodology = _load(methodology_path)
    trace_path = Path(str(result.get("trace_path", "")))
    screen_path = Path(str(result.get("screen_path", "")))
    if (not trace_path.is_file() or _sha(trace_path) != result.get("trace_sha256")
            or not screen_path.is_file()
            or _sha(screen_path) != result.get("screen_sha256")):
        raise ValueError("completed screen source hash mismatch")
    screen = _load(screen_path)
    screen_decision = "PASS" if selected else "REJECT"
    screen_receipt = {
        "decision": screen_decision, "candidate_ids": [],
        "holdout_accessed": False, "artifact": str(screen_path),
    }
    screen_errors = validate_stage_artifact(
        "hypothesis_screen", screen, screen_receipt, methodology,
        receipt.get("campaign_id"), "alquimia_native")
    if screen_errors:
        raise ValueError(f"completed screen contract invalid: {screen_errors}")
    for hypothesis_id, branch in (result.get("branches") or {}).items():
        chain_path = Path(branch["chain_path"])
        if _sha(chain_path) != branch["chain_sha256"]:
            raise ValueError(f"branch chain changed: {hypothesis_id}")
        verification = verify_chain(_load(chain_path), methodology_path)
        if (not verification["valid"] or not verification["promotable"]
                or verification["next_stage"] != "sq_generation"):
            raise ValueError(f"branch no longer promotable: {hypothesis_id}")
        plan_path = Path(branch["generation_plan_path"])
        if _sha(plan_path) != branch["generation_plan_sha256"]:
            raise ValueError(f"branch plan changed: {hypothesis_id}")
    expected = "PASS_SCREEN_TRIGGER" if selected else "REJECT_SCREEN_TRIGGER"
    if receipt["decision"] != expected:
        raise ValueError("screen trigger decision does not match bootstrap")
    journal = _load(Path(str(receipt.get("journal_path", ""))))
    if (journal.get("phase") != "COMPLETED"
            or journal.get("receipt_sha256") != _sha(receipt_path)):
        raise ValueError("screen trigger completion journal invalid")
    return receipt


def trigger(*, preflight_path: Path, source_path: Path,
            methodology_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    receipt_path, journal_path = output_dir / RECEIPT, output_dir / JOURNAL
    if receipt_path.is_file():
        return verify_completed(output_dir)
    if journal_path.is_file():
        return _resume(journal_path, output_dir)
    preflight = _load(preflight_path.resolve())
    if preflight.get("decision") != "PASS":
        return {
            "schema_version": 1, "decision": "WAITING_FOR_MARKET_PREFLIGHT",
            "campaign_id": preflight.get("campaign_id"),
            "blocking_reasons": preflight.get("blocking_reasons", []),
            "sqcli_started": False, "paper_authorized": False,
            "live_authorized": False,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    journal = _snapshot_plan(
        preflight_path.resolve(), source_path.resolve(),
        methodology_path.resolve(), output_dir)
    write_atomic(journal_path, journal)
    return _resume(journal_path, output_dir)


def main() -> None:
    root = Path(__file__).parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output-dir", type=Path,
                        default=root / "data" / "alquimia_v4" /
                        "eurusd-d1-alquimia-v4" / "screen-bootstrap")
    args = parser.parse_args()
    result = trigger(preflight_path=args.preflight, source_path=args.source,
                     methodology_path=args.methodology, output_dir=args.output_dir)
    print(json.dumps({key: result.get(key) for key in (
        "decision", "campaign_id", "selected_hypothesis_ids",
        "blocking_reasons", "sqcli_started")}, indent=2))


if __name__ == "__main__":
    main()
