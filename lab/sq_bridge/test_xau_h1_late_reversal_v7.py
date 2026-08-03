import json

from lab.sq_bridge.xau_h1_late_reversal_v7 import validate


def test_rejects_holdout_release_before_loading_data(tmp_path):
    family={"legacy_quantitative_inputs":[],"holdout_release_authorized":True}
    p=tmp_path/"family.json"; p.write_text(json.dumps(family))
    try:
        validate(tmp_path,p)
    except ValueError as error:
        assert str(error)=="HOLDOUT_MUST_REMAIN_SEALED"
    else:
        raise AssertionError("expected sealed holdout rejection")
