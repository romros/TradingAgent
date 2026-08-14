#!/usr/bin/env python3
"""Validació OOS reproduïble del subset MSFT D1 generat per SQ.

La simulació és deliberadament conservadora: senyal amb barres tancades, entrada a
l'obertura següent, stop abans que target si tots dos es toquen a la mateixa barra,
i una sola posició. No certifica encara paritat d'execució amb Ostium.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from sqx_extract import extract


def _p(node, key, default=0):
    return node.get("params", {}).get(key, default)


class Evaluator:
    def __init__(self, frame: pd.DataFrame):
        self.f = frame
        self.cache: dict[tuple, pd.Series] = {}

    def series(self, node: dict) -> pd.Series:
        op = node["op"]
        children = node.get("children", [])
        shift = int(_p(node, "#Shift#", 0) or 0)
        key = (json.dumps(node, sort_keys=True),)
        if key in self.cache:
            return self.cache[key]
        if op in {"Close", "High", "Low"}:
            out = self.f[op.lower()].shift(shift)
        elif op == "Number":
            out = pd.Series(float(_p(node, "#Value#", 0)), index=self.f.index)
        elif op == "Boolean":
            out = pd.Series(bool(_p(node, "#Value#", False)), index=self.f.index)
        elif op in {"SMA", "EMA", "RSI", "ROC"}:
            period = int(_p(node, "#Period#", 14))
            close = self.f.close
            if op == "SMA": out = close.rolling(period).mean().shift(shift)
            elif op == "EMA": out = close.ewm(span=period, adjust=False, min_periods=period).mean().shift(shift)
            elif op == "ROC": out = (close / close.shift(period) - 1.0).mul(100).shift(shift)
            else:
                delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
                avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
                avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
                out = (100 - 100 / (1 + avg_gain / avg_loss.replace(0, np.nan))).shift(shift)
        elif op == "AND":
            out = pd.Series(True, index=self.f.index)
            for child in children: out &= self.series(child).fillna(False).astype(bool)
        elif op in {"IsGreater", "IsLower"}:
            left, right = map(self.series, children[:2]); out = left > right if op == "IsGreater" else left < right
        elif op in {"CrossesAbove", "CrossesBelow"}:
            left, right = map(self.series, children[:2])
            out = (left > right) & (left.shift(1) <= right.shift(1)) if op == "CrossesAbove" else (left < right) & (left.shift(1) >= right.shift(1))
        elif op in {"IsRising", "IsFalling"}:
            value = self.series(children[0]).shift(int(_p(node, "#Shift#", 0) or 0))
            bars = int(_p(node, "#Bars#", 1)); strict = not bool(_p(node, "#NotStrict#", False))
            out = pd.Series(True, index=self.f.index)
            for n in range(bars):
                a, b = value.shift(n), value.shift(n + 1)
                out &= (a > b if strict and op == "IsRising" else
                        a >= b if op == "IsRising" else
                        a < b if strict else a <= b)
        elif op == "BarDayOfMonth": out = pd.Series(self.f.index.day, index=self.f.index).shift(shift)
        elif op == "BarDayOfWeekIs":
            # SQ/MT4: Sunday=0, Monday=1 ... Saturday=6.
            wanted = int(_p(node, "#Day#", _p(node, "#Value#", 1)))
            out = pd.Series(self.f.index.dayofweek + 1, index=self.f.index).eq(wanted).shift(shift).fillna(False)
        elif op in {"IsMonthFirstTradingDay", "IsMonthLastTradingDay"}:
            month = pd.Series(self.f.index.to_period("M"), index=self.f.index)
            first = month.ne(month.shift(1)); last = month.ne(month.shift(-1))
            # Els extrems del dataset no demostren un canvi de mes: evita senyals
            # artificials creats pel tall del warm-up o del final de mostra.
            if len(first): first.iloc[0] = False
            if len(last): last.iloc[-1] = False
            out = (first if op == "IsMonthFirstTradingDay" else last).shift(shift).fillna(False)
        else:
            raise ValueError(f"Operador no suportat: {op}")
        self.cache[key] = out
        return out


def atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prev = frame.close.shift(1)
    tr = pd.concat([(frame.high-frame.low), (frame.high-prev).abs(), (frame.low-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()


def formula(action: dict, name: str):
    raw = action.get("params", {}).get(name)
    return raw if isinstance(raw, dict) else None


def simulate(frame: pd.DataFrame, contract: dict, start: str, end: str,
             signal_override: pd.Series | None = None) -> dict:
    ev = Evaluator(frame); direction, entry = next((d, e) for d, e in contract["entries"].items() if e)
    signal = (signal_override if signal_override is not None else ev.series(entry["signal"])).fillna(False)
    action = entry["action"]; sl = formula(action, "#StopLoss.StopLoss#"); pt = formula(action, "#ProfitTarget.ProfitTarget#")
    pt_atr = atr(frame, int(pt["params"].get("#AtrPeriod#", 14))) if pt and "ATRBasedValue" in pt["formula"] else None
    sl_atr = atr(frame, int(sl["params"].get("#AtrPeriod#", 14))) if sl and "ATRBasedValue" in sl["formula"] else None
    trades=[]; pos=None; sign=1 if direction == "long" else -1
    for i in range(1, len(frame)):
        day=frame.index[i]; row=frame.iloc[i]
        if pos:
            stop_hit = row.low <= pos["stop"] if sign == 1 else row.high >= pos["stop"]
            target_hit = row.high >= pos["target"] if sign == 1 else row.low <= pos["target"]
            if stop_hit or target_hit:
                price = pos["stop"] if stop_hit else pos["target"]
                ret = sign * (price / pos["entry"] - 1)
                trades.append({"entry_date":str(pos["date"].date()),"exit_date":str(day.date()),"return":ret,
                               "stop_distance_pct":pos["stop_distance"] / pos["entry"] * 100,
                               "bars":i-pos["i"],"reason":"stop" if stop_hit else "target"})
                pos=None
        if pos is None and bool(signal.iloc[i]):
            entry_price=float(row.open)
            # SQ no pot calcular una sortida ATR durant el warm-up. No inventem
            # una distància infinita ni obrim una posició impossible de tancar.
            if pt_atr is not None and math.isnan(pt_atr.iloc[i]):
                continue
            if sl_atr is not None and math.isnan(sl_atr.iloc[i]):
                continue
            if sl and "PctValue" in sl["formula"]:
                stop_distance = entry_price * float(sl["params"]["#Value#"]) / 100
            elif sl_atr is not None and not math.isnan(sl_atr.iloc[i]):
                stop_distance = float(sl["params"]["#Value#"]) * float(sl_atr.iloc[i])
            else:
                stop_distance = math.inf
            if pt_atr is not None and not math.isnan(pt_atr.iloc[i]):
                target_distance = float(pt["params"]["#Value#"]) * float(pt_atr.iloc[i])
            elif pt and "PctValue" in pt["formula"]:
                target_distance = entry_price * float(pt["params"]["#Value#"]) / 100
            else:
                target_distance = math.inf
            pos={"i":i,"date":day,"entry":entry_price,"stop_distance":stop_distance,
                 "stop":entry_price-sign*stop_distance,"target":entry_price+sign*target_distance}
    selected=[t for t in trades if start <= t["entry_date"] <= end]
    returns=np.array([t["return"] for t in selected],dtype=float)
    wins=returns[returns>0].sum() if len(returns) else 0; losses=-returns[returns<0].sum() if len(returns) else 0
    equity=np.cumprod(1+returns) if len(returns) else np.array([]); peak=np.maximum.accumulate(np.r_[1,equity]); curve=np.r_[1,equity]
    dd=float(np.max(1-curve/peak)) if len(curve) else 0
    return {"direction":direction,"trades":len(selected),"win_rate":float((returns>0).mean()) if len(returns) else None,
            "profit_factor":float(wins/losses) if losses else None,"compound_return":float(equity[-1]-1) if len(equity) else 0,
            "max_drawdown":dd,"median_bars":float(np.median([t["bars"] for t in selected])) if selected else None,"trades_detail":selected}


def load_data(start: str, end: str, source: Path | None = None) -> pd.DataFrame:
    if source is not None:
        raw = pd.read_csv(source, header=None)
        if raw.shape[1] < 6:
            raise ValueError("local OHLC source requires date,time,open,high,low,close")
        frame = raw.iloc[:, [0, 2, 3, 4, 5]].copy()
        frame.columns = ["date", "open", "high", "low", "close"]
        frame["date"] = pd.to_datetime(frame["date"], format="%Y.%m.%d")
        frame = frame.set_index("date").sort_index()
        return frame.loc[(frame.index >= start) & (frame.index < end)]
    import yfinance as yf
    frame=yf.download("MSFT",start=start,end=end,auto_adjust=False,progress=False)
    if isinstance(frame.columns,pd.MultiIndex): frame.columns=frame.columns.droplevel(1)
    frame.columns=[str(x).lower() for x in frame.columns]
    return frame[["open","high","low","close"]].dropna()


def main():
    p=argparse.ArgumentParser(); p.add_argument("--inventory",type=Path,action="append",required=True); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--source", type=Path, help="Deterministic local date,time,OHLC CSV")
    p.add_argument("--unseal-holdout", action="store_true")
    p.add_argument("--finalist", action="append", default=[], help="PROJECT_STEM::Strategy name")
    p.add_argument("--data-start",default="1998-01-01"); p.add_argument("--data-end",default="2026-08-02"); a=p.parse_args()
    frame=load_data(a.data_start,a.data_end,a.source); periods={"validation":("2012-10-17","2018-04-23"),"oos":("2018-04-24","2023-10-29")}
    if a.unseal_holdout: periods["holdout"]=("2023-10-30","2026-08-01")
    finalists=set(a.finalist)
    rows=[]
    for inv_path in a.inventory:
        inv=json.loads(inv_path.read_text()); root=Path(inv["source"]); selected=set(inv["pareto_candidates"])
        for c in inv["candidates"]:
            if c["strategy"] not in selected: continue
            identity=f"{inv_path.stem}::{c['strategy']}"
            if finalists and identity not in finalists: continue
            path=root/c["file"]
            try:
                contract=extract(path); result={k:simulate(frame,contract,*v) for k,v in periods.items()}
                rows.append({"project":inv_path.stem,"strategy":c["strategy"],"sqx_sha256":contract["source_sha256"],"translation":contract["translation_status"],"results":result})
            except Exception as exc: rows.append({"project":inv_path.stem,"strategy":c["strategy"],"error":f"{type(exc).__name__}: {exc}"})
    gate_periods=("validation","oos")
    eligible=[r for r in rows if "error" not in r and all(r["results"][p]["trades"]>=25 and (r["results"][p]["profit_factor"] or 0)>=1.15 and r["results"][p]["compound_return"]>0 for p in gate_periods)]
    out={"schema_version":1,"data":"Yahoo MSFT unadjusted OHLC; close parity certified, OHLC execution provisional","periods":periods,"candidate_count":len(rows),"eligible_count":len(eligible),"eligible":[{"project":r["project"],"strategy":r["strategy"],"results":r["results"]} for r in eligible],"candidates":rows}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2)+"\n"); print(json.dumps({"candidates":len(rows),"eligible":len(eligible),"errors":sum('error' in r for r in rows)},indent=2))


if __name__ == "__main__": main()
