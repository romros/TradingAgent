#!/usr/bin/env python3
"""Compare daily proxy closes with Ostium in memory; emit summary evidence only."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import statistics
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from probe_ostium_ohlc import fetch as fetch_ostium


COINBASE_ENDPOINT = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
EIA_WTI_XLS = "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls"
EIA_WTI_FRONT_FUTURE_XLS = "https://www.eia.gov/dnav/pet/hist_xls/RCLC1d.xls"
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def daily_closes(rows: list[list[float]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows:
        day = datetime.fromtimestamp(row[0], UTC).date().isoformat()
        if day in result:
            raise ValueError(f"duplicate daily candle: {day}")
        result[day] = float(row[4])
    return result


def ostium_closes(payload: dict) -> dict[str, float]:
    result: dict[str, float] = {}
    for candle in payload.get("data", []):
        day = datetime.fromtimestamp(candle["time"] / 1000, UTC).date().isoformat()
        if day in result:
            raise ValueError(f"duplicate Ostium daily candle: {day}")
        result[day] = float(candle["close"])
    return result


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return numerator / denominator if denominator else None


def compare(proxy: dict[str, float], target: dict[str, float]) -> dict:
    common = sorted(set(proxy) & set(target))
    close_diff_bps = [abs(proxy[d] / target[d] - 1) * 10_000 for d in common if target[d]]
    proxy_returns: dict[str, float] = {}
    target_returns: dict[str, float] = {}
    for before, after in zip(common, common[1:]):
        if proxy[before]:
            proxy_returns[after] = proxy[after] / proxy[before] - 1
        if target[before]:
            target_returns[after] = target[after] / target[before] - 1
    correlations = {}
    close_differences_by_lag = {}
    for lag in range(-2, 3):
        pairs = []
        shifted_close_differences = []
        for day, value in proxy_returns.items():
            shifted = (datetime.fromisoformat(day).date() + timedelta(days=lag)).isoformat()
            if shifted in target_returns:
                pairs.append((value, target_returns[shifted]))
        for day, value in proxy.items():
            shifted = (datetime.fromisoformat(day).date() + timedelta(days=lag)).isoformat()
            if shifted in target and target[shifted]:
                shifted_close_differences.append(abs(value / target[shifted] - 1) * 10_000)
        correlations[str(lag)] = correlation([x for x, _ in pairs], [y for _, y in pairs])
        close_differences_by_lag[str(lag)] = shifted_close_differences
    usable = {lag: value for lag, value in correlations.items() if value is not None}
    best_lag = max(usable, key=usable.get) if usable else None
    aligned_differences = sorted(close_differences_by_lag.get(best_lag, []))
    aligned_p95_index = max(0, math.ceil(0.95 * len(aligned_differences)) - 1) if aligned_differences else 0
    ordered = sorted(close_diff_bps)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1) if ordered else 0
    return {
        "proxy_count": len(proxy),
        "ostium_count": len(target),
        "common_days": len(common),
        "first_common": common[0] if common else None,
        "last_common": common[-1] if common else None,
        "close_absolute_difference_bps_median": statistics.median(close_diff_bps) if close_diff_bps else None,
        "close_absolute_difference_bps_p95": ordered[p95_index] if ordered else None,
        "daily_return_correlation": correlations["0"],
        "daily_return_correlation_by_target_day_lag": correlations,
        "best_target_day_lag": int(best_lag) if best_lag is not None else None,
        "aligned_daily_return_correlation": usable.get(best_lag),
        "aligned_close_absolute_difference_bps_median": statistics.median(aligned_differences) if aligned_differences else None,
        "aligned_close_absolute_difference_bps_p95": aligned_differences[aligned_p95_index] if aligned_differences else None,
    }


def alignment_decision(metrics: dict) -> str:
    if metrics["common_days"] == 0:
        return "NO_OVERLAP"
    return "SESSION_ALIGNMENT_REQUIRED" if metrics["best_target_day_lag"] else "DATE_ALIGNED"


def fetch_coinbase(start: str, end: str, timeout: int = 30) -> list[list[float]]:
    query = urllib.parse.urlencode({"start": f"{start}T00:00:00Z", "end": f"{end}T00:00:00Z", "granularity": 86400})
    request = urllib.request.Request(f"{COINBASE_ENDPOINT}?{query}", headers={"user-agent": "alquimia-academia/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def parse_eia_sheet(xml: bytes, start: str, end: str) -> dict[str, float]:
    result = {}
    for row in ET.fromstring(xml).iter(f"{XML_NS}row"):
        values = {}
        for cell in row.findall(f"{XML_NS}c"):
            value = cell.find(f"{XML_NS}v")
            if value is not None:
                values[cell.attrib["r"][0]] = value.text
        if "A" not in values or "B" not in values:
            continue
        try:
            day = (datetime(1899, 12, 30).date() + timedelta(days=int(float(values["A"])))).isoformat()
            close = float(values["B"])
        except (TypeError, ValueError):
            continue
        if start <= day <= end:
            result[day] = close
    return result


def fetch_eia_wti(start: str, end: str, source_url: str = EIA_WTI_XLS, timeout: int = 60) -> dict[str, float]:
    with tempfile.TemporaryDirectory(prefix="alquimia-eia-") as directory:
        root = Path(directory)
        xls = root / "RWTCd.xls"
        request = urllib.request.Request(source_url, headers={"user-agent": "alquimia-academia/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            xls.write_bytes(response.read())
        profile = root / "lo-profile"
        subprocess.run(
            ["libreoffice", f"-env:UserInstallation=file://{profile}", "--headless", "--convert-to", "xlsx", "--outdir", str(root), str(xls)],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        with zipfile.ZipFile(root / "RWTCd.xlsx") as workbook:
            return parse_eia_sheet(workbook.read("xl/worksheets/sheet2.xml"), start, end)


def run_btc(start: str, end: str) -> dict:
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp())
    end_ts = int(datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp())
    proxy = daily_closes(fetch_coinbase(start, end))
    target = ostium_closes(fetch_ostium("BTC-USD", start_ts, end_ts))
    metrics = compare(proxy, target)
    return {
        "schema_version": 1,
        "asset": "BTC/USD",
        "proxy_source": COINBASE_ENDPOINT,
        "target_source": "https://builder.prod.bedrock.ostium.io/v1/ohlc",
        "requested_window": f"{start}/{end}",
        "metrics": metrics,
        "decision": alignment_decision(metrics),
        "promotion_gate": "PENDING_THRESHOLDS_AND_SECOND_WINDOW",
        "raw_candles_persisted": False,
        "holdout_accessed": False,
    }


def run_wti(start: str, end: str, series: str = "front-future") -> dict:
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp())
    end_ts = int(datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp())
    source_url = EIA_WTI_FRONT_FUTURE_XLS if series == "front-future" else EIA_WTI_XLS
    proxy = fetch_eia_wti(start, end, source_url)
    target = ostium_closes(fetch_ostium("CL-USD", start_ts, end_ts))
    metrics = compare(proxy, target)
    return {
        "schema_version": 1,
        "asset": "WTI/USD",
        "proxy_source": source_url,
        "proxy_series": series,
        "target_source": "https://builder.prod.bedrock.ostium.io/v1/ohlc",
        "requested_window": f"{start}/{end}",
        "metrics": metrics,
        "decision": alignment_decision(metrics),
        "promotion_gate": "PENDING_THRESHOLDS_AND_SECOND_WINDOW",
        "raw_candles_persisted": False,
        "holdout_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=["BTC/USD", "WTI/USD"], default="BTC/USD")
    parser.add_argument("--wti-series", choices=["front-future", "spot"], default="front-future")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_btc(args.start, args.end) if args.asset == "BTC/USD" else run_wti(args.start, args.end, args.wti_series)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
