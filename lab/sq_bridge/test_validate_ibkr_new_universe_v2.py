import copy
import json
from pathlib import Path

import pytest

from lab.sq_bridge.validate_ibkr_new_universe_v2 import REGISTRY, validate


def _write(tmp_path: Path, doc: dict) -> Path:
    target = tmp_path / "universe.json"
    target.write_text(json.dumps(doc), encoding="utf-8")
    return target


def test_canonical_universe_passes() -> None:
    result = validate()
    assert result["status"] == "PASS"
    assert result["candidate_count"] == 13
    assert result["priority_1_count"] == 4
    assert result["explicitly_reauthorized_count"] == 4


def test_old_symbol_is_rejected(tmp_path: Path) -> None:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    changed = copy.deepcopy(doc)
    changed["candidates"][0]["symbol"] = "SPY"
    with pytest.raises(ValueError, match="old/Ostium"):
        validate(_write(tmp_path, changed))


def test_explicit_clean_slate_reauthorization_is_accepted() -> None:
    result = validate()
    assert result["explicitly_reauthorized_count"] == 4


def test_unknown_data_symbol_is_rejected(tmp_path: Path) -> None:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    changed = copy.deepcopy(doc)
    changed["candidates"][0]["sq_data_symbol"] = "NOT_IN_CATALOG"
    with pytest.raises(ValueError, match="missing from frozen"):
        validate(_write(tmp_path, changed))
