import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "lab/sq_bridge/evidence"
SOURCE_ROOT = ROOT / "lab/sq_bridge/sq_custom_blocks_v4"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_compression_install_evidence_is_bound_to_parity_and_sources():
    receipt = json.loads((EVIDENCE / "crypto_h4_compression_signal_install_v4.json").read_text())
    parity_path = ROOT / receipt["exact_signal_parity_path"]
    parity = json.loads(parity_path.read_text())
    assert receipt["decision"] == "PASS_SQ_COMPRESSION_SIGNALS_INSTALL_CATALOG_AND_RUNTIME"
    assert receipt["catalog_entries"] == [
        "AlquimiaH4CompressionChannelAbove",
        "AlquimiaH4CompressionChannelBelow"]
    assert receipt["exact_signal_comparisons"] == 32364
    assert parity["differences"] == receipt["exact_signal_differences"] == 0
    for member, digest in receipt["installed_source_sha256"].items():
        assert _sha(SOURCE_ROOT / member) == digest
    assert parity["source_sha256"]["SQ/Utils/AlquimiaH4Signals.java"] == \
        receipt["installed_source_sha256"]["SQ/Utils/AlquimiaH4Signals.java"]
    assert receipt["strategy_promotion_authorized"] is False


def test_compression_smoke_is_explicitly_non_promotional():
    smoke = json.loads((EVIDENCE / "crypto_h4_compression_signal_smoke_replay_v4.json").read_text())
    assert smoke["decision"] == "PASS_TECHNICAL_GROSS_SMOKE_NOT_FORMAL_CANDIDATE"
    assert smoke["translation_status"] == "SUPPORTED_SUBSET"
    assert smoke["formal_screen_member"] is False
    assert smoke["costs_accessed"] is False
    assert smoke["validation_accessed"] is False
    assert smoke["oos_accessed"] is False
    assert smoke["strategy_promotion_authorized"] is False
