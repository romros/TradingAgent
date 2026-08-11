from pathlib import Path
import zipfile

import pytest

from lab.sq_bridge.crypto_h4_custom_block_build_v4 import CLASS_MEMBER, build


class Result:
    returncode = 0
    stderr = ""


def test_build_is_offline_compile_only_and_packages_no_stub(tmp_path: Path):
    source_root = tmp_path / "source"
    source = source_root / CLASS_MEMBER.replace(".class", ".java")
    source.parent.mkdir(parents=True)
    source.write_text("class placeholder {}")
    internal = tmp_path / "internal"
    (internal / "libs").mkdir(parents=True)
    (internal / "libs/Snippets.jar").write_bytes(b"sq")

    def runner(command, **kwargs):
        assert command[command.index("--network") + 1] == "none"
        assert f"type=bind,src={internal.resolve()},dst=/sq/internal,readonly" in command
        output = tmp_path / "out/classes" / CLASS_MEMBER
        output.parent.mkdir(parents=True)
        output.write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x42payload")
        return Result()

    result = build(source_root=source_root, internal_root=internal,
                   output_dir=tmp_path / "out", runner=runner)
    assert result["decision"] == "PASS_COMPILE_ONLY_NOT_PARITY"
    assert result["promotion_authorized"] is False
    with zipfile.ZipFile(result["bundle_path"]) as bundle:
        assert bundle.namelist() == [CLASS_MEMBER]


def test_missing_inputs_fail_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="missing"):
        build(source_root=tmp_path, internal_root=tmp_path,
              output_dir=tmp_path / "out")

