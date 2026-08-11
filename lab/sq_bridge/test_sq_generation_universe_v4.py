import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.sq_generation_universe_v4 import build_universe
from lab.sq_bridge.test_alquimia_retest import _fixture


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _branch(tmp_path, hypothesis, candidate=None, candidate_id="T"):
    root = tmp_path / hypothesis
    root.mkdir()
    artifact = root / "sq_generation.json"
    ids = [candidate_id] if candidate else []
    artifact.write_text(json.dumps({
        "stage": "sq_generation", "decision": "PASS" if ids else "REJECT",
        "campaign_id": "campaign", "holdout_accessed": False,
        "source_hypothesis_ids": [hypothesis], "candidate_ids": ids,
        "candidate_artifact_paths": ({candidate_id: str(candidate)} if candidate else {}),
        "candidate_artifact_hashes": ({candidate_id: _sha(candidate)} if candidate else {}),
    }))
    return artifact


def test_builds_complete_global_universe_and_keeps_reject_provenance(tmp_path):
    (tmp_path / "fixture").mkdir()
    _, candidate, _ = _fixture(tmp_path / "fixture")
    h1 = _branch(tmp_path, "h1", candidate)
    h2 = _branch(tmp_path, "h2")
    output = tmp_path / "combined/global_sq_generation.json"
    result = build_universe(
        campaign_id="campaign", generation_artifact_paths={"h2": h2, "h1": h1},
        output_path=output)
    assert result["decision"] == "PASS"
    assert result["candidate_ids"] == ["T"]
    assert result["candidate_source_hypothesis_ids"] == {"T": "h1"}
    assert result["source_hypothesis_ids"] == ["h1", "h2"]
    assert result["source_generation_artifacts"]["h2"]["decision"] == "REJECT"
    assert Path(output.parent / result["candidate_artifact_paths"]["T"]).resolve() == candidate.resolve()


def test_deduplicates_identical_candidate_but_rejects_identity_collision(tmp_path):
    (tmp_path / "fixture").mkdir()
    _, candidate, _ = _fixture(tmp_path / "fixture")
    h1 = _branch(tmp_path, "h1", candidate)
    h2 = _branch(tmp_path, "h2", candidate)
    result = build_universe(
        campaign_id="campaign", generation_artifact_paths={"h1": h1, "h2": h2},
        output_path=tmp_path / "same.json")
    assert result["candidate_ids"] == ["T"]

    (tmp_path / "other").mkdir()
    different = tmp_path / "other/candidate.sqx"
    shutil.copy2(candidate, different)
    with zipfile.ZipFile(different, "a") as archive:
        archive.comment = b"different but still a valid SQX"
    h3 = _branch(tmp_path, "h3", different)
    with pytest.raises(ValueError, match="identity collision"):
        build_universe(
            campaign_id="campaign", generation_artifact_paths={"h1": h1, "h3": h3},
            output_path=tmp_path / "collision.json")


def test_rejects_changed_branch_artifact_candidate_and_empty_global_universe(tmp_path):
    rejected = _branch(tmp_path, "h1")
    result = build_universe(
        campaign_id="campaign", generation_artifact_paths={"h1": rejected},
        output_path=tmp_path / "empty.json")
    assert result["decision"] == "REJECT"
    assert result["rejection_reason"] == "NO_SQ_CANDIDATES_IN_ANY_BRANCH"

    (tmp_path / "fixture").mkdir()
    _, candidate, _ = _fixture(tmp_path / "fixture")
    passed = _branch(tmp_path, "h2", candidate)
    value = json.loads(passed.read_text())
    value["candidate_artifact_hashes"]["T"] = "0" * 64
    passed.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="path/hash mismatch"):
        build_universe(
            campaign_id="campaign", generation_artifact_paths={"h2": passed},
            output_path=tmp_path / "tampered.json")
