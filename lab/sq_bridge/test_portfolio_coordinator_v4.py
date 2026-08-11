import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.portfolio_coordinator_v4 import tick


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registry(tmp_path: Path, campaigns: list[dict], *, closed: bool) -> Path:
    methodology = _write(tmp_path / "methodology.json", {"version": 4})
    return _write(tmp_path / "registry.json", {
        "schema_version": 1, "portfolio_id": "portfolio-v4",
        "registration_closed": closed,
        "methodology_path": str(methodology),
        "methodology_sha256": _sha(methodology), "campaigns": campaigns})


def _campaign(tmp_path: Path, campaign_id: str, decisions: list[str]) -> dict:
    root = tmp_path / campaign_id
    names = [
        "sq-worker/worker_receipt.json",
        "temporal-worker/temporal_worker_receipt.json",
        "robustness-worker/robustness_worker_receipt.json",
        "small-account-worker/small_account_worker_receipt.json",
    ]
    for name, decision in zip(names, decisions):
        receipt = {"campaign_id": campaign_id, "decision": decision}
        if decision == "PASS_SMALL_ACCOUNT":
            artifact = _write(root / "small-account-worker/artifact.json", {
                "stage": "small_account_economics", "decision": "PASS",
                "campaign_id": campaign_id, "candidate_ids": [f"{campaign_id}-C"],
                "holdout_accessed": False})
            receipt.update({"small_account_artifact_path": str(artifact),
                            "small_account_artifact_sha256": _sha(artifact)})
        _write(root / name, receipt)
    return {"campaign_id": campaign_id, "campaign_root": str(root)}


def test_open_registry_never_constructs_partial_portfolio(tmp_path):
    row = _campaign(tmp_path, "campaign-a", [
        "PASS_SQ_GENERATION_ORCHESTRATED", "PASS_TEMPORAL_VALIDATION",
        "PASS_ROBUSTNESS", "PASS_SMALL_ACCOUNT"])
    called = []
    result = tick(registry_path=_registry(tmp_path, [row], closed=False),
                  output_dir=tmp_path / "out",
                  portfolio_fn=lambda **kwargs: called.append(kwargs),
                  hypothesis_fn=lambda artifact, path, candidate: "h-a")
    assert result["decision"] == "WAITING_FOR_REGISTRATION_CLOSE"
    assert result["passing_branch_count"] == 1
    assert not called
    assert not (tmp_path / "out/portfolio_manifest.json").exists()


def test_closed_registry_waits_for_every_registered_campaign(tmp_path):
    rows = [
        _campaign(tmp_path, "campaign-a", ["REJECT_NO_SQ_CANDIDATES"]),
        {"campaign_id": "campaign-b", "campaign_root": str(tmp_path / "missing")},
    ]
    result = tick(registry_path=_registry(tmp_path, rows, closed=True),
                  output_dir=tmp_path / "out")
    assert result["decision"] == "WAITING_FOR_REGISTERED_CAMPAIGNS"
    assert result["rejected_campaign_ids"] == ["campaign-a"]
    assert result["pending_campaign_ids"] == ["campaign-b"]


def test_all_terminal_campaigns_are_frozen_before_portfolio_build(tmp_path):
    rows = [
        _campaign(tmp_path, "campaign-a", ["REJECT_NO_SQ_CANDIDATES"]),
        _campaign(tmp_path, "campaign-b", [
            "PASS_SQ_GENERATION_ORCHESTRATED", "PASS_TEMPORAL_VALIDATION",
            "PASS_ROBUSTNESS", "PASS_SMALL_ACCOUNT"]),
    ]

    def portfolio(**kwargs):
        manifest = json.loads(kwargs["manifest_path"].read_text())
        assert manifest["registered_campaign_ids"] == ["campaign-a", "campaign-b"]
        assert set(manifest["terminal_campaign_receipts"]) == {
            "campaign-a", "campaign-b"}
        assert [row["campaign_id"] for row in manifest["small_account_branches"]] == [
            "campaign-b"]
        artifact = {"decision": "REJECT", "candidate_ids": []}
        _write(kwargs["output_path"], artifact)
        return artifact

    result = tick(registry_path=_registry(tmp_path, rows, closed=True),
                  output_dir=tmp_path / "out", portfolio_fn=portfolio,
                  hypothesis_fn=lambda artifact, path, candidate: "h-b")
    assert result["decision"] == "REJECT_PORTFOLIO_CONSTRUCTION"
    assert result["rejected_campaign_ids"] == ["campaign-a"]
    assert result["passing_branch_count"] == 1


def test_receipts_after_terminal_rejection_are_rejected(tmp_path):
    row = _campaign(tmp_path, "campaign-a", [
        "REJECT_NO_SQ_CANDIDATES", "PASS_TEMPORAL_VALIDATION"])
    with pytest.raises(ValueError, match="after terminal rejection"):
        tick(registry_path=_registry(tmp_path, [row], closed=True),
             output_dir=tmp_path / "out")


def test_registry_requires_unique_sorted_campaign_ids(tmp_path):
    rows = [
        {"campaign_id": "b", "campaign_root": str(tmp_path / "b")},
        {"campaign_id": "a", "campaign_root": str(tmp_path / "a")},
    ]
    with pytest.raises(ValueError, match="unique and sorted"):
        tick(registry_path=_registry(tmp_path, rows, closed=False),
             output_dir=tmp_path / "out")
