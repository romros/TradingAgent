import hashlib
import json

from lab.sq_bridge.eurusd_sq_d1_extended_resource_audit_v4 import audit


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audits_exact_extended_roundtrip_and_allows_only_zero_volume_normalization(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("2026.07.31,00:00,1,2,0.5,1.5,0\n")
    exported = tmp_path / "export.csv"
    exported.write_text("2026.07.31,00:00,1,2,0.5,1.5,1\n")
    extension = tmp_path / "extension.json"
    extension.write_text(json.dumps({
        "decision": "PASS_HOLDOUT_SOURCE_EXTENSION", "performance_accessed": False,
        "output_path": str(source), "output_sha256": _sha(source),
        "last": "2026-07-31", "required_through": "2026-07-31"}))
    parity = tmp_path / "parity.json"
    parity.write_text(json.dumps({
        "decision": "PASS_CANDLE_PARITY", "performance_accessed": False,
        "dukascopy_candles_sha256": _sha(source), "sq_candles_path": str(exported),
        "sq_candles_sha256": _sha(exported), "sq_rows": 1}))
    result = audit(extension_receipt_path=extension, parity_contract_path=parity,
                   output_path=tmp_path / "audit.json")
    assert result["decision"] == "PASS_SQ_D1_RESOURCE"
    assert result["checks"]["holdout_covered"] is True
    assert result["volume_normalizations"] == [
        {"day": "2026.07.31", "source": 0, "sq_export": 1}]
