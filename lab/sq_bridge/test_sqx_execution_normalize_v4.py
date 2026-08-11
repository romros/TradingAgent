from __future__ import annotations

import zipfile
import json
import hashlib
from pathlib import Path

from sqx_execution_normalize_v4 import normalize
from sqx_extract import extract
from test_sqx_extract import SETTINGS, STRATEGY


def _source(path: Path) -> None:
    costly = SETTINGS.replace(
        b'<F key="ExitOnFriday.ExitOnFriday">false</F>',
        b'<F key="ExitOnFriday.ExitOnFriday">true</F>')
    costly = costly.replace(b'<S key="Slippage">0.0</S>',
                            b'<S key="Slippage">0.5</S>')
    costly = costly.replace(b'defaultSpread="0"', b'defaultSpread="0.8"')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr("settings.xml", costly)
        archive.writestr("version.txt", "3")


def test_normalizes_only_settings_and_produces_executable_sqx(tmp_path: Path):
    source, output = tmp_path / "source.sqx", tmp_path / "T.sqx"
    _source(source)
    result = normalize(source_path=source, output_path=output,
                       receipt_path=tmp_path / "receipt.json")

    assert result["decision"] == "PASS_VENUE_NEUTRAL_SQX"
    assert result["changed_members"] == ["settings.xml"]
    assert result["performance_from_source_invalidated"] is True
    assert result["source_member_sha256"]["strategy_Portfolio.xml"] == (
        result["output_member_sha256"]["strategy_Portfolio.xml"])
    contract = extract(output)
    assert contract["execution"]["exit_on_friday"] is False
    assert contract["execution"]["spread_in_sq"] == 0
    assert contract["execution"]["slippage_in_sq"] == 0
    assert contract["execution"]["commission_enabled"] is False
    assert contract["execution"]["swap_enabled"] is False


def test_normalization_is_byte_reproducible(tmp_path: Path):
    source = tmp_path / "source.sqx"
    _source(source)
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    first_dir.mkdir(); second_dir.mkdir()
    first, second = first_dir / "T.sqx", second_dir / "T.sqx"
    normalize(source_path=source, output_path=first,
              receipt_path=tmp_path / "first.json")
    normalize(source_path=source, output_path=second,
              receipt_path=tmp_path / "second.json")
    assert first.read_bytes() == second.read_bytes()


def test_post_retest_normalization_requires_exact_fresh_receipt(tmp_path: Path):
    source = tmp_path / "source.sqx"
    _source(source)
    retest = tmp_path / "retest.json"
    retest.write_text(json.dumps({
        "decision": "PASS_SUPERVISED_RETEST", "candidate_id": "T",
        "retest_output_sqx_path": str(source.resolve()),
        "retest_output_sqx_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "performance_filters_applied_in_sq": False, "total_tested": 1,
    }))
    result = normalize(
        source_path=source, output_path=tmp_path / "T.sqx",
        receipt_path=tmp_path / "receipt.json", retest_receipt_path=retest)
    assert result["fresh_sq_retest_proven"] is True
    assert result["normalization_role"] == "configuration_metadata_after_fresh_sq_retest"

    changed = json.loads(retest.read_text())
    changed["total_tested"] = 2
    retest.write_text(json.dumps(changed))
    import pytest
    with pytest.raises(ValueError, match="resultat fresc"):
        normalize(source_path=source, output_path=tmp_path / "other" / "T.sqx",
                  receipt_path=tmp_path / "bad.json", retest_receipt_path=retest)
