import copy
import json

import pytest

from lab.sq_bridge.noncrypto_exit_contract_v5 import CONTRACT, PREREG, verify


def test_all_18_preregistered_exits_have_exact_semantics():
    assert verify()["templates"] == 18


def test_missing_template_fails_closed(tmp_path):
    value = json.loads(CONTRACT.read_text())
    value["templates"].pop(next(iter(value["templates"])))
    path = tmp_path / "contract.json"; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="one-to-one"):
        verify(path, PREREG)


def test_manager_cannot_widen_stop(tmp_path):
    value = json.loads(CONTRACT.read_text())
    managed = next(item for item in value["templates"].values()
                   if item["manager"]["kind"] != "NONE")
    managed["manager"]["allow_widen"] = True
    path = tmp_path / "contract.json"; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="widen"):
        verify(path, PREREG)
