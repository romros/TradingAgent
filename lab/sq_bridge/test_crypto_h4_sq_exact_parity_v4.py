from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_sq_exact_parity_v4 import run


class Result:
    returncode = 0
    stdout = "PASS_EXACT_ATR_STOP_PARITY rows=512 stop_comparisons=3984 differences=0\n"
    stderr = ""


def fixture(tmp_path: Path):
    source = tmp_path / "source"
    for member in ("SQ/Utils/AlquimiaGapSafeATR.java", "parity/AlquimiaATRParityHarness.java",
                   "parity/stubs/com/strategyquant/lib/random/MersenneTwisterRng.java"):
        path = source / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class Placeholder {}")
    internal = tmp_path / "internal"
    (internal / "libs").mkdir(parents=True)
    (internal / "libs/SQTradingLib.jar").write_bytes(b"sq")
    oracle = tmp_path / "oracle.txt"
    oracle.write_text("oracle")
    return source, internal, oracle


def test_exact_parity_is_offline_fail_closed_and_evidence_bound(tmp_path: Path):
    source, internal, oracle = fixture(tmp_path)

    def runner(command, **kwargs):
        assert command[command.index("--network") + 1] == "none"
        return Result()

    result = run(source_root=source, internal_root=internal, oracle=oracle,
                 output_dir=tmp_path / "out", runner=runner)
    assert result["decision"] == "PASS_EXACT_SQ_CHARTDATA_ATR_STOP_PARITY"
    assert result["comparison"] == "DOUBLE_BITS_EXACT"
    assert result["differences"] == 0
    assert result["strategy_promotion_authorized"] is False


def test_any_runtime_failure_or_missing_pass_marker_fails_closed(tmp_path: Path):
    source, internal, oracle = fixture(tmp_path)

    class Failed(Result):
        returncode = 1
        stdout = ""
        stderr = "differences=1"

    with pytest.raises(RuntimeError, match="differences=1"):
        run(source_root=source, internal_root=internal, oracle=oracle,
            output_dir=tmp_path / "out", runner=lambda *args, **kwargs: Failed())
