#!/usr/bin/env python3
"""Preregistered cross-listing falsification of a gold weekend effect."""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "gold_weekend_effect_preregistration_v1.json"
LOCK = HERE / "gold_weekend_effect_preregistration_v1.lock.json"


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    if "2025" in path.name: raise ValueError("2025+ holdout is sealed")
    rows = []
    for raw in csv.reader(path.open(encoding="utf-8-sig")):
        if not raw: continue
        day = dt.datetime.strptime(raw[0], "%Y.%m.%d").date()
        if day.year >= 2025: raise ValueError("2025+ holdout row")
        rows.append({"date": day, "open": float(raw[2]), "close": float(raw[5])})
    if any(b["date"] <= a["date"] for a,b in zip(rows, rows[1:])): raise ValueError("dates not increasing")
    return rows


def returns(rows: list[dict], variant: str) -> list[tuple[dt.date,float]]:
    by_date = {r["date"]: r for r in rows}; out=[]
    for friday in rows:
        if friday["date"].weekday() != 4: continue
        monday_date = friday["date"] + dt.timedelta(days=3); monday = by_date.get(monday_date)
        if not monday: continue
        if variant == "FRIDAY_CLOSE_TO_MONDAY_CLOSE": entry, exit_ = friday["close"], monday["close"]
        elif variant == "FRIDAY_OPEN_TO_MONDAY_OPEN": entry, exit_ = friday["open"], monday["open"]
        elif variant == "FRIDAY_CLOSE_TO_MONDAY_OPEN": entry, exit_ = friday["close"], monday["open"]
        else: raise ValueError("unknown variant")
        out.append((monday_date, exit_/entry-1))
    return out


def metrics(rows: list[tuple[dt.date,float]], cost_bps: float) -> dict:
    values=[r-cost_bps/10000 for _,r in rows]; n=len(values)
    if not n:return {"trades":0}
    mean=sum(values)/n; sd=(sum((x-mean)**2 for x in values)/(n-1))**.5 if n>1 else 0
    t=mean/(sd/(n**.5)) if sd else None
    # one-sided normal approximation; reported explicitly, not called exact Student-t
    p=.5*math.erfc((t or 0)/math.sqrt(2)) if t is not None else None
    equity=peak=1.;dd=0.;gp=gl=0.
    for value in values:
        equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
        if value>0:gp+=value
        elif value<0:gl-=value
    return {"trades":n,"mean_return":mean,"total_return":equity-1,
            "profit_factor":gp/gl if gl else None,"max_drawdown":dd,
            "t_stat":t,"one_sided_normal_p":p,"wins":sum(x>0 for x in values)}


def period(rows, start, end):
    a,b=map(dt.date.fromisoformat,(start,end));return [x for x in rows if a<=x[0]<=b]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--asset",action="append",required=True)
    ap.add_argument("--output",type=Path,required=True);args=ap.parse_args()
    spec,lock=json.loads(SPEC.read_text()),json.loads(LOCK.read_text())
    if sha(SPEC)!=lock["preregistration_sha256"]:raise ValueError("preregistration lock mismatch")
    paths=dict(x.split("=",1) for x in args.asset)
    if set(paths)!=set(spec["assets"]):raise ValueError("exact frozen assets required")
    report={"schema_version":1,"preregistration_sha256":sha(SPEC),"optimized":False,
            "holdout_2025_accessed":False,"assets":{},"decision":{}}
    gates=spec["gates"]; passing={}
    for asset,path in paths.items():
        source=Path(path);data=load(source);report["assets"][asset]={"source_sha256":sha(source),"variants":{}}
        passing[asset]=set()
        for variant in spec["variants"]:
            raw=returns(data,variant);block={}
            for name,bounds in spec["periods"].items():
                if name=="holdout":continue
                sample=period(raw,*bounds);block[name]={key:metrics(sample,cost) for key,cost in spec["costs_roundtrip_bps"].items()}
            combined=period(raw,spec["periods"]["validation"][0],spec["periods"]["oos"][1])
            block["combined_validation_oos"]={key:metrics(combined,cost) for key,cost in spec["costs_roundtrip_bps"].items()}
            passed=True
            for name in ("train","validation","oos"):
                m=block[name]["stress_1000"]
                passed &= m["trades"]>=gates["minimum_trades"][name] and m["mean_return"]>0 and (m["profit_factor"] or 0)>=gates["each_period_stress_profit_factor_gte"]
            c=block["combined_validation_oos"]["stress_1000"]
            passed &= (c["one_sided_normal_p"] or 1)<=gates["combined_validation_oos_one_sided_t_p_lte"] and c["max_drawdown"]<=gates["combined_validation_oos_stress_max_drawdown_lte"]
            block["pass"]=bool(passed)
            if passed:passing[asset].add(variant)
            report["assets"][asset]["variants"][variant]=block
    shared=sorted(set.intersection(*passing.values()))
    report["decision"]={"status":"PASS_THIRD_EDGE_CANDIDATE" if shared else "REJECT_NO_TRANSFERABLE_WEEKEND_EDGE",
                        "shared_passing_variants":shared,"passing_by_asset":{k:sorted(v) for k,v in passing.items()},
                        "paper_authorized":False,"live_authorized":False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["decision"],indent=2))

if __name__=="__main__":main()
