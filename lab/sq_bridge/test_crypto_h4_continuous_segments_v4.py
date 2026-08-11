import csv
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_continuous_segments_v4 import split_continuous


def _write(path: Path, times: list[str]) -> None:
    with path.open("w", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(
            [["2024.01.01", time, "100", "101", "99", "100", "1"]
             for time in times])


def test_split_is_lossless_ordered_and_marks_short_segments(tmp_path: Path):
    source = tmp_path / "source.csv"
    _write(source, ["00:00", "04:00", "08:00", "16:00", "20:00"])
    result = split_continuous(source=source, output_dir=tmp_path / "segments",
                              minimum_eligible_bars=3)
    assert result["segment_count"] == 2
    assert result["eligible_segment_count"] == 1
    assert result["all_source_rows_assigned_exactly_once"] is True
    assert [item["rows"] for item in result["segments"]] == [3, 2]
    combined = []
    for item in result["segments"]:
        combined.extend(Path(item["path"]).read_text().splitlines())
    assert combined == source.read_text().splitlines()
    assert result["promotion_authorized"] is False


def test_non_increasing_source_fails_closed(tmp_path: Path):
    source = tmp_path / "source.csv"
    _write(source, ["04:00", "00:00"])
    with pytest.raises(ValueError, match="strictly increasing"):
        split_continuous(source=source, output_dir=tmp_path / "segments",
                         minimum_eligible_bars=1)

