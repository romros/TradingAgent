import csv
import json

from lab.sq_bridge.ibkr_equity_split_adjusted_d1_v2 import build


def test_adjusts_prices_and_volume_to_latest_share_basis(tmp_path):
    source = tmp_path / "raw.csv"
    source.write_text(
        "2020.08.28,00:00,1500,1530,1470,1500,10\n"
        "2020.08.31,00:00,300,306,294,300,50\n"
        "2022.08.24,00:00,900,918,882,900,20\n"
        "2022.08.25,00:00,300,306,294,300,60\n")
    output, receipt = tmp_path / "adjusted.csv", tmp_path / "receipt.json"
    result = build(source=source, output=output, receipt=receipt, symbol="TEST",
                   splits=[
                       {"effective_date": "2020-08-31", "factor": 5,
                        "source_url": "https://example.test/one"},
                       {"effective_date": "2022-08-25", "factor": 3,
                        "source_url": "https://example.test/two"}])
    with output.open() as stream:
        rows = list(csv.reader(stream))
    assert [float(row[5]) for row in rows] == [100, 100, 300, 300]
    assert [float(row[6]) for row in rows] == [150, 150, 60, 60]
    assert result["split_boundary_returns"] == [
        {"effective_date": "2020-08-31", "adjusted_close_return": 0.0},
        {"effective_date": "2022-08-25", "adjusted_close_return": 0.0}]
    assert json.loads(receipt.read_text())["performance_accessed"] is False
