#!/usr/bin/env python3
"""Frozen GLD physical-holdings flow screen using the official XLSX archive."""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_archive(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in shared_root.findall("m:si", NS)]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
    rows = []
    for xml_row in sheet.findall(".//m:sheetData/m:row", NS):
        values = []
        for cell in xml_row.findall("m:c", NS):
            value = cell.find("m:v", NS)
            raw = "" if value is None else value.text
            values.append(shared[int(raw)] if cell.get("t") == "s" and raw else raw)
        rows.append(values)
    header = rows[0]
    result = []
    for values in rows[1:]:
        row = dict(zip(header, values))
        try:
            result.append({
                "date": datetime.strptime(row["Date"], "%d-%b-%Y").date(),
                "price": float(row["Indicative Price per Share at 4:15pm NYT"]),
                "ounces": float(row["Total Ounces of Gold in the Trust"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return result


def friday(day: date) -> date:
    return day + timedelta(days=4 - day.weekday())


def weekly_last(rows: list[dict]) -> list[dict]:
    selected = {}
    for row in rows:
        key = friday(row["date"])
        if key not in selected or row["date"] > selected[key]["date"]:
            selected[key] = row
    return [{**selected[key], "week": key} for key in sorted(selected)]


def build_episodes(rows: list[dict], lookback: int = 4, threshold_pct: float = 1.0) -> list[dict]:
    states = []
    threshold = threshold_pct / 100
    for index in range(lookback, len(rows) - 1):
        factor, prior, executable = rows[index], rows[index - lookback], rows[index + 1]
        change = factor["ounces"] / prior["ounces"] - 1
        state = 1 if change >= threshold else -1 if change <= -threshold else 0
        states.append((executable, state))
    episodes = []
    active = 0
    entry = None
    for row, state in states:
        if state == active:
            continue
        if active and entry is not None:
            episodes.append({
                "entry": entry["week"],
                "exit": row["week"],
                "signal": active,
                "gross_return": active * (row["price"] / entry["price"] - 1),
            })
        active = state
        entry = row if state else None
    return episodes


def summarize(episodes: list[dict], execution_bps: float = 12, annual_financing_pct: float = 12) -> dict:
    gains = losses = total = 0.0
    yearly = defaultdict(float)
    for row in episodes:
        days = (row["exit"] - row["entry"]).days
        net = row["gross_return"] - execution_bps / 10_000 - annual_financing_pct / 100 * days / 365
        total += net
        yearly[row["exit"].year] += net
        gains += max(net, 0)
        losses += max(-net, 0)
    positive = sum(value > 0 for value in yearly.values())
    return {
        "closed_episodes": len(episodes),
        "long_episodes": sum(row["signal"] == 1 for row in episodes),
        "short_episodes": sum(row["signal"] == -1 for row in episodes),
        "gross_return_sum_pct": round(100 * sum(row["gross_return"] for row in episodes), 6),
        "net_return_sum_pct": round(100 * total, 6),
        "profit_factor_after_stress": round(gains / losses, 6) if losses else math.inf,
        "positive_years": positive,
        "years": len(yearly),
        "positive_year_share": round(positive / len(yearly), 6) if yearly else 0,
        "yearly_net_pct": {str(year): round(100 * value, 6) for year, value in sorted(yearly.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    episodes = build_episodes(weekly_last(load_archive(args.archive)))
    train = [row for row in episodes if date(2006, 1, 1) <= row["entry"] and row["exit"] <= date(2018, 12, 31)]
    metrics = summarize(train)
    passed = metrics["closed_episodes"] >= 30 and metrics["gross_return_sum_pct"] > 0 and metrics["net_return_sum_pct"] > 0 and metrics["profit_factor_after_stress"] >= 1.2 and metrics["positive_year_share"] >= 0.6
    result = {
        "experiment": "xau-gld-holdings-flow-v36",
        "split": "TRAIN_ONLY",
        "publication_lag_weeks": 1,
        "sealed_ostium_holdout_accessed": False,
        "archive_rows_outside_train_ignored": True,
        "metrics": metrics,
        "decision": "OPEN_FROZEN_VALIDATION" if passed else "REJECT_BEFORE_SQ",
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
