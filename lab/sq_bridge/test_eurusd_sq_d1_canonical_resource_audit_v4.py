from lab.sq_bridge.eurusd_sq_d1_canonical_resource_audit_v4 import audit, sha256


def receipt(path, rows=5884):
    return {"decision": "PASS_CANONICAL_D1_IMPORT_SOURCE", "rows": rows,
            "output": {"sha256": sha256(path)}}


def test_accepts_only_sq_zero_to_one_volume_normalization(tmp_path):
    source, exported = tmp_path / "source.csv", tmp_path / "export.csv"
    # Repeat distinct dates so the production row-count invariant is exercised.
    # Give every row a unique synthetic key while keeping CSV parsing simple.
    rows = [f"D{i:04d},00:00,1.1,1.2,1.0,1.15,0" for i in range(5884)]
    source.write_text("\n".join(rows) + "\n")
    exported.write_text(("\n".join(row[:-1] + "1" for row in rows)) + "\n")
    result = audit(source, exported, receipt(source))
    assert result["decision"] == "PASS_SQ_D1_RESOURCE"
    assert result["ohlc_match_ratio"] == 1


def test_price_change_blocks(tmp_path):
    source, exported = tmp_path / "source.csv", tmp_path / "export.csv"
    rows = [f"D{i:04d},00:00,1.1,1.2,1.0,1.15,1" for i in range(5884)]
    source.write_text("\n".join(rows) + "\n")
    rows[0] = "D0000,00:00,1.1,1.2,1.0,1.16,1"
    exported.write_text("\n".join(rows) + "\n")
    assert audit(source, exported, receipt(source))["decision"] == "BLOCK_SQ_D1_RESOURCE_PARITY"
