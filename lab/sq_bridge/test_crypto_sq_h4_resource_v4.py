import hashlib
import json

import pytest

from lab.sq_bridge.crypto_sq_h4_resource_v4 import build, expected_commands


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("2020.01.01,00:00,100.00,102.00,99.00,101.00,1.25\n")
    exported = tmp_path / "BTCUSD_ALQ_H4-H4-No Session.csv"
    exported.write_text("2020.01.01,00:00,100.00,102.00,99.00,101.00,1\n")
    canonical = tmp_path / "canonical.json"
    canonical.write_text(json.dumps({
        "decision": "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED",
        "research_symbol": "BTCUSD", "source_symbol": "BTCUSDT",
        "timeframe": "H4", "timezone": "UTC", "canonical_sha256": _sha(source),
        "rows": 1, "first_bar_utc": "2020-01-01T00:00:00+00:00",
        "last_bar_utc": "2020-01-01T00:00:00+00:00",
        "performance_accessed": False, "research_authorized": False}))
    commands = tmp_path / "commands"
    commands.write_text("\n".join(expected_commands("BTCUSD", source, exported.parent)) + "\n")
    return canonical, source, exported, commands


def test_certifies_exact_ohlc_but_records_volume_normalization(tmp_path):
    canonical, source, exported, commands = _fixture(tmp_path)
    result = build(market="BTCUSD", canonical_receipt_path=canonical,
                   source_path=source, exported_path=exported,
                   commands_path=commands, output_path=tmp_path / "receipt.json")
    assert result["decision"] == "PASS_SQ_H4_PROXY_RESOURCE"
    assert result["roundtrip"]["exact_ohlc_parity"] is True
    assert result["roundtrip"]["volume_changed_rows"] == 1
    assert result["checks"]["volume_dependent_rules_forbidden"] is True
    assert result["research_authorized"] is False


def test_rejects_rounded_price(tmp_path):
    canonical, source, exported, commands = _fixture(tmp_path)
    exported.write_text("2020.01.01,00:00,100.01,102.00,99.00,101.00,1\n")
    with pytest.raises(ValueError, match="not timestamp/OHLC exact"):
        build(market="BTCUSD", canonical_receipt_path=canonical,
              source_path=source, exported_path=exported,
              commands_path=commands, output_path=tmp_path / "receipt.json")


def test_rejects_embedded_spread_or_command_drift(tmp_path):
    canonical, source, exported, commands = _fixture(tmp_path)
    commands.write_text(commands.read_text().replace("defaultspread=0", "defaultspread=1"))
    with pytest.raises(ValueError, match="neutral frozen contract"):
        build(market="BTCUSD", canonical_receipt_path=canonical,
              source_path=source, exported_path=exported,
              commands_path=commands, output_path=tmp_path / "receipt.json")
