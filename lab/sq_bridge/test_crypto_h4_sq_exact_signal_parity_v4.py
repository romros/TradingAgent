from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_sq_exact_signal_parity_v4 import SOURCES, run


class Result:
    returncode = 0
    stdout = "PASS_EXACT_SIGNAL_PARITY comparisons=21576 differences=0\n"
    stderr = ""


def inputs(tmp_path: Path):
    source = tmp_path / "source"
    for member in SOURCES:
        path = source / member; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class Placeholder {}")
    internal = tmp_path / "internal"; (internal / "libs").mkdir(parents=True)
    (internal / "libs/SQTradingLib.jar").write_bytes(b"sq")
    price = tmp_path / "price.txt"; price.write_text("price")
    signal = tmp_path / "signal.txt"; signal.write_text("signal")
    return source, internal, price, signal


def test_signal_parity_runner_is_offline_and_evidence_bound(tmp_path: Path):
    source, internal, price, signal = inputs(tmp_path)

    def runner(command, **kwargs):
        assert command[command.index("--network") + 1] == "none"
        return Result()

    result = run(source_root=source, internal_root=internal, price_oracle=price,
                 signal_oracle=signal, output_dir=tmp_path / "out", runner=runner)
    assert result["decision"] == "PASS_EXACT_SQ_CHARTDATA_SIGNAL_PARITY"
    assert result["differences"] == 0
    assert result["strategy_promotion_authorized"] is False


def test_signal_parity_runner_fails_without_exact_pass(tmp_path: Path):
    source, internal, price, signal = inputs(tmp_path)

    class Failed(Result):
        returncode = 1; stdout = ""; stderr = "differences=1"

    with pytest.raises(RuntimeError, match="differences=1"):
        run(source_root=source, internal_root=internal, price_oracle=price,
            signal_oracle=signal, output_dir=tmp_path / "out",
            runner=lambda *args, **kwargs: Failed())
