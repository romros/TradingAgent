#!/usr/bin/env python3
"""Freeze a mature US500 preflight and execute its deterministic screen once."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lab.sq_bridge.us500_d1_market_preflight_v4 import compose, write_atomic
from lab.sq_bridge.us500_v4_screen_bootstrap import CAMPAIGN_ID, bootstrap


RECEIPT = "screen_trigger_receipt.json"
JOURNAL = "screen_trigger_journal.json"
RECEIPT_LABELS = ("coverage", "mapping", "canonical_source", "sq_resource", "costs")
ROOT = Path(__file__).parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _copy_exact(source: Path, destination: Path, expected: str) -> None:
    if destination.is_file():
        if _sha(destination) != expected:
            raise ValueError(f"frozen snapshot changed: {destination}")
        return
    if not source.is_file() or _sha(source) != expected:
        raise ValueError(f"source changed before snapshot: {source}")
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


def _resource_path(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (ROOT / path).resolve()


def _freeze_sq_resource(source_receipt: Path, destination: Path,
                        canonical_data: Path) -> None:
    value = _load(source_receipt)
    frozen = destination.parent
    dependencies = (
        ("commands", "path", "sha256", "sq_commands.txt"),
        ("roundtrip", "export_path", "export_sha256", "sq_export.csv"),
        ("roundtrip", "audit_path", "audit_sha256", "sq_audit.json"),
    )
    for section, path_key, hash_key, filename in dependencies:
        row = value.get(section) or {}
        original, target = _resource_path(row.get(path_key)), frozen / filename
        _copy_exact(original, target, row.get(hash_key))
        row[path_key] = str(target.resolve())
        row[hash_key] = _sha(target)
    value["source"]["path"] = str(canonical_data.resolve())
    value["source"]["sha256"] = _sha(canonical_data)
    value["upstream_receipt_sha256"] = _sha(source_receipt)
    if destination.is_file() and _load(destination) != value:
        raise ValueError("frozen SQ resource receipt changed")
    write_atomic(destination, value)


def _prepare(preflight_path: Path, source_path: Path,
             methodology_path: Path, output_dir: Path) -> dict[str, Any]:
    preflight = _load(preflight_path)
    if (preflight.get("decision") != "PASS"
            or preflight.get("campaign_id") != CAMPAIGN_ID
            or preflight.get("next_stage_authorized") != "hypothesis_screen"
            or preflight.get("canonical_source_sha256") != _sha(source_path)):
        raise ValueError("US500 preflight does not authorize a frozen screen")
    receipts = preflight.get("input_receipts") or {}
    labels = list(RECEIPT_LABELS)
    if "vix" in receipts:
        labels.append("vix")
    sources = {}
    for label in labels:
        row = receipts.get(label) or {}
        path, digest = Path(str(row.get("path", ""))), row.get("sha256")
        if not path.is_file() or not isinstance(digest, str) or _sha(path) != digest:
            raise ValueError(f"live preflight input invalid: {label}")
        sources[label] = {
            "source_path": str(path.resolve()), "sha256": digest,
            "snapshot_path": str((output_dir / "frozen" / f"{label}.json").resolve()),
        }
    for label, path, filename in (
            ("canonical_data", source_path, "canonical_data.csv"),
            ("methodology", methodology_path, "methodology.json")):
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"screen input missing: {label}")
        sources[label] = {
            "source_path": str(path), "sha256": _sha(path),
            "snapshot_path": str((output_dir / "frozen" / filename).resolve()),
        }
    return {
        "schema_version": 1, "phase": "PREPARED", "campaign_id": CAMPAIGN_ID,
        "live_preflight_path": str(preflight_path.resolve()),
        "live_preflight_sha256": _sha(preflight_path), "sources": sources,
        "sqcli_started": False, "paper_authorized": False,
        "live_authorized": False,
    }


def _resume(journal_path: Path, output_dir: Path) -> dict[str, Any]:
    journal = _load(journal_path)
    if (journal.get("schema_version") != 1
            or journal.get("campaign_id") != CAMPAIGN_ID
            or journal.get("phase") not in {"PREPARED", "SNAPSHOTTED"}
            or journal.get("sqcli_started") is not False):
        raise ValueError("invalid US500 screen journal")
    sources = journal.get("sources") or {}
    required = {*RECEIPT_LABELS, "canonical_data", "methodology"}
    if not required.issubset(sources) or set(sources) - required != {"vix"} and set(sources) != required:
        raise ValueError("US500 screen source inventory invalid")
    for label, row in sources.items():
        if label in {"canonical_source", "sq_resource"}:
            continue
        _copy_exact(Path(row["source_path"]), Path(row["snapshot_path"]),
                    row["sha256"])
    canonical_row = sources["canonical_source"]
    original_canonical = Path(canonical_row["source_path"])
    if _sha(original_canonical) != canonical_row["sha256"]:
        raise ValueError("canonical receipt changed before snapshot")
    frozen_canonical = _load(original_canonical)
    frozen_canonical["canonical_path"] = sources["canonical_data"]["snapshot_path"]
    frozen_canonical["canonical_sha256"] = sources["canonical_data"]["sha256"]
    frozen_canonical["upstream_receipt_sha256"] = canonical_row["sha256"]
    canonical_snapshot = Path(canonical_row["snapshot_path"])
    if canonical_snapshot.is_file() and _load(canonical_snapshot) != frozen_canonical:
        raise ValueError("frozen canonical receipt changed")
    write_atomic(canonical_snapshot, frozen_canonical)
    sq_resource_row = sources["sq_resource"]
    sq_resource_source = Path(sq_resource_row["source_path"])
    if _sha(sq_resource_source) != sq_resource_row["sha256"]:
        raise ValueError("SQ resource receipt changed before snapshot")
    _freeze_sq_resource(
        sq_resource_source, Path(sq_resource_row["snapshot_path"]),
        Path(sources["canonical_data"]["snapshot_path"]))

    frozen = output_dir / "frozen"
    config = {
        "schema_version": 1, "campaign_id": CAMPAIGN_ID,
        "ostium_pair_id": "SPX/USD",
        **{label: f"{label}.json" for label in RECEIPT_LABELS},
    }
    if "vix" in sources:
        config["vix"] = "vix.json"
    config_path = frozen / "preflight_config.json"
    if config_path.is_file() and _load(config_path) != config:
        raise ValueError("frozen US500 preflight config changed")
    write_atomic(config_path, config)
    preflight = compose(config_path)
    if preflight.get("decision") != "PASS":
        raise ValueError("frozen US500 inputs no longer compose a PASS")
    frozen_preflight = frozen / "market_preflight.json"
    if frozen_preflight.is_file() and _load(frozen_preflight) != preflight:
        raise ValueError("frozen US500 preflight changed")
    write_atomic(frozen_preflight, preflight)
    journal["phase"] = "SNAPSHOTTED"
    journal["frozen_preflight_path"] = str(frozen_preflight.resolve())
    journal["frozen_preflight_sha256"] = _sha(frozen_preflight)
    write_atomic(journal_path, journal)

    run_dir = output_dir / "run"
    result = bootstrap(
        preflight_path=frozen_preflight,
        source_path=Path(sources["canonical_data"]["snapshot_path"]),
        cost_model_path=Path(sources["costs"]["snapshot_path"]),
        methodology_path=Path(sources["methodology"]["snapshot_path"]),
        output_dir=run_dir)
    receipt = {
        "schema_version": 1,
        "decision": ("PASS_SCREEN_TRIGGER" if result["decision"]
                     == "PASS_SQ_BRANCHES_READY" else "REJECT_SCREEN_TRIGGER"),
        "campaign_id": CAMPAIGN_ID,
        "journal_path": str(journal_path.resolve()),
        "frozen_preflight_path": str(frozen_preflight.resolve()),
        "frozen_preflight_sha256": _sha(frozen_preflight),
        "bootstrap_path": str((run_dir / "bootstrap.json").resolve()),
        "bootstrap_sha256": _sha(run_dir / "bootstrap.json"),
        "selected_hypothesis_ids": result["selected_hypothesis_ids"],
        "sqcli_started": False, "paper_authorized": False,
        "live_authorized": False,
    }
    receipt_path = output_dir / RECEIPT
    write_atomic(receipt_path, receipt)
    journal["phase"] = "COMPLETED"
    journal["receipt_sha256"] = _sha(receipt_path)
    write_atomic(journal_path, journal)
    return receipt


def verify_completed(output_dir: Path) -> dict[str, Any]:
    receipt_path = output_dir.resolve() / RECEIPT
    receipt = _load(receipt_path)
    if (receipt.get("decision") not in {"PASS_SCREEN_TRIGGER", "REJECT_SCREEN_TRIGGER"}
            or receipt.get("campaign_id") != CAMPAIGN_ID
            or receipt.get("sqcli_started") is not False):
        raise ValueError("invalid completed US500 screen receipt")
    for label in ("frozen_preflight", "bootstrap"):
        path = Path(str(receipt.get(f"{label}_path", "")))
        if not path.is_file() or _sha(path) != receipt.get(f"{label}_sha256"):
            raise ValueError(f"completed US500 {label} changed")
    result = _load(Path(receipt["bootstrap_path"]))
    if (result.get("selected_hypothesis_ids") != receipt["selected_hypothesis_ids"]
            or result.get("sqcli_started") is not False):
        raise ValueError("completed US500 bootstrap identity mismatch")
    journal = _load(Path(str(receipt.get("journal_path", ""))))
    if (journal.get("phase") != "COMPLETED"
            or journal.get("receipt_sha256") != _sha(receipt_path)):
        raise ValueError("completed US500 journal invalid")
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
    write_atomic(journal_path, _prepare(
        preflight_path.resolve(), source_path.resolve(),
        methodology_path.resolve(), output_dir))
    return _resume(journal_path, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(trigger(
        preflight_path=args.preflight, source_path=args.source,
        methodology_path=args.methodology, output_dir=args.output_dir), indent=2))


if __name__ == "__main__":
    main()
