import csv
from pathlib import Path

from lab.sq_bridge.msft_capitulation_sq_parity_v1 import build


def test_rejects_extra_sq_entry(tmp_path: Path):
    candles = tmp_path / "candles.csv"
    candles.write_text("\n".join(
        f"2024.01.{day:02d},00:00,100,101,95,{96 if day == 20 else 100},1"
        for day in range(1, 23)
    ) + "\n")
    orders = tmp_path / "orders.csv"
    with orders.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Open time"], delimiter=";")
        writer.writeheader()
        writer.writerow({"Open time": "2024.01.22 14:30:00"})
    report = build(candles, orders)
    assert report["decision"] == "REJECT_SIGNAL_PARITY"
    assert report["actual_sq_entries"] == 1
