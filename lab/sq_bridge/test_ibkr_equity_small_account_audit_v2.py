import csv

import pytest

from lab.sq_bridge.ibkr_equity_small_account_audit_v2 import audit, load_orders, simulate


def _orders(tmp_path, rows):
    path = tmp_path / "orders.csv"
    fields = ["Type", "Open time", "Open price", "Close time", "Close price", "Profit/Loss"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader(); writer.writerows(rows)
    return load_orders(path)


def test_whole_share_compounding_and_minimum_tiered_fee(tmp_path):
    orders = _orders(tmp_path, [{
        "Type": "Buy", "Open time": "2023.01.02 10:00:00", "Open price": "100",
        "Close time": "2023.01.02 11:00:00", "Close price": "110", "Profit/Loss": "10",
    }])
    result = simulate(orders, initial_capital=1000, plan="tiered")
    assert result["minimum_shares"] == 10
    assert result["net_pnl_usd"] == pytest.approx(99.3)


def test_rejects_overlapping_positions(tmp_path):
    with pytest.raises(ValueError, match="overlapping"):
        _orders(tmp_path, [{
            "Type": "Buy", "Open time": "2023.01.02 10:00:00", "Open price": "100",
            "Close time": "2023.01.02 12:00:00", "Close price": "101", "Profit/Loss": "1",
        }, {
            "Type": "Buy", "Open time": "2023.01.02 11:00:00", "Open price": "100",
            "Close time": "2023.01.02 13:00:00", "Close price": "101", "Profit/Loss": "1",
        }])


def test_oos_audit_discloses_access_without_opening_holdout(tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text(
        '"Type";"Open time";"Open price";"Close time";"Close price";"Profit/Loss"\n'
        '"Buy";"2024.01.02 10:00:00";"100";"2024.01.02 11:00:00";"101";"1"\n')
    result = audit(candidate_id="T", orders_path=path,
                   capital_scenarios=[1000], stage="oos")
    assert result["stage"] == "IBKR_EQUITY_SMALL_ACCOUNT_OOS_AUDIT"
    assert result["oos_2024_accessed"] is True
    assert result["holdout_2025_accessed"] is False


def test_same_bar_d1_stop_allows_sub_target_favorable_excursion(tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text(
        '"Type";"Open time";"Open price";"Close time";"Close price";'
        '"Profit/Loss";"Close type";"MAE ($)";"MFE ($)"\n'
        '"Buy";"2024.01.02 10:00:00";"100";"2024.01.02 10:00:00";'
        '"98";"-2";"SL";"-2";"0.5"\n')
    orders = load_orders(path, allow_same_bar_d1=True)
    assert len(orders) == 1 and orders[0]["mfe"] == .5


def test_same_bar_d1_accepts_verified_target_and_endtest(tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text(
        '"Type";"Open time";"Open price";"Size";"Close time";"Close price";'
        '"Profit/Loss";"Close type";"MAE ($)";"MFE ($)"\n'
        '"Buy";"2024.01.02 10:00:00";"100";"2";"2024.01.02 10:00:00";'
        '"105";"10";"PT";"-1";"10"\n'
        '"Buy";"2024.01.03 10:00:00";"100";"2";"2024.01.03 10:00:00";'
        '"99";"-2";"EndTest";"-3";"1"\n')
    orders = load_orders(path, allow_same_bar_d1=True)
    assert [row["close_type"] for row in orders] == ["PT", "EndTest"]
