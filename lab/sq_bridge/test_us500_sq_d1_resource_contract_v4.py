import hashlib
import json
from pathlib import Path

from lab.sq_bridge.us500_sq_d1_resource_contract_v4 import verify


ROOT = Path(__file__).parent
RECEIPT = ROOT / "evidence/us500_alq_rth_d1_sq_resource_v4.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_us500_sq_resource_replays_to_exact_ohlcv_parity():
    result = verify(RECEIPT)
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["replayed_exact_numeric_parity"] is True


def test_resource_contract_detects_export_tampering_without_using_sq_claim(tmp_path):
    receipt = json.loads(RECEIPT.read_text())
    source = Path(receipt["source"]["path"])
    exported = Path(receipt["roundtrip"]["export_path"])
    commands = ROOT.parents[1] / receipt["commands"]["path"]
    audit = ROOT.parents[1] / receipt["roundtrip"]["audit_path"]
    copies = {}
    for label, original in (("source", source), ("export", exported),
                            ("commands", commands), ("audit", audit)):
        copies[label] = tmp_path / original.name
        copies[label].write_bytes(original.read_bytes())
    receipt["source"].update(
        {"path": str(copies["source"]), "sha256": _sha(copies["source"])})
    receipt["commands"].update(
        {"path": str(copies["commands"]), "sha256": _sha(copies["commands"])})
    receipt["roundtrip"].update({
        "export_path": str(copies["export"]),
        "export_sha256": _sha(copies["export"]),
        "audit_path": str(copies["audit"]),
        "audit_sha256": _sha(copies["audit"]),
    })
    local = tmp_path / "receipt.json"
    local.write_text(json.dumps(receipt) + "\n")
    assert verify(local)["valid"] is True
    copies["export"].write_text(copies["export"].read_text() + "\n")
    result = verify(local)
    assert result["valid"] is False
    assert "EXPORT_HASH_MISMATCH" in result["errors"]
