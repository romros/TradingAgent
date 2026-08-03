import hashlib
import json

import pytest

from lab.sq_bridge.crypto_capitulation_reclaim_checkpoint import build


def write(path, value): path.write_text(json.dumps(value)); return path
def canonical(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def setup(tmp_path):
    family = {"family_id": "v19"}; digest = canonical(family); sources = {"BTCUSD": "x"}
    temporal = {"decision": "PASS_INTERNAL_NON_INDEPENDENT", "performance_promotion_authorized": False}
    discovery = {"config_sha256": digest, "source_sha256": sources, "stable_candidate_ids": ["x"],
        "topology_selected_representatives": [{"candidate_id": "x"}], "points_evaluated": 10, "point_gate_passes": 2}
    wf = {"config_sha256": digest, "source_sha256": sources, "decision": "REJECT_INTERNAL_WALK_FORWARD",
        "passing_candidate_ids": [], "independent_validation": False, "global_holdout_accessed": False,
        "performance_promotion_authorized": False, "results": [{"aggregate_metrics": {"stress": {"trades": 27, "profit_factor": 2}}, "positive_fold_ratio": .6}]}
    return tuple(write(tmp_path / name, value) for name, value in (("family", family), ("temporal", temporal), ("discovery", discovery), ("wf", wf)))


def test_checkpoint_accepts_non_independent_terminal_rejection(tmp_path):
    result = build(*setup(tmp_path))
    assert result["decision"] == "REJECT_CRYPTO_CAPITULATION_RECLAIM_INTERNAL_WF"
    assert result["performance_promotion_authorized"] is False


def test_checkpoint_rejects_holdout_access(tmp_path):
    paths = setup(tmp_path); wf = json.loads(paths[3].read_text()); wf["global_holdout_accessed"] = True; paths[3].write_text(json.dumps(wf))
    with pytest.raises(ValueError, match="INDEPENDENCE_OR_HOLDOUT_CONTRACT_BROKEN"):
        build(*paths)
