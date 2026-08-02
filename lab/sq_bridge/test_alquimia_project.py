#!/usr/bin/env python3
from datetime import date
from alquimia_project import SEARCH_PROFILES, _split_dates

breakout = SEARCH_PROFILES["xau_h4_channel_breakout_v1"]
assert "Indicators.Highest" in breakout and "Indicators.Lowest" in breakout
assert "Indicators.SMA" not in breakout and "Indicators.EMA" not in breakout
stop_breakout = SEARCH_PROFILES["xau_h4_stop_channel_breakout_v2"]
assert "EnterAtStop" in stop_breakout
assert "Stop/Limit Price Levels.Highest" in stop_breakout
assert "EnterAtMarket" not in stop_breakout
compression = SEARCH_PROFILES["xau_h4_atr_compression_breakout_v3"]
assert {"Indicators.ATR", "IsFalling", "EnterAtStop"}.issubset(compression)
assert "Indicators.ADX" not in compression and "Indicators.ROC" not in compression

split = _split_dates(date(2017, 1, 26), date(2026, 3, 13),
    {"train_pct": 50, "validation_pct": 20, "oos_pct": 20, "final_holdout_pct": 10})
assert split["train_to"] == "2021-08-19"
assert split["validation_to"] == "2023-06-17"
assert split["oos_to"] == "2025-04-14"
assert split["holdout_to"] == "2026-03-13"
assert split["train_to"] < split["validation_from"] < split["oos_from"] < split["holdout_from"]
print("PASS: sealed chronological split")
