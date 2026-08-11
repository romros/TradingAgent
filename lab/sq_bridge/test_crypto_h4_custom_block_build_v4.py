from pathlib import Path
import zipfile

import pytest

from lab.sq_bridge.crypto_h4_custom_block_build_v4 import (
    CLASS_MEMBERS, SOURCE_MEMBERS, build,
)


class Result:
    returncode = 0
    stderr = ""


def test_build_is_offline_compile_only_and_packages_no_stub(tmp_path: Path):
    source_root = tmp_path / "source"
    for member in SOURCE_MEMBERS:
        source = source_root / member
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("class placeholder {}")
    internal = tmp_path / "internal"
    (internal / "libs").mkdir(parents=True)
    (internal / "libs/Snippets.jar").write_bytes(b"sq")

    def runner(command, **kwargs):
        assert command[command.index("--network") + 1] == "none"
        assert f"type=bind,src={internal.resolve()},dst=/sq/internal,readonly" in command
        for member in CLASS_MEMBERS:
            output = tmp_path / "out/classes" / member
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x42payload")
        return Result()

    result = build(source_root=source_root, internal_root=internal,
                   output_dir=tmp_path / "out", runner=runner)
    assert result["decision"] == "PASS_COMPILE_ONLY_NOT_PARITY"
    assert result["promotion_authorized"] is False
    with zipfile.ZipFile(result["bundle_path"]) as bundle:
        assert bundle.namelist() == list(CLASS_MEMBERS)


def test_missing_inputs_fail_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="missing"):
        build(source_root=tmp_path, internal_root=tmp_path,
              output_dir=tmp_path / "out")


def test_versioned_stop_and_continuity_sources_enforce_canonical_semantics():
    root = Path(__file__).parent / "sq_custom_blocks_v4"
    formula = (root / "SQ/Formulas/SLPT/AlquimiaH4GapSafeSMAATRValue.java").read_text()
    guard = (root / "SQ/Blocks/BarAndTime/AlquimiaH4WindowIsContinuous.java").read_text()
    utility = (root / "SQ/Utils/AlquimiaGapSafeATR.java").read_text()
    signals = (root / "SQ/Utils/AlquimiaH4Signals.java").read_text()
    assert "stopPrice(" in formula and "AtrPeriod, 1, currentBar" in formula
    assert "SQUtils" not in formula
    assert "isContinuous(Chart, Shift, Transitions)" in guard
    assert "H4_MILLISECONDS = 4L * 60L * 60L * 1000L" in utility
    assert "return Double.NaN" in utility
    assert "Math.max(period, 13)" in signals
    assert "shift + period" in signals
    assert "offset = 1; offset <= period" in signals
