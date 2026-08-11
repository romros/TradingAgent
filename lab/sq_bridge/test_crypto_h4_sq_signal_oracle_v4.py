import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab.sq_bridge.crypto_h4_sq_signal_oracle_v4 import CASES, build


def test_signal_oracle_is_deterministic_and_covers_shift_period_level(tmp_path: Path):
    source = tmp_path / "prices.csv"
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with source.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        for index in range(80):
            stamp = start + timedelta(hours=4 * index)
            close = 100 + index
            writer.writerow((stamp.strftime("%Y.%m.%d"), stamp.strftime("%H:%M"),
                             close - 1, close + .5, close - 1.5, close, 1))
    output = tmp_path / "signals.csv"
    result = build(source=source, output=output, maximum_rows=80)
    rows = list(csv.reader(output.open(), delimiter=";"))
    assert rows[0][:6] == ["decision", "period", "shift", "level",
                           "compression_lookback", "compression_percentile"]
    assert rows[0][-2:] == ["compression_above", "compression_below"]
    assert len(rows) == 1 + len(CASES) * 79
    assert result["expectations"] == len(CASES) * 79
    assert result["evaluation_timing"] == "entry_bar_with_sq_shift_1_or_2"
