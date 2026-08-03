#!/usr/bin/env python3
"""Offline OHLC parity gate: SQ Data Manager CSV versus native Ostium M1."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from lab.sq_bridge.msft_source_parity import aggregate_regular_session, load_ostium_m1

FIELDS = ("open", "high", "low", "close")


def _number(row: dict, name: str) -> float:
    for key, value in row.items():
        if key and key.strip().lower() == name:
            return float(value)
    raise ValueError(f"SQ_CSV_MISSING_{name.upper()}")


def load_sq_csv(path: Path) -> list[dict]:
    """Load the frozen custom export format, rejecting duplicate dates."""
    rows=[]; seen=set()
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("SQ_CSV_HEADER_REQUIRED")
        for raw in reader:
            normalized={str(k).strip().lower():v for k,v in raw.items() if k is not None}
            date=(normalized.get("date") or "").strip().replace(".","-")
            if not date:
                continue
            if date in seen:
                raise ValueError(f"SQ_CSV_DUPLICATE_DATE:{date}")
            values={field:_number(normalized,field) for field in FIELDS}
            if (min(values.values()) <= 0
                    or values["high"] < max(values["open"], values["close"])
                    or values["low"] > min(values["open"], values["close"])):
                raise ValueError(f"SQ_CSV_INVALID_OHLC:{date}")
            seen.add(date); rows.append({"date":date,**values})
    if not rows:
        raise ValueError("SQ_CSV_EMPTY")
    return sorted(rows,key=lambda row:row["date"])


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values: return None
    values=sorted(values); return values[min(len(values)-1,math.ceil(len(values)*fraction)-1)]


def _correlation(pairs: list[tuple[float,float]]) -> float | None:
    if len(pairs)<2: return None
    xs,ys=zip(*pairs); mx,my=sum(xs)/len(xs),sum(ys)/len(ys)
    vx=sum((x-mx)**2 for x in xs); vy=sum((y-my)**2 for y in ys)
    if vx<=0 or vy<=0:return None
    return sum((x-mx)*(y-my) for x,y in pairs)/math.sqrt(vx*vy)


def compare(sq_rows: list[dict], ostium_rows: list[dict]) -> dict:
    sq={r["date"]:r for r in sq_rows}; ost={r["date"]:r for r in ostium_rows}
    dates=sorted(set(sq)&set(ost)); differences={field:[] for field in FIELDS}
    for day in dates:
        for field in FIELDS:
            differences[field].append(abs(sq[day][field]/ost[day][field]-1)*10_000)
    returns=[]; directions=[]
    for previous,current in zip(dates,dates[1:]):
        sq_ret=sq[current]["close"]/sq[previous]["close"]-1
        ost_ret=ost[current]["close"]/ost[previous]["close"]-1
        returns.append((sq_ret,ost_ret)); directions.append((sq_ret>=0)==(ost_ret>=0))
    field_stats={field:{"median_bps":median(values) if values else None,
                        "p95_bps":_percentile(values,.95),"max_bps":max(values) if values else None}
                 for field,values in differences.items()}
    only_sq=sorted(set(sq)-set(ost)); only_ostium=sorted(set(ost)-set(sq))
    return {"overlap_days":len(dates),"first_overlap":dates[0] if dates else None,
            "last_overlap":dates[-1] if dates else None,"ohlc":field_stats,
            "daily_return_correlation":_correlation(returns),
            "return_direction_match_ratio":sum(directions)/len(directions) if directions else None,
            "dates_only_sq_count":len(only_sq),"dates_only_sq_examples":only_sq[:10],
            "dates_only_ostium_count":len(only_ostium),"dates_only_ostium_examples":only_ostium[:10]}


def certify(sq_csv: Path, ostium_root: Path, symbol: str) -> dict:
    sq=load_sq_csv(sq_csv); raw=load_ostium_m1(ostium_root); daily,anomalies=aggregate_regular_session(raw)
    complete_daily=[row for row in daily if row["bars"]>=300]
    comparison=compare(sq,complete_daily); reasons=[]; warnings=[]
    if comparison["overlap_days"]<60:reasons.append("OVERLAP_LT_60")
    if (comparison["daily_return_correlation"] or -1)<.98:reasons.append("RETURN_CORRELATION_LT_0_98")
    if (comparison["return_direction_match_ratio"] or 0)<.95:reasons.append("DIRECTION_MATCH_LT_0_95")
    for field in FIELDS:
        stats=comparison["ohlc"][field]
        if stats["median_bps"] is None or stats["median_bps"]>25:
            reasons.append(f"{field.upper()}_MEDIAN_DIFF_GT_25_BPS")
        if stats["p95_bps"] is None or stats["p95_bps"]>100:
            reasons.append(f"{field.upper()}_P95_DIFF_GT_100_BPS")
    incomplete=[r for r in daily if r["bars"]<300]
    if anomalies:warnings.append("OSTIUM_ISOLATED_OUTLIERS_FILTERED")
    if incomplete:warnings.append("INCOMPLETE_OSTIUM_SESSIONS_PRESENT")
    return {"schema_version":1,"symbol":symbol,"sq_csv":str(sq_csv),
            "sq_csv_sha256":hashlib.sha256(sq_csv.read_bytes()).hexdigest(),
            "ostium_root":str(ostium_root),"sq_rows":len(sq),"ostium_m1_rows":len(raw),
            "ostium_regular_days":len(daily),"ostium_complete_days_compared":len(complete_daily),
            "comparison":comparison,
            "ostium_anomalies":anomalies,"incomplete_ostium_sessions":incomplete,
            "scope":"RECENT_OHLC_RESEARCH_PARITY_NOT_EXECUTION_FILL_PARITY",
            "decision":"PASS_RESEARCH_OHLC" if not reasons else "BLOCK",
            "reasons":reasons,"warnings":warnings,"live_authorized":False}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--sq-csv",type=Path,required=True)
    p.add_argument("--ostium-root",type=Path,required=True); p.add_argument("--symbol",required=True)
    p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    result=certify(a.sq_csv,a.ostium_root,a.symbol); a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))


if __name__=="__main__":main()
