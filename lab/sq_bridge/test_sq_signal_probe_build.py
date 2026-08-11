from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from sq_signal_probe_build import (
    SUPPORTED_SIGNAL_SOURCE_SHA256,
    _replace_class_deterministically,
    instrument,
)


REAL_SOURCE = Path(
    "/home/roman/dockers-SQ/6ACC10/internal/extend/Snippets/"
    "SQ/Internal/RulesImpl/Signal.java"
)


def test_installed_source_is_allowlisted_and_instrumentation_is_opt_in_bar_only():
    raw = REAL_SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() in SUPPORTED_SIGNAL_SOURCE_SHA256
    # Path.read_text() applies the same universal-newline normalization as build().
    patched = instrument(REAL_SOURCE.read_text())

    assert 'System.getenv("ALQUIMIA_SIGNAL_LOG_PATH")' in patched
    assert "if(updateEventType == barEventType)" in patched
    assert "long strategyTime = Strategy.Time(0);" in patched
    assert "import com.strategyquant.lib.SQTime;" not in patched
    assert "writeAlquimiaSignal(signalVariableIds[i], value);" in patched
    assert patched.count("signalVariableIds.add(signalVarId);") == 2
    assert "super.deinitialize();" in patched


def test_instrumentation_fails_closed_if_sq_source_anchor_changes():
    source = REAL_SOURCE.read_text().replace(
        "private Variable[] signalVariables = null;",
        "private Variable[] upstreamSignalVariables = null;",
    )
    with pytest.raises(ValueError, match="anchor mismatch"):
        instrument(source)


def _make_original_jar(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in (
            ("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\n"),
            ("SQ/Internal/RulesImpl/Signal.class", b"old"),
            ("SQ/Other.class", b"unchanged"),
        ):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 2, 3, 4, 6))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)


def test_class_replacement_is_reproducible_and_changes_only_signal(tmp_path: Path):
    original = tmp_path / "Snippets.jar"
    compiled = tmp_path / "Signal.class"
    first = tmp_path / "first.jar"
    second = tmp_path / "second.jar"
    _make_original_jar(original)
    compiled.write_bytes(b"compiled-java-22-class")

    _replace_class_deterministically(
        original_jar=original, class_file=compiled, output_jar=first)
    _replace_class_deterministically(
        original_jar=original, class_file=compiled, output_jar=second)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as patched, zipfile.ZipFile(original) as source:
        assert patched.namelist() == source.namelist()
        assert patched.read("SQ/Internal/RulesImpl/Signal.class") == compiled.read_bytes()
        assert patched.read("SQ/Other.class") == source.read("SQ/Other.class")
