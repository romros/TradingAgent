import csv
from pathlib import Path

from lab.sq_bridge.crypto_h4_sq_indicator_oracle_v4 import build


def test_oracle_uses_official_seven_semicolon_column_format(tmp_path: Path):
    source = tmp_path / "source.csv"
    with source.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        for index in range(20):
            writer.writerow(["2024.01.01", f"{index * 4:02d}:00" if index < 6 else
                             f"{(index * 4) % 24:02d}:00", 100, 102, 99, 101, 1])
    # Use valid multi-day timestamps instead of relying on the compact fixture above.
    source.write_text("".join(
        f"2024.01.{1 + index // 6:02d},{(index % 6) * 4:02d}:00,100,102,99,101,1\n"
        for index in range(20)))
    output = tmp_path / "oracle.txt"
    result = build(source=source, output=output, maximum_rows=20)
    rows = list(csv.reader(output.open(), delimiter=";"))
    assert len(rows) == 20 and all(len(row) == 7 for row in rows)
    assert rows[0][0] == "2024.01.01 00:00:00"
    assert rows[0][6] == "NaN"
    assert rows[13][6] == "3.0"
    assert result["sq_bars_to_reserve"] == 14
    assert result["comparison_decimals"] == 10
