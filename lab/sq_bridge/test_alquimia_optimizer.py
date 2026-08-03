import json

import pytest

from lab.sq_bridge.alquimia_optimizer import generate


def _family(tmp_path, **overrides):
    value = {
        "legacy_quantitative_inputs": [],
        "holdout_release_authorized": False,
    }
    value.update(overrides)
    path = tmp_path / "family.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_optimizer_rejects_legacy_quantitative_inputs_before_loading_scaffold(tmp_path):
    with pytest.raises(ValueError, match="LEGACY_QUANTITATIVE_INPUTS_FORBIDDEN"):
        generate(tmp_path/"missing.cfx", tmp_path/"out.cfx", "p",
                 _family(tmp_path, legacy_quantitative_inputs=["old"]),
                 tmp_path/"seed.sqx", tmp_path/"resource.cfx", "XAU", "H4")


def test_optimizer_refuses_released_holdout_and_unbounded_budget(tmp_path):
    with pytest.raises(ValueError, match="HOLDOUT_MUST_REMAIN_SEALED"):
        generate(tmp_path/"missing.cfx", tmp_path/"out.cfx", "p",
                 _family(tmp_path, holdout_release_authorized=True),
                 tmp_path/"seed.sqx", tmp_path/"resource.cfx", "XAU", "H4")
    with pytest.raises(ValueError, match="OPTIMIZATION_BUDGET_INVALID"):
        generate(tmp_path/"missing.cfx", tmp_path/"out.cfx", "p", _family(tmp_path),
                 tmp_path/"seed.sqx", tmp_path/"resource.cfx", "XAU", "H4",
                 max_optimizations=5001)
