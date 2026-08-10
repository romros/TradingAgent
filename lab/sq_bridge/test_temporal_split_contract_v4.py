import json
from datetime import date, timedelta
from pathlib import Path

from lab.sq_bridge.temporal_split_contract_v4 import (
    build_contract, digest, sq_periods,
)


ROOT = Path(__file__).parent


def _source(tmp_path, rows=100):
    path, values, day = tmp_path / "source.csv", [], date(2020, 1, 1)
    while len(values) < rows:
        if day.weekday() < 5:
            values.append(f"{day:%Y.%m.%d},00:00,1,1,1,1,1")
        day += timedelta(days=1)
    path.write_text("\n".join(values) + "\n")
    return path, values


def test_observation_split_is_exact_embargoed_and_reproducible(tmp_path):
    source, values = _source(tmp_path, 1000)
    contract = build_contract(source, ROOT / "methodology_v4.json")
    assert contract == build_contract(source, ROOT / "methodology_v4.json")
    assert len(digest(contract)) == 64
    assert contract["segments"]["train"] == {
        "first_row_index": 0, "last_row_index": 499, "rows": 500,
        "from": values[0][:10].replace(".", "-"),
        "to": values[499][:10].replace(".", "-"),
    }
    assert contract["segments"]["validation"]["first_row_index"] == 510
    assert contract["segments"]["oos"]["first_row_index"] == 710
    assert contract["segments"]["final_holdout"]["first_row_index"] == 910


def test_realistic_contract_maps_exact_dates_for_sq(tmp_path):
    source, values = _source(tmp_path, 1000)
    contract = build_contract(source, ROOT / "methodology_v4.json")
    periods = sq_periods(contract)
    assert periods["train_to"] == values[499][:10].replace(".", "-")
    assert periods["validation_from"] == values[510][:10].replace(".", "-")
    assert periods["holdout_to"] == values[-1][:10].replace(".", "-")
