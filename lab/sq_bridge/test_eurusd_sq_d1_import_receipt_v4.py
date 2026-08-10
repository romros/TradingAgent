from lab.sq_bridge.eurusd_sq_d1_import_receipt_v4 import EXPECTED, evaluate


def source():
    return {"decision": "PASS_CANONICAL_D1_IMPORT_SOURCE", "rows": 5884,
            "first": "2003-05-05", "last": "2026-02-26", "weekend_rows": 0,
            "output": {"sha256": "abc"}}


def test_catalog_presence_without_roundtrip_fails_closed(tmp_path):
    commands = tmp_path / "import.commands"
    commands.write_text("import")
    result = evaluate(source(), dict(EXPECTED), commands)
    assert result["decision"] == "BLOCK_SQ_D1_ROUNDTRIP_UNAVAILABLE"
    assert result["blocking_reasons"] == ["SQ_D1_ROUNDTRIP_UNAVAILABLE"]
    assert result["research_authorized"] is False


def test_catalog_mismatch_is_reported_independently(tmp_path):
    commands = tmp_path / "import.commands"
    commands.write_text("import")
    catalog = dict(EXPECTED, rows=1)
    result = evaluate(source(), catalog, commands)
    assert "SQ_CATALOG_OBSERVATION_MISMATCH" in result["blocking_reasons"]
